"""Proxy provider helpers for the settings UI: a catalog of known providers and a live proxy test.

The stored setting remains a single URL (`throttle.proxy`, read by `ytdl.yt_proxy`); the catalog
only tells the frontend how to build that URL for supported providers. The test endpoint fetches
one channel RSS feed through the given URL so the user sees whether the proxy actually works
before saving it.
"""
from __future__ import annotations

import time
import urllib.parse as up

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import log_yt_request

router = APIRouter()

FEED_CHANNEL = "UCBR8-60-B28hp2BmLPdYCiA"  # YouTube's own channel: stable, always serves RSS
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"

PROXY_PROVIDERS: list[dict] = [
    {
        "id": "pia",
        "label": "PIA (SOCKS5)",
        "hint": "In the PIA dashboard enable the SOCKS5 proxy and generate proxy credentials "
                "(username + password), then enter them here.",
        "scheme": "socks5",
        "port": 1080,
        "host": "proxy-{region}.privateinternetaccess.com",
        "regions": [
            {"id": "nl", "name": "Netherlands"},
            {"id": "switzerland", "name": "Switzerland"},
            {"id": "sweden", "name": "Sweden"},
            {"id": "germany", "name": "Germany"},
            {"id": "france", "name": "France"},
            {"id": "uk-london", "name": "UK, London"},
            {"id": "us-texas", "name": "US, Texas"},
            {"id": "us-california", "name": "US, California"},
            {"id": "ca-toronto", "name": "Canada, Toronto"},
            {"id": "au-sydney", "name": "Australia, Sydney"},
        ],
    },
    {
        "id": "mullvad",
        "label": "Mullvad (SOCKS5)",
        "hint": "The password is your 16-digit Mullvad account number; the username can be anything.",
        "scheme": "socks5",
        "port": 1080,
        "host": "{region}-wg-socks5.mullvad.net",
        "regions": [
            {"id": "se-sto", "name": "Sweden, Stockholm"},
            {"id": "nl-ams", "name": "Netherlands, Amsterdam"},
            {"id": "de-fra", "name": "Germany, Frankfurt"},
            {"id": "us-nyc", "name": "US, New York"},
        ],
    },
    {
        "id": "local",
        "label": "Local VPN container",
        "hint": "A proxy on your own network, e.g. the gluetun container with HTTPPROXY=on (port 8000), "
                "or an SSH tunnel (ssh -D 1080).",
        "schemes": ["http", "socks5"],
        "default_port": 8000,
    },
]

_PROXY_SCHEMES = ("http", "https", "socks4", "socks5", "socks5h")


@router.get("/proxy/providers")
def proxy_providers() -> dict:
    return {"providers": PROXY_PROVIDERS}


class ProxyTestBody(BaseModel):
    url: str = ""


def _err_hint(e: Exception) -> str:
    if isinstance(e, httpx.ProxyError):
        return "The proxy refused the connection — check the username/password and the address."
    if isinstance(e, (httpx.ConnectError, httpx.ConnectTimeout)):
        return "Could not reach the proxy — check the host and port (and that it is reachable from this server)."
    if isinstance(e, httpx.ReadTimeout):
        return "The proxy accepted the connection but nothing came back in time."
    return ""


@router.post("/proxy/test")
def proxy_test(body: ProxyTestBody) -> dict:
    url = (body.url or "").strip()
    if "://" not in url:
        raise HTTPException(400, "not a proxy URL — expected http(s):// or socks5://host:port")
    scheme = up.urlparse(url).scheme
    if scheme not in _PROXY_SCHEMES:
        raise HTTPException(400, f"unsupported scheme {scheme!r} — use http, https, socks4 or socks5")
    t = time.monotonic()
    try:
        r = httpx.get(f"https://www.youtube.com/feeds/videos.xml?channel_id={FEED_CHANNEL}",
                      headers={"User-Agent": UA}, timeout=20, follow_redirects=True, proxy=url)
    except httpx.HTTPError as e:
        log_yt_request("proxy_test", "user", False, f"proxy test: {type(e).__name__}: {str(e)[:200]}")
        return {"ok": False, "error": str(e)[:300], "hint": _err_hint(e)}
    ms = time.monotonic() - t
    log_yt_request("proxy_test", "user", r.status_code == 200, f"proxy test: HTTP {r.status_code} ({ms:.1f}s)")
    if r.status_code == 200:
        return {"ok": True, "ms": int(ms * 1000), "detail": "YouTube served a channel feed through this proxy."}
    if r.status_code in (403, 429):
        return {"ok": False, "error": f"YouTube answered HTTP {r.status_code} through the proxy.",
                "hint": "The proxy works, but YouTube is rate-limiting this exit IP. Pick another region."}
    return {"ok": False, "error": f"YouTube answered HTTP {r.status_code} through the proxy.",
            "hint": "The proxy connection worked; check whether the region serves YouTube."}
