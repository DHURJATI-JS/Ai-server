"""
Local AI gateway: ONE link for every device on your Wi-Fi / LAN.

Every request goes to THIS PC's model server first. It switches to the
OTHER PC when this one is:
  - busy      (all its slots are already answering requests)
  - overloaded (CPU on this PC above LOCAL_CPU_LIMIT)
  - offline   (model server not running / still loading)

Run:   double-click 3_start_gateway.bat   (or: python gateway.py)
Link:  http://<this PC's IP>:8000/v1       (OpenAI-compatible)
Check: http://<this PC's IP>:8000/status   (open in any browser)
"""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
import psutil
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

# ============================ settings ============================
OTHER_PC_IP = "192.168.0.223"                # <- your other PC's IP (run ipconfig there)
GATEWAY_PORT = 8000
GATEWAY_API_KEY = "change-me-gateway-key"   # the key your apps / devices use
SERVER_API_KEY = "change-me-server-key"     # same as API_KEY in 2_start_server.bat
SLOTS_PER_PC = 2                            # same as SLOTS in 2_start_server.bat
LOCAL_CPU_LIMIT = 90                        # % CPU; set to None to ignore CPU load
HEALTH_CHECK_SECONDS = 5
# ==================================================================


@dataclass(eq=False)
class Backend:
    name: str
    url: str
    max_inflight: int
    is_local: bool
    healthy: bool = False
    inflight: int = 0


backends = [
    Backend("this-pc", "http://127.0.0.1:8080", SLOTS_PER_PC, is_local=True),
    Backend("other-pc", f"http://{OTHER_PC_IP}:8080", SLOTS_PER_PC, is_local=False),
]
local_cpu = 0.0
client: httpx.AsyncClient


async def health_loop() -> None:
    """Every few seconds: is each model server up and ready? How busy is this PC's CPU?"""
    global local_cpu
    psutil.cpu_percent(interval=None)  # prime the counter
    async with httpx.AsyncClient(timeout=3) as hc:
        while True:
            for b in backends:
                was = b.healthy
                try:
                    r = await hc.get(f"{b.url}/health")
                    b.healthy = r.status_code == 200   # 503 = still loading the model
                except httpx.HTTPError:
                    b.healthy = False
                if b.healthy != was:
                    print(f"[gateway] {b.name} is now {'ONLINE' if b.healthy else 'OFFLINE'}")
            local_cpu = psutil.cpu_percent(interval=None)
            await asyncio.sleep(HEALTH_CHECK_SECONDS)


def is_overloaded(b: Backend) -> bool:
    if b.inflight >= b.max_inflight:
        return True
    if b.is_local and LOCAL_CPU_LIMIT is not None and local_cpu >= LOCAL_CPU_LIMIT:
        return True
    return False


def choose(exclude: list[Backend]) -> Backend | None:
    online = [b for b in backends if b.healthy and b not in exclude]
    if not online:
        return None
    for b in online:                       # this PC first, then the other PC
        if not is_overloaded(b):
            return b
    # everyone is busy: queue on whichever is least loaded
    return min(online, key=lambda b: b.inflight / b.max_inflight)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global client
    client = httpx.AsyncClient(timeout=httpx.Timeout(connect=3, read=None, write=60, pool=None))
    task = asyncio.create_task(health_loop())
    print(f"[gateway] listening on http://0.0.0.0:{GATEWAY_PORT}/v1")
    yield
    task.cancel()
    await client.aclose()


app = FastAPI(title="Local AI gateway", lifespan=lifespan)

DROP_REQUEST_HEADERS = {"host", "content-length", "authorization", "connection", "transfer-encoding", "keep-alive"}
DROP_RESPONSE_HEADERS = {"content-length", "transfer-encoding", "connection", "content-encoding", "keep-alive"}


@app.get("/status")
async def status():
    return {
        "this_pc_cpu_percent": local_cpu,
        "backends": [
            {
                "name": b.name,
                "url": b.url,
                "online": b.healthy,
                "busy_slots": f"{b.inflight}/{b.max_inflight}",
                "overloaded": is_overloaded(b),
            }
            for b in backends
        ],
    }


@app.api_route("/v1/{path:path}", methods=["GET", "POST"])
async def proxy(path: str, request: Request):
    if GATEWAY_API_KEY and request.headers.get("authorization") != f"Bearer {GATEWAY_API_KEY}":
        raise HTTPException(401, "Wrong or missing API key")

    body = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower() not in DROP_REQUEST_HEADERS}
    headers["authorization"] = f"Bearer {SERVER_API_KEY}"

    tried: list[Backend] = []
    while True:
        b = choose(exclude=tried)
        if b is None:
            raise HTTPException(503, "No model server is available right now.")
        tried.append(b)
        b.inflight += 1
        try:
            upstream = await client.send(
                client.build_request(
                    request.method, f"{b.url}/v1/{path}",
                    params=request.query_params, headers=headers, content=body,
                ),
                stream=True,
            )
        except httpx.HTTPError:
            b.inflight -= 1
            b.healthy = False                  # couldn't reach it: try the other PC
            print(f"[gateway] {b.name} unreachable, switching")
            continue

        if upstream.status_code == 503 and choose(exclude=tried):
            await upstream.aclose()            # this one says it's busy/loading: try the other PC
            b.inflight -= 1
            continue

        async def relay(upstream=upstream, b=b):
            try:
                async for chunk in upstream.aiter_bytes():
                    yield chunk
            finally:
                await upstream.aclose()
                b.inflight -= 1

        out_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in DROP_RESPONSE_HEADERS}
        out_headers["x-served-by"] = b.name
        return StreamingResponse(relay(), status_code=upstream.status_code, headers=out_headers)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=GATEWAY_PORT)
