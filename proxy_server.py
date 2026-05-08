#!/usr/bin/env python3
"""反向代理服务器：静态文件 + /api/* 转发到 MES"""
import http.server
import socketserver
import urllib.request
import urllib.error
import os
import threading
import time

MES_HOST = "localhost"
MES_PORT = 8000
STATIC_PORT = 8503
STATIC_DIR = "/Users/xuyan/software/hermesWorkspace"
PROXY_PATHS = {"/api", "/health"}

class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_GET(self):
        if self.should_proxy(self.path):
            self.proxy_request("GET")
        else:
            super().do_GET()

    def do_POST(self):
        if self.should_proxy(self.path):
            self.proxy_request("POST")
        else:
            super().do_GET()

    def should_proxy(self, path):
        for p in PROXY_PATHS:
            if path == p or path.startswith(p + "/"):
                return True
        return False

    def proxy_request(self, method):
        mes_path = f"http://{MES_HOST}:{MES_PORT}{self.path}"
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else None

            headers = {}
            for k, v in self.headers.items():
                if k.lower() not in ("host", "connection"):
                    headers[k] = v
            headers["Connection"] = "close"

            req = urllib.request.Request(
                mes_path,
                data=body,
                headers=headers,
                method=method
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(k, v)
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(resp.read())
        except urllib.error.URLError as e:
            self.send_error(502, f"MES unreachable: {e}")

    def log_message(self, format, *args):
        print(f"[{time.strftime('%H:%M:%S')}] {args[0]}")
        super().log_message(format, *args)

    def __init__(self, *args, **kwargs):
        # Python 3.7+ compatible super()
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == "__main__":
    server = ThreadedHTTPServer(("", STATIC_PORT), ProxyHandler)
    print(f"Proxy server running on http://localhost:{STATIC_PORT}")
    print(f"  Static: /*        -> {STATIC_DIR}")
    print(f"  Proxy:  /api/*, /health -> http://localhost:{MES_PORT}/*")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()
