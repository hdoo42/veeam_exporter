#!/usr/bin/env python3
"""End-to-end token refresh test.

Observed engine behavior:
- login script is triggered when auth is invalid (401/403), not on every scrape.

Test model:
1) First scrape: no token -> 401 -> password grant.
2) Second scrape before expiry: token reuse.
3) Third scrape after expiry: 401 -> refresh_token grant -> scrape succeeds.

This validates recovery after token expiry in a long-lived exporter process.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORTER_BIN = REPO_ROOT / "httpapi_exporter"
CONFIG_FILE = REPO_ROOT / "test" / "test_config.yml"
MOCK_SCRIPT = REPO_ROOT / "test" / "mock_veeam_server_v2.py"
MOCK_LOG = Path("/tmp/mock_veeam_server.log")
MOCK_STDOUT = Path("/tmp/mock_veeam_server.stdout.log")
EXPORTER_STDOUT = Path("/tmp/veeam_exporter.stdout.log")

MOCK_PORT = 9999


class TestFailure(RuntimeError):
    pass


def log(msg: str) -> None:
    print(f"[token-test] {msg}", flush=True)


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def http_get(url: str, timeout: float = 5.0) -> str:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def tail_lines(path: Path, n: int = 20) -> str:
    if not path.exists():
        return "<log file not found>"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-n:]) if lines else "<empty log>"


def wait_http(
    url: str,
    timeout_sec: int,
    label: str,
    proc: subprocess.Popen | None = None,
    log_path: Path | None = None,
    allow_http_error: bool = False,
) -> None:
    deadline = time.time() + timeout_sec
    last_error = ""
    while time.time() < deadline:
        if proc is not None and proc.poll() is not None:
            details = ""
            if log_path is not None:
                details = f"\n{label} log tail:\n{tail_lines(log_path)}"
            raise TestFailure(
                f"{label} exited early with code {proc.returncode}.{details}"
            )
        try:
            http_get(url, timeout=1.5)
            return
        except urllib.error.HTTPError as err:
            # For readiness checks we only need to know the process is serving HTTP.
            if allow_http_error:
                return
            last_error = f"HTTP Error {err.code}: {err.reason}"
            time.sleep(0.2)
        except Exception as err:  # noqa: BLE001
            last_error = str(err)
            time.sleep(0.2)
    raise TestFailure(f"Timeout waiting for {label} at {url}. last_error={last_error}")


def start_mock() -> subprocess.Popen:
    MOCK_STDOUT.write_text("", encoding="utf-8")
    stdout = MOCK_STDOUT.open("w", encoding="utf-8")

    proc = subprocess.Popen(  # noqa: S603
        [
            "python3",
            str(MOCK_SCRIPT),
            "--host",
            "127.0.0.1",
            "--port",
            str(MOCK_PORT),
            "--token-lifetime",
            "20",
            "--log-file",
            str(MOCK_LOG),
        ],
        cwd=str(REPO_ROOT),
        stdout=stdout,
        stderr=subprocess.STDOUT,
    )
    wait_http(
        f"http://127.0.0.1:{MOCK_PORT}/health",
        timeout_sec=10,
        label="mock server",
        proc=proc,
        log_path=MOCK_STDOUT,
        allow_http_error=False,
    )
    log("mock server is ready")
    return proc


def start_exporter(exporter_port: int) -> subprocess.Popen:
    EXPORTER_STDOUT.write_text("", encoding="utf-8")
    stdout = EXPORTER_STDOUT.open("w", encoding="utf-8")

    proc = subprocess.Popen(  # noqa: S603
        [
            str(EXPORTER_BIN),
            "-c",
            str(CONFIG_FILE),
            "--web.listen-address",
            f"127.0.0.1:{exporter_port}",
            "--log.level",
            "debug",
        ],
        cwd=str(REPO_ROOT),
        stdout=stdout,
        stderr=subprocess.STDOUT,
    )
    wait_http(
        f"http://127.0.0.1:{exporter_port}/metrics",
        timeout_sec=10,
        label="exporter",
        proc=proc,
        log_path=EXPORTER_STDOUT,
        allow_http_error=True,
    )
    log("exporter is ready")
    return proc


def scrape(tag: str, exporter_port: int) -> None:
    url = f"http://127.0.0.1:{exporter_port}/metrics?target=default"
    data = http_get(url, timeout=10)
    if "veeam_backup_test_up 1" not in data:
        raise TestFailure(f"{tag}: scrape failed, veeam_backup_test_up is not 1")
    log(f"{tag}: scrape ok")


def analyze_mock_log() -> None:
    if not MOCK_LOG.exists():
        raise TestFailure(f"mock log file not found: {MOCK_LOG}")

    text = MOCK_LOG.read_text(encoding="utf-8")
    password_grants = text.count("Grant type: password")
    refresh_grants = text.count("Grant type: refresh_token")
    unauthorized = text.count("RESULT: 401 Unauthorized")

    # Expected sequence for this timing:
    # 1st scrape -> unauthenticated ping 401, then password grant
    # 2nd scrape (8s later) -> token reuse
    # 3rd scrape (22s from first login, 20s lifetime) -> expired token 401,
    # then refresh_token grant
    if password_grants != 1:
        raise TestFailure(f"expected exactly 1 password grant, got {password_grants}")
    if refresh_grants != 1:
        raise TestFailure(f"expected exactly 1 refresh grant, got {refresh_grants}")
    if unauthorized < 2:
        raise TestFailure(
            f"expected at least 2 unauthorized responses (initial + expired token), got {unauthorized}"
        )

    log("log assertions passed")


def stop_proc(proc: subprocess.Popen | None, name: str) -> None:
    if proc is None:
        return
    if proc.poll() is not None:
        return

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        log(f"{name}: force kill")
        proc.kill()
        proc.wait(timeout=5)


def main() -> int:
    if not EXPORTER_BIN.exists():
        print(f"ERROR: exporter binary not found at {EXPORTER_BIN}", file=sys.stderr)
        return 2

    mock_proc: subprocess.Popen | None = None
    exporter_proc: subprocess.Popen | None = None

    try:
        log("starting mock server")
        mock_proc = start_mock()

        exporter_port = find_free_port()
        log(f"starting exporter on 127.0.0.1:{exporter_port}")
        exporter_proc = start_exporter(exporter_port)

        scrape("scrape-1", exporter_port)

        log("sleep 8s (token should still be reused)")
        time.sleep(8)
        scrape("scrape-2", exporter_port)

        log("sleep 14s (token should expire and force refresh on next scrape)")
        time.sleep(14)
        scrape("scrape-3", exporter_port)

        analyze_mock_log()
        log("PASS")
        return 0
    except (TestFailure, urllib.error.URLError) as err:
        print(f"FAIL: {err}", file=sys.stderr)
        print(f"mock stdout: {MOCK_STDOUT}", file=sys.stderr)
        print(f"exporter stdout: {EXPORTER_STDOUT}", file=sys.stderr)
        print(f"mock log: {MOCK_LOG}", file=sys.stderr)
        return 1
    finally:
        stop_proc(exporter_proc, "exporter")
        stop_proc(mock_proc, "mock")


if __name__ == "__main__":
    raise SystemExit(main())
