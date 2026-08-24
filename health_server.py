"""Tiny keepalive HTTP server for Railway/Render free deployments.

GhostGram is a pure MTProto userbot (no web framework), so we bind a minimal
http.server in a background thread so the platform's port check stays happy.
"""
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (stdlib naming)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"GhostGram is alive \xf0\x9f\x91\xbb\n")

    def log_message(self, *args, **kwargs):
        pass  # stay quiet


def start_health_server():
    port = int(os.getenv("PORT") or os.getenv("HEALTH_PORT") or 10000)
    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), _HealthHandler)
    except OSError as e:
        print(f"⚠️ Health server could not bind port {port}: {e}")
        return
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="health-server")
    thread.start()
    print(f"🌐 Health server listening on 0.0.0.0:{port}")
