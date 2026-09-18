"""Loopback-only demo server. No CDN, build step, or arbitrary filesystem endpoint."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "skills" / "ai-model-router" / "scripts"))
from routerlib.config import RouterError
from routerlib.service import RouterService
from routerlib.settings import SettingsStore


def make_server(port=8765, service=None, settings=None):
    svc = service or RouterService()
    store = settings or SettingsStore()

    def save_settings(req):
        result = store.save(req)
        svc.clear_cache()
        return result

    def clear_settings(req):
        result = store.clear()
        svc.clear_cache()
        return result

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Audit metadata goes to SQLite; never print raw request content.

        def respond(self, status, payload, mime="application/json; charset=utf-8"):
            body = json.dumps(payload, ensure_ascii=False).encode() if not isinstance(payload, bytes) else payload
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def trusted(self):
            host = self.headers.get("Host", "")
            allowed = (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")
            origin = self.headers.get("Origin")
            return host in allowed and (not origin or origin in tuple("http://" + h for h in allowed))

        def do_GET(self):
            if not self.trusted():
                return self.respond(403, {"ok": False, "error": {"code": "ORIGIN_BLOCKED", "message": "仅允许本机同源访问。"}})
            u = urlsplit(self.path)
            static = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8")}
            if u.path in static:
                file, mime = static[u.path]
                return self.respond(200, (ROOT / "web" / file).read_bytes(), mime)
            try:
                if u.path == "/api/stats":
                    return self.respond(200, svc.stats())
                if u.path == "/api/settings":
                    return self.respond(200, store.status())
                if u.path == "/api/health":
                    return self.respond(200, {"ok": True, "version": "2.0.0"})
            except RouterError as exc:
                return self.respond(400, {"ok": False, "error": {"code": exc.code, "message": exc.message}})
            self.respond(404, {"ok": False, "error": {"code": "NOT_FOUND", "message": "接口不存在。"}})

        def do_POST(self):
            if not self.trusted():
                return self.respond(403, {"ok": False, "error": {"code": "ORIGIN_BLOCKED", "message": "仅允许本机同源访问。"}})
            try:
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise RouterError("CONTENT_TYPE", "请求必须为 application/json。")
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 120000:
                    raise RouterError("BODY_SIZE", "请求体长度无效或超过 120 KB。")
                self.connection.settimeout(10)
                req = json.loads(self.rfile.read(length).decode("utf-8"))
                actions = {"/api/plan": svc.preview, "/api/run": svc.run,
                           "/api/settings": save_settings, "/api/settings/clear": clear_settings,
                           "/api/settings/check": lambda _: store.check()}
                if self.path == "/api/cache/clear":
                    return self.respond(200, svc.clear_cache())
                if self.path not in actions:
                    return self.respond(404, {"ok": False, "error": {"code": "NOT_FOUND", "message": "接口不存在。"}})
                result = actions[self.path](req)
                self.respond(200 if result["ok"] else 502, result)
            except RouterError as exc:
                self.respond(400, {"ok": False, "error": {"code": exc.code, "message": exc.message}})
            except (ValueError, UnicodeError):
                self.respond(400, {"ok": False, "error": {"code": "INVALID_JSON", "message": "请求 JSON 无效。"}})
            except Exception:
                self.respond(500, {"ok": False, "error": {"code": "INTERNAL_ERROR", "message": "本地服务异常，请检查依赖和运行目录权限。"}})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()
    # Warm up SDK before accepting requests; no model call or API key required.
    import litellm
    server = make_server(args.port)
    print(f"RouteLab ready: http://127.0.0.1:{server.server_port} (Ctrl+C to stop)", flush=True)
    if args.open_browser:
        import threading
        import webbrowser
        threading.Timer(0.5, lambda: webbrowser.open(f"http://127.0.0.1:{server.server_port}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
