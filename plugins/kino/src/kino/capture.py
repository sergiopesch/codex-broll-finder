from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets

CLICK_CONSENT_JS = r"""
(() => {
  const rx = /accept all|accept cookies|accepteren|alles accepteren|tout accepter|consentir|agree|akkoord|got it|allow all|j'accepte|i accept|^accept$|^agree$/i;
  function tryClick(root) {
    const els = root.querySelectorAll('button, a, [role=button], input[type=button], input[type=submit]');
    for (const el of els) {
      const t = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim();
      if (t && rx.test(t)) { el.click(); return t; }
    }
    return null;
  }
  let r = tryClick(document);
  if (r) return 'clicked:' + r;
  for (const el of document.querySelectorAll('*')) {
    if (el.shadowRoot) {
      const s = tryClick(el.shadowRoot);
      if (s) return 'clicked-shadow:' + s;
    }
  }
  return 'none';
})()
"""

REMOVE_OVERLAYS_JS = r"""
(() => { let n=0;
  for (const sel of ["iframe[id^='sp_message']","[id*='sp_message']","[class*='sp_message']",
                     "#onetrust-consent-sdk","#qc-cmp2-container","[id*='cmp-container']"]) {
    document.querySelectorAll(sel).forEach(e => { e.remove(); n++; });
  }
  document.querySelectorAll('div').forEach(e => {
    const s = getComputedStyle(e);
    if ((s.position==='fixed'||s.position==='sticky') && parseInt(s.zIndex||0) > 100000 &&
        e.offsetWidth >= innerWidth*0.5 && e.offsetHeight >= innerHeight*0.3) { e.remove(); n++; }
  });
  document.body.style.overflow='auto'; document.documentElement.style.overflow='auto';
  return 'removed:'+n;
})()
"""


def find_chrome(explicit: str | None = None) -> str:
    candidates = [
        explicit,
        os.environ.get("CHROME"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("chrome"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise FileNotFoundError("Chrome/Chromium not found. Set CHROME=/path/to/browser.")


async def capture_page(
    url: str,
    out: Path,
    *,
    chrome: str | None = None,
    wait: float = 7.0,
    port: int = 9777,
    width: int = 1920,
    height: int = 1080,
    scale: int = 1,
) -> None:
    browser = find_chrome(chrome)
    profile = tempfile.mkdtemp(prefix="kino-cdp-")
    proc = subprocess.Popen(
        [
            browser,
            "--headless=new",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "--hide-scrollbars",
            f"--window-size={width},{height}",
            "--disable-gpu",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        ws_url = _wait_for_debugger(port)
        async with websockets.connect(ws_url, max_size=50 * 1024 * 1024) as ws:
            contexts: list[int] = []
            mid = 0

            async def cmd(method: str, **params: object) -> dict[str, object]:
                nonlocal mid
                mid += 1
                await ws.send(json.dumps({"id": mid, "method": method, "params": params}))
                while True:
                    message = json.loads(await ws.recv())
                    if message.get("method") == "Runtime.executionContextCreated":
                        contexts.append(message["params"]["context"]["id"])
                    if message.get("id") == mid:
                        return message.get("result", {})

            await cmd("Page.enable")
            await cmd("Runtime.enable")
            await cmd("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=scale, mobile=False)
            await cmd("Page.navigate", url=url)
            await _drain_events(ws, contexts, wait)
            for context_id in [None, *contexts]:
                params: dict[str, object] = {"expression": CLICK_CONSENT_JS, "returnByValue": True}
                if context_id:
                    params["contextId"] = context_id
                await cmd("Runtime.evaluate", **params)
            await asyncio.sleep(2.0)
            await cmd("Runtime.evaluate", expression=REMOVE_OVERLAYS_JS, returnByValue=True)
            await asyncio.sleep(0.75)
            shot = await cmd("Page.captureScreenshot", format="png")
            out.write_bytes(base64.b64decode(str(shot["data"])))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)


def _wait_for_debugger(port: int) -> str:
    for _ in range(40):
        try:
            tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json"))
            pages = [tab for tab in tabs if tab.get("type") == "page"]
            if pages:
                return str(pages[0]["webSocketDebuggerUrl"])
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError("Chrome debugger did not become available")


async def _drain_events(ws: websockets.WebSocketClientProtocol, contexts: list[int], wait: float) -> None:
    end = time.time() + wait
    while time.time() < end:
        try:
            message = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.5))
        except asyncio.TimeoutError:
            continue
        if message.get("method") == "Runtime.executionContextCreated":
            contexts.append(message["params"]["context"]["id"])
