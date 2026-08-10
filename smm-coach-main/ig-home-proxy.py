#!/usr/bin/env python3
"""
IG SCRAPER UCHUN UY PROXY — sof Python (tashqi kutubxona KERAK EMAS).

Vazifasi: agents serveridan kelgan Instagram so'rovlarini SHU kompyuterning
uy interneti (residential IP) orqali yuboradi. Shu sabab Instagram datacenter
IP o'rniga oddiy foydalanuvchi IP'sini ko'radi.

Ishlaydi: HTTPS (CONNECT tunnel) + oddiy HTTP. instagrapi'ga shu yetarli.

ISHGA TUSHIRISH (thinkbook — 100.118.108.116):
    python ig-home-proxy.py

To'xtatish: Ctrl+C
Tekshirish: konsolda "listening on 0.0.0.0:8888" chiqishi kerak; so'rov kelsa
            "CONNECT <host>" qatorlari ko'rinadi.

ESLATMA: Windows Firewall'da 8888 ochiq bo'lsin (siz buni qilgansiz) va
         kompyuter uyqu rejimiga o'tmasin (Settings -> Power -> Never sleep).
"""
from __future__ import annotations

import select
import socket
import sys
import threading

# ── Sozlamalar ───────────────────────────────────────────────────────────────
LISTEN_HOST = "0.0.0.0"   # barcha interfeyslar (Tailscale 100.118.108.116 ham)
# Port: birinchi argument bilan beriladi, aks holda 8888. Masalan:
#   python ig-home-proxy.py          → 8888
#   python ig-home-proxy.py 9000     → 9000
LISTEN_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8888
BUFSIZE = 65536
TIMEOUT = 60              # soniya — bo'sh ulanishni yopish
# ─────────────────────────────────────────────────────────────────────────────


def _pipe(a: socket.socket, b: socket.socket) -> None:
    """a va b o'rtasida ikki tomonlama ma'lumot uzatadi (biri yopilguncha)."""
    socks = [a, b]
    try:
        while True:
            r, _, x = select.select(socks, [], socks, TIMEOUT)
            if x or not r:
                break
            for s in r:
                data = s.recv(BUFSIZE)
                if not data:
                    return
                (b if s is a else a).sendall(data)
    except OSError:
        pass


def _read_headers(client: socket.socket) -> bytes:
    """So'rov qatori + sarlavhalarni (bo'sh qatorgacha) o'qiydi."""
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = client.recv(BUFSIZE)
        if not chunk:
            return data
        data += chunk
        if len(data) > BUFSIZE:  # noto'g'ri so'rovdan himoya
            break
    return data


def _handle(client: socket.socket, addr: tuple) -> None:
    client.settimeout(TIMEOUT)
    upstream: socket.socket | None = None
    try:
        data = _read_headers(client)
        if b"\r\n" not in data:
            client.close()
            return
        line = data.split(b"\r\n", 1)[0].decode("latin-1", "replace")
        parts = line.split()
        if len(parts) < 3:
            client.close()
            return
        method, target, version = parts[0], parts[1], parts[2]
        header_end = data.find(b"\r\n\r\n")
        leftover = data[header_end + 4:] if header_end != -1 else b""

        # ── HTTPS: CONNECT host:port → TLS tunnel ────────────────────────────
        if method.upper() == "CONNECT":
            host, _, port_s = target.partition(":")
            port = int(port_s or 443)
            print(f"CONNECT {host}:{port}", flush=True)
            try:
                upstream = socket.create_connection((host, port), timeout=TIMEOUT)
            except OSError as exc:
                client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                print(f"  502 {host}: {exc}", flush=True)
                client.close()
                return
            client.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
            if leftover:
                upstream.sendall(leftover)
            _pipe(client, upstream)
            return

        # ── Oddiy HTTP: absolyut URL (http://host/path) ──────────────────────
        if target.startswith("http://"):
            rest = target[len("http://"):]
            hostport, _, path = rest.partition("/")
            host, _, port_s = hostport.partition(":")
            port = int(port_s or 80)
            print(f"{method} http://{host}/{path}", flush=True)
            new_line = f"{method} /{path} {version}".encode("latin-1")
            rebuilt = new_line + data[len(line.encode("latin-1", "replace")):]
            try:
                upstream = socket.create_connection((host, port), timeout=TIMEOUT)
            except OSError as exc:
                client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                print(f"  502 {host}: {exc}", flush=True)
                client.close()
                return
            upstream.sendall(rebuilt)
            _pipe(client, upstream)
            return

        client.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
        client.close()
    except Exception as exc:  # noqa: BLE001 — bitta xato butun proxyni o'ldirmasin
        print(f"  xato {addr}: {exc!r}", flush=True)
    finally:
        try:
            client.close()
        except OSError:
            pass
        if upstream is not None:
            try:
                upstream.close()
            except OSError:
                pass


def main() -> None:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind((LISTEN_HOST, LISTEN_PORT))
    except OSError as exc:
        print(f"[proxy] {LISTEN_HOST}:{LISTEN_PORT} ga bog'lanib bo'lmadi: {exc}")
        print("       (port band? boshqa proxy/gost ishlayaptimi? yoki ruxsat yo'q?)")
        sys.exit(1)
    srv.listen(256)
    print(f"[proxy] listening on {LISTEN_HOST}:{LISTEN_PORT} — to'xtatish: Ctrl+C")
    print("[proxy] so'rov kelsa pastda 'CONNECT <host>' qatorlari ko'rinadi.\n")
    try:
        while True:
            client, addr = srv.accept()
            threading.Thread(target=_handle, args=(client, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[proxy] to'xtatildi.")
    finally:
        srv.close()


if __name__ == "__main__":
    main()
