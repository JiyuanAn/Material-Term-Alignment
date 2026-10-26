# -*- coding: utf-8 -*-
"""Material Term Alignment HTTP service.

Start from the src directory:
    python -m term_align.server
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .align import align_object, align_property, get_service
from . import config


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] != "/health":
            self._send({"ok": False, "error": "未知路径"}, 404)
            return
        service = get_service()
        self._send({
            "ok": True,
            "n_properties": len(service.lexicon.properties),
            "n_entities": len(service.lexicon.entities),
        })

    def do_POST(self):
        path = self.path.split("?")[0]
        if path not in ("/api/align/property", "/api/align/object"):
            self._send({"ok": False, "error": "未知路径"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b""
            body = json.loads(raw.decode("utf-8")) if raw else {}
            if not isinstance(body, dict):
                raise ValueError("请求体必须是 JSON 对象")
            if path.endswith("/property"):
                result = align_property(
                    body.get("name"),
                    unit=body.get("unit"),
                    context_fields=body.get("context_fields"),
                )
            else:
                result = align_object(body.get("name"))
            self._send({"ok": True, "result": result})
        except ValueError as exc:
            self._send({"ok": False, "error": str(exc)}, 400)
        except json.JSONDecodeError:
            self._send({"ok": False, "error": "请求体不是合法 JSON"}, 400)

    def _send(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        return


def main():
    service = get_service()
    print(
        f"属性词条 {len(service.lexicon.properties)}，实体词条 {len(service.lexicon.entities)}",
        flush=True,
    )
    server = ThreadingHTTPServer((config.HOST, config.PORT), Handler)
    print(f"就绪 http://{config.HOST}:{config.PORT}/health", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
