#!/usr/bin/env python3
"""Deterministic mock Veeam API used by token refresh integration tests."""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict

TOKENS: Dict[str, float] = {}
REFRESH_TOKENS: Dict[str, float] = {}
TOKEN_LIFETIME = 20
LOG_FILE = Path("/tmp/mock_veeam_server.log")


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)


class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True


class MockVeeamHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        log(fmt % args)

    def do_POST(self) -> None:  # noqa: N802
        log(f"POST {self.path}")
        if self.path in ["/oauth2/token", "/api/oauth2/token"]:
            self.handle_token_request()
            return
        self.send_json(404, {"error": "Not found"})

    def do_GET(self) -> None:  # noqa: N802
        auth_header = self.headers.get("Authorization", "")
        log(f"GET {self.path} auth={auth_header[:40]}")

        if self.path == "/health":
            self.send_json(200, {"ok": True})
            return

        if self.path in ["/api/v1/serverTime", "/v1/serverTime"]:
            self.handle_server_time(auth_header)
            return

        if self.path in ["/api/v1/backups", "/v1/backups"]:
            self.handle_backups(auth_header)
            return

        self.send_json(404, {"error": "Not found"})

    def handle_token_request(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length).decode("utf-8")
        params = urllib.parse.parse_qs(body)
        grant_type = params.get("grant_type", [""])[0]

        log(f"Grant type: {grant_type}")

        if grant_type == "password":
            username = params.get("username", [""])[0]
            password = params.get("password", [""])[0]
            if username != "test" or password != "test":
                self.send_json(401, {"error": "invalid credentials"})
                return

            self.issue_tokens(prefix="access")
            return

        if grant_type == "refresh_token":
            refresh_token = params.get("refresh_token", [""])[0]
            if refresh_token not in REFRESH_TOKENS:
                self.send_json(401, {"error": "invalid refresh token"})
                return

            self.issue_tokens(prefix="access_refreshed")
            return

        self.send_json(400, {"error": "unsupported grant type"})

    def issue_tokens(self, prefix: str) -> None:
        now = time.time()
        access_token = f"{prefix}_{int(now * 1000)}"
        refresh_token = f"refresh_{int(now * 1000)}"
        TOKENS[access_token] = now
        REFRESH_TOKENS[refresh_token] = now

        response = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": TOKEN_LIFETIME,
            "token_type": "Bearer",
        }
        log(f"Issued access token: {access_token}")
        self.send_json(200, response)

    def handle_server_time(self, auth_header: str) -> None:
        if not self.is_valid_token(auth_header):
            log("RESULT: 401 Unauthorized")
            self.send_json(401, {"error": "unauthorized"})
            return

        self.send_json(200, {"serverTime": time.strftime("%Y-%m-%dT%H:%M:%S")})

    def handle_backups(self, auth_header: str) -> None:
        if not self.is_valid_token(auth_header):
            log("RESULT: 401 Unauthorized")
            self.send_json(401, {"error": "unauthorized"})
            return

        self.send_json(
            200,
            {
                "data": [
                    {"name": "backup1", "platformName": "VmWare"},
                    {"name": "backup2", "platformName": "HyperV"},
                ]
            },
        )

    def is_valid_token(self, auth_header: str) -> bool:
        if not auth_header.startswith("Bearer "):
            return False

        token = auth_header[7:].strip()
        created_at = TOKENS.get(token)
        if created_at is None:
            return False

        elapsed = time.time() - created_at
        if elapsed > TOKEN_LIFETIME:
            log(f"Token expired: token={token[:20]} elapsed={elapsed:.2f}s")
            return False

        return True

    def send_json(self, status_code: int, data: dict) -> None:
        encoded = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9999)
    parser.add_argument("--token-lifetime", type=int, default=20)
    parser.add_argument("--log-file", default="/tmp/mock_veeam_server.log")
    return parser.parse_args()


def main() -> None:
    global TOKEN_LIFETIME, LOG_FILE

    args = parse_args()
    TOKEN_LIFETIME = args.token_lifetime
    LOG_FILE = Path(args.log_file)

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text("", encoding="utf-8")

    server = ReusableHTTPServer((args.host, args.port), MockVeeamHandler)
    log(f"Mock Veeam server listening on http://{args.host}:{args.port}")
    log(f"Token lifetime: {TOKEN_LIFETIME}s")
    log(f"Log file: {LOG_FILE}")
    server.serve_forever()


if __name__ == "__main__":
    main()
