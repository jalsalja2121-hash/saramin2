"""Loopback-only HTML form, written and served entirely from Python."""
from __future__ import annotations

from contextlib import contextmanager
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlsplit
import secrets
import sqlite3


def initialize(db: Path):
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS submissions (
            run_id TEXT PRIMARY KEY, company TEXT NOT NULL, role TEXT NOT NULL,
            title TEXT NOT NULL, body TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")


def get_submission(db: Path, run_id: str):
    with sqlite3.connect(db) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM submissions WHERE run_id = ?", (run_id,)).fetchone()
        return dict(row) if row else None


@contextmanager
def demo_server(db: Path, run_id: str):
    initialize(db)
    token = secrets.token_urlsafe(24)
    route = f"/{token}"

    class Handler(BaseHTTPRequestHandler):
        def handle(self):
            try:
                super().handle()
            except (ConnectionResetError, BrokenPipeError):
                pass  # Browsers can close speculative keep-alive connections.

        def log_message(self, *_):
            pass

        def send_html(self, status, body):
            data = ("<!doctype html><html lang='ko'><meta charset='utf-8'>"
                    "<title>채용 업무 · 입력 데모</title><body>" + body + "</body></html>").encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if urlsplit(self.path).path != route:
                return self.send_html(404, "페이지를 찾을 수 없습니다.")
            self.send_html(200, f"""
                <h1>채용 분석 보고서 등록</h1>
                <p>로컬 테스트 사이트 · 실제 외부 서비스에 전송하지 않습니다.</p>
                <form action='{route}' method='post'>
                <input type='hidden' name='token' value='{token}'>
                <p><label>회사 <input id='company' name='company' required></label></p>
                <p><label>직무 <input id='role' name='role' required></label></p>
                <p><label>문서 제목 <input id='title' name='title' required size='60'></label></p>
                <p><label>문서 내용<br><textarea id='body' name='body' rows='22' cols='100' required></textarea></label></p>
                <button id='submit' type='submit'>저장</button></form>""")

        def do_POST(self):
            if urlsplit(self.path).path != route:
                return self.send_html(404, "페이지를 찾을 수 없습니다.")
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1_000_000:
                    return self.send_html(413, "허용된 입력 크기를 초과했습니다.")
                values = parse_qs(self.rfile.read(length).decode("utf-8"))
                if not secrets.compare_digest(values.get("token", [""])[0], token):
                    return self.send_html(403, "유효하지 않은 요청입니다.")
                data = {key: values.get(key, [""])[0].replace("\r\n", "\n").strip()
                        for key in ("company", "role", "title", "body")}
                if not all(data.values()):
                    return self.send_html(400, "모든 항목을 입력해 주세요.")
                with sqlite3.connect(db) as con:
                    con.execute("INSERT OR IGNORE INTO submissions(run_id, company, role, title, body) VALUES (?, ?, ?, ?, ?)",
                                (run_id, data["company"], data["role"], data["title"], data["body"]))
                self.send_html(200, f"<h1 id='success' data-run-id='{escape(run_id)}'>저장 완료</h1>")
            except (ValueError, UnicodeDecodeError):
                self.send_html(400, "입력을 읽을 수 없습니다.")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}{route}"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
