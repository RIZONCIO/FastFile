# FastFile v3.7 — Secure Anonymous P2P File Transfer

TLS 1.3 + AES-256-GCM + zlib + optional Tor.  No logs. No history. No tracking.

---

## Requirements

- Python 3.8+
- Same local network (LAN) for auto-discovery, or VPN/Tor for cross-network

Dependencies installed automatically on first run:
cryptography >=41.0, colorama >=0.4, netifaces >=0.11, zeroconf >=0.60, stem >=1.8, PySocks >=1.7

Linux note: FastFile retries with --break-system-packages if pip is blocked by PEP 668.

---

## Start

    Windows:  python main.py
    Linux:    python3 main.py

---

## Menu

    [1] Start / Tor          Start node + optional Tor. Toggle Tor if already running.
    [2] View peers           List active peers on your network.
    [3] Connect to peer      Add peer by Node ID (cross-network / VPN).
    [4] Send file(s)         Send to peer OR start mobile web transfer (phone/tablet).
    [5] Profile / Settings   Identity, security, formats, share via email.
    [6] Exit
    [7] Self-destruct        Remove all data + uninstall packages + delete program.

---

## Security

- TLS 1.3 mandatory (no downgrade)
- AES-256-GCM per file, session key via HKDF-SHA384
- HMAC-SHA256 integrity check after each file
- zlib level-6 compression before encryption (mandatory)
- Anonymous Node ID (Blake2b entropy, no hostname/MAC/IP)
- EC P-384 self-signed cert (no personal info)
- Optional Tor onion routing (hides real IP from peers)
- UDP heartbeat every 20s (peers stay alive, no TCP reconnect spam)
- Zero logging — no transfer history, nothing written to disk

---

## [4] Send modes

    [1] Send 1 file          Max 20 MB. GUI file picker or terminal browser.
    [2] Send multiple files  Max 200 MB total. Ctrl+click in GUI.
    [3] Mobile web transfer  LAN HTTP server for phone/tablet (port 8765).
                             PIN-protected. Hacker 90s theme. LAN-only enforced.

---

## Cross-network

    VPN (recommended): Tailscale, ZeroTier, WireGuard — then use [3] with VPN IP
    Tor both sides:    Enable in [1], add peer in [3]
    Port forward:      Open TCP 55771 on router (exposes real IP)

---

## Self-destruct

Types DESTROY then YES. Removes: downloads, certs, config, pip packages, program folder.

---

## File limits

    Per file:  20 MB max
    Per batch: 200 MB max
    Blocked:   video, Photoshop/Illustrator/Premiere/AE, RAW photos, disk images, DAW projects
    Tip:       compress blocked formats into .zip before sending
