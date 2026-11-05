# Local AI server: one link for your whole Wi-Fi / LAN

Each PC runs its own copy of the model. A small Python gateway on **this PC**
gives you one link. Requests go to this PC first and switch to your
**other PC** when this one is busy, overloaded or offline.

```
phone / laptop / your Python apps
            │
            ▼
   http://<this PC's IP>:8000/v1      ← the single link (gateway.py)
            │
   ┌────────┴─────────┐
   ▼                  ▼
this PC :8080      other PC :8080      (llama-server, same model on both)
first choice       used when this PC is busy or down
```

## Setup on THIS PC

1. Right-click **`1_setup_this_pc.bat`** and choose **Run as administrator**.
   It detects your GPU, downloads llama.cpp into `C:\llama`, opens the firewall
   for your home network and prints this PC's IP address.
2. Open `2_start_server.bat` and `gateway.py` and change the
   `change-me-...` keys. In `gateway.py`, set `OTHER_PC_IP`.
3. Double-click **`2_start_server.bat`**. The first run downloads Gemma 3 12B (~8 GB).
   Wait for `server is listening`.
4. Double-click **`3_start_gateway.bat`**. This needs Python installed.

## Setup on the OTHER PC

Copy `1_setup_this_pc.bat`, `setup.ps1` and `2_start_server.bat` to it.
Then do steps 1 and 3 above. Use the **same keys and model** as this PC.
It doesn't need the gateway.

## Using it

- **Python:** see `client.py`. Use `pip install openai`, then point `base_url` at
  `http://<this PC's IP>:8000/v1` with your gateway key.
- **Check what's happening:** open `http://<this PC's IP>:8000/status` in any browser.
  It shows which PCs are online and how many slots are busy.
- Every reply carries an `x-served-by` header (`this-pc` or `other-pc`).

## When does it switch?

| This PC is…                                        | Request goes to                                    |
|----------------------------------------------------|----------------------------------------------------|
| online, has a free slot, CPU below 90%             | this PC                                            |
| all slots busy (default 2 at once)                 | other PC                                           |
| CPU at or above `LOCAL_CPU_LIMIT` (90%)            | other PC                                           |
| server stopped, crashed or still loading           | other PC (checked every 5 s, and instantly on errors) |
| both PCs busy                                      | queued on the least busy PC                        |

## Tips

- **Other devices can't connect?** In Windows Settings → Network, set your Wi-Fi or
  Ethernet to **Private**. The firewall rules only apply to private networks.
- **Fixed IPs:** reserve both PCs' IPs in your router so the links never change.
- **Bigger model:** put `unsloth/gemma-3-27b-it-GGUF:Q4_K_M` in `2_start_server.bat`.
  It's ~17 GB, so part of it runs from RAM and it'll be slower, especially on the RTX 3060.
- **Update llama.cpp:** run `1_setup_this_pc.bat` again.
- **The gateway runs on this PC.** If this PC is switched off, the link is down.
  You can still reach the other PC directly at `http://<other PC's IP>:8080/v1`
  with the server key.
- Don't port-forward these ports to the internet. Use Tailscale for access away from home.
