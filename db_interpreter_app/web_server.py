import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .core import MODE_SQL
from .core.database_service import DatabaseService


class InterpreterHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address, request_handler_class, service, static_dir):
        super().__init__(server_address, request_handler_class)
        self.service = service
        self.static_dir = static_dir


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "DBInterpreterWeb/1.0"

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path.startswith("/api/"):
            self._handle_api_get(parsed.path)
            return

        self._serve_static(parsed.path)

    def do_POST(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self._send_json(404, {"ok": False, "error": "Not found"})
            return

        self._handle_api_post(parsed.path)

    def _handle_api_get(self, path):
        service = self.server.service

        try:
            if path == "/api/bootstrap":
                payload = service.get_bootstrap_state()
                self._send_json(200, {"ok": True, **payload})
                return

            if path == "/api/schema":
                schema = service.view_schema()
                self._send_json(200, {"ok": True, "schema": schema})
                return

            if path == "/api/tables":
                tables = service.get_tables()
                self._send_json(200, {"ok": True, "tables": tables})
                return

            if path == "/api/generate-sql":
                generated = service.generate_sql_code()
                self._send_json(200, {"ok": True, "sql": generated})
                return

            self._send_json(404, {"ok": False, "error": "Unknown API route"})
        except ValueError as error:
            self._send_json(400, {"ok": False, "error": str(error)})
        except RuntimeError as error:
            self._send_json(409, {"ok": False, "error": str(error)})
        except Exception as error:
            self._send_json(500, {"ok": False, "error": str(error)})

    def _handle_api_post(self, path):
        service = self.server.service

        try:
            body = self._read_json_body()

            if path == "/api/execute":
                result = service.execute(
                    mode=body.get("mode", MODE_SQL),
                    code=body.get("code", ""),
                    autocommit=bool(body.get("autocommit", True)),
                )
                self._send_json(200, result)
                return

            if path == "/api/explain":
                explanation = service.explain(body.get("query", ""))
                self._send_json(200, {"ok": True, "explanation": explanation})
                return

            if path == "/api/switch-db":
                state = service.switch_database(body.get("name", ""))
                self._send_json(200, {"ok": True, **state})
                return

            if path == "/api/create-db":
                state = service.create_database(body.get("name", ""))
                self._send_json(200, {"ok": True, **state})
                return

            if path == "/api/commit":
                status = service.commit()
                self._send_json(200, {"ok": True, "status": status})
                return

            if path == "/api/rollback":
                status = service.rollback()
                self._send_json(200, {"ok": True, "status": status})
                return

            if path == "/api/nuke":
                result = service.nuke_database()
                self._send_json(200, {"ok": True, **result})
                return

            self._send_json(404, {"ok": False, "error": "Unknown API route"})

        except ValueError as error:
            self._send_json(400, {"ok": False, "error": str(error)})
        except RuntimeError as error:
            self._send_json(409, {"ok": False, "error": str(error)})
        except Exception as error:
            self._send_json(500, {"ok": False, "error": str(error)})

    def _read_json_body(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b"{}"
        if not raw_body:
            return {}
        return json.loads(raw_body.decode("utf-8"))

    def _serve_static(self, raw_path):
        static_dir = self.server.static_dir.resolve()
        path = raw_path or "/"
        if path == "/":
            path = "/index.html"

        target = (static_dir / path.lstrip("/")).resolve()
        if not str(target).startswith(str(static_dir)):
            self.send_error(403)
            return

        if not target.exists() or target.is_dir():
            self.send_error(404)
            return

        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"

        with open(target, "rb") as file:
            content = file.read()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


def run_web_app(host="127.0.0.1", port=8000):
    base_dir = Path(os.getcwd()).resolve()
    static_dir = Path(__file__).resolve().parent / "web"

    service = DatabaseService(base_dir=base_dir)
    server = InterpreterHTTPServer((host, port), RequestHandler, service=service, static_dir=static_dir)

    print(f"Starting web app on http://{host}:{port}")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.close()
        server.server_close()
