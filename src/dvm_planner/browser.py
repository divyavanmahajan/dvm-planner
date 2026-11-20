"""Launch Edge with remote debugging and capture the Planner bearer token via CDP."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import httpx
from websockets.sync.client import connect

PLANNER_HOME = "https://planner.cloud.microsoft/ui/web/"
API_HOST = "api.planner.svc.cloud.microsoft"
OUTLOOK_HOST = "outlook.cloud.microsoft"
OUTLOOK_CALENDAR = f"https://{OUTLOOK_HOST}/calendar/view/week"
DEFAULT_PORT = 19222
DEFAULT_PROFILE = Path.home() / ".dvm-planner" / "edge-profile"

_EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/microsoft-edge",
]


def find_edge() -> str:
    found = shutil.which("msedge") or shutil.which("microsoft-edge")
    if found:
        return found
    for c in _EDGE_CANDIDATES:
        if os.path.exists(c):
            return c
    raise FileNotFoundError("Microsoft Edge not found; pass --edge-path")


def cdp_alive(port: int) -> bool:
    try:
        return httpx.get(f"http://127.0.0.1:{port}/json/version", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def launch_edge(port: int = DEFAULT_PORT, profile: Path = DEFAULT_PROFILE,
                edge_path: str | None = None, url: str = PLANNER_HOME) -> bool:
    """Start Edge with CDP enabled. Returns False if a browser already listens on the port."""
    if cdp_alive(port):
        return False
    profile.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [edge_path or find_edge(), f"--remote-debugging-port={port}",
         f"--user-data-dir={profile}", "--remote-allow-origins=*", "--no-first-run", url],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        if cdp_alive(port):
            return True
        time.sleep(0.5)
    raise TimeoutError(f"Edge did not expose CDP on port {port}")


class Cdp:
    """Minimal synchronous CDP session over a page websocket."""

    def __init__(self, ws_url: str):
        self.ws = connect(ws_url, max_size=None)
        self._id = 0

    def call(self, method: str, **params):
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, "method": method, "params": params}))
        return self._id

    def events(self, timeout: float):
        """Yield CDP messages until `timeout` seconds have elapsed."""
        end = time.monotonic() + timeout
        while (left := end - time.monotonic()) > 0:
            try:
                yield json.loads(self.ws.recv(timeout=min(left, 1)))
            except TimeoutError:
                continue

    def close(self):
        self.ws.close()


def _planner_tab(port: int) -> dict:
    base = f"http://127.0.0.1:{port}"
    for t in httpx.get(f"{base}/json/list").json():
        if t["type"] == "page" and "planner.cloud.microsoft" in t["url"]:
            return t
    return httpx.put(f"{base}/json/new?{PLANNER_HOME}").json()


def capture_outlook(port: int = DEFAULT_PORT, timeout: float = 60) -> tuple[str, str]:
    """Reload an Outlook calendar tab (opening one if needed); return (Authorization, X-AnchorMailbox)
    as sent by Outlook on the web to its owa/service.svc endpoint."""
    base = f"http://127.0.0.1:{port}"
    tab = next((t for t in httpx.get(f"{base}/json/list").json()
                if t["type"] == "page" and OUTLOOK_HOST in t["url"]), None)
    tab = tab or httpx.put(f"{base}/json/new?{OUTLOOK_CALENDAR}").json()
    cdp = Cdp(tab["webSocketDebuggerUrl"])
    try:
        cdp.call("Network.enable")
        cdp.call("Page.reload")
        for msg in cdp.events(timeout):
            if msg.get("method") != "Network.requestWillBeSent":
                continue
            req = msg["params"]["request"]
            if "/owa/service.svc" not in req["url"]:
                continue
            h = {k.lower(): v for k, v in req["headers"].items()}
            if "authorization" in h and "x-anchormailbox" in h:
                return h["authorization"], h["x-anchormailbox"]
    finally:
        cdp.close()
    raise TimeoutError("No Outlook token seen. Is the browser signed in to Outlook on the web?")


def capture_tokens(port: int = DEFAULT_PORT, hosts: tuple[str, ...] = (API_HOST,),
                   timeout: float = 60) -> dict[str, str]:
    """Reload the Planner tab and return the Authorization header seen for each host in `hosts`."""
    tab = _planner_tab(port)
    cdp = Cdp(tab["webSocketDebuggerUrl"])
    found: dict[str, str] = {}
    try:
        cdp.call("Network.enable")
        cdp.call("Page.reload")
        for msg in cdp.events(timeout):
            if msg.get("method") != "Network.requestWillBeSent":
                continue
            req = msg["params"]["request"]
            host = req["url"].split("/")[2] if "//" in req["url"] else ""
            if host not in hosts or host in found:
                continue
            for k, v in req["headers"].items():
                if k.lower() == "authorization":
                    found[host] = v
            if len(found) == len(hosts):
                return found
    finally:
        cdp.close()
    missing = [h for h in hosts if h not in found]
    raise TimeoutError(f"No token seen for {missing}. Is the browser signed in to Planner?")


def capture_token(port: int = DEFAULT_PORT, timeout: float = 60) -> str:
    """Return the Authorization header sent to the Planner API."""
    return capture_tokens(port, (API_HOST,), timeout)[API_HOST]
