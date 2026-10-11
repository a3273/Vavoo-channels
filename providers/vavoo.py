"""
Provider Vavoo - API ufficiale mediahubmx (senza proxy, diretto).

Stream instradati attraverso Cloudflare Worker per URL corti.
"""

import time
import logging
from urllib.parse import quote

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

LANGUAGE = "de"
REGION = "US"
BASE_SITES = ["https://vavoo.to", "https://kool.to"]
PING_URL = "https://www.vavoo.tv/api/app/ping"
SEPARATORS = ["➾", "⟾", "->", "→", "»", "›"]

# IL TUO WORKER CLOUDFLARE
WORKER_BASE = "https://vavoo-channels.simone-scorrano-2011.workers.dev"

_catalog_cache = None
_sig = {"value": None, "ts": 0}


def _ping_sig():
    """Ottiene addonSig, rinnovandola se scaduta (TTL interno 240s)."""
    now = time.time()

    if _sig["value"] and now - _sig["ts"] < 240:
        return _sig["value"]

    ts = int(now * 1000)
    payload = {
        "reason": "app-focus",
        "locale": LANGUAGE,
        "theme": "dark",
        "metadata": {
            "device": {"type": "desktop", "uniqueId": f"node-{ts}"},
            "os": {"name": "linux", "version": "Linux", "abis": ["x64"], "host": "node"},
            "app": {"platform": "electron"},
            "version": {"package": "tv.vavoo.app", "binary": "3.1.8", "js": "3.1.8"},
        },
        "appFocusTime": 0,
        "playerActive": False,
        "playDuration": 0,
        "devMode": False,
        "hasAddon": True,
        "castConnected": False,
        "package": "tv.vavoo.app",
        "version": "3.1.8",
        "process": "app",
        "firstAppStart": ts,
        "lastAppStart": ts,
        "ipLocation": None,
        "adblockEnabled": True,
        "proxy": {"supported": ["ss"], "engine": "Mu", "enabled": False, "autoServer": True},
        "iap": {"supported": False},
    }

    r = requests.post(PING_URL, json=payload, timeout=30, verify=False)
    r.raise_for_status()
    sig = r.json().get("addonSig")

    if not sig:
        raise RuntimeError("addonSig mancante nella risposta ping")

    _sig["value"] = sig
    _sig["ts"] = now
    logger.info("Vavoo: nuova addonSig ottenuta")
    return sig


def _api_headers():
    return {
        "content-type": "application/json; charset=utf-8",
        "mediahubmx-signature": _ping_sig(),
        "user-agent": "MediaHubMX/2",
        "accept": "*/*",
        "Accept-Language": LANGUAGE,
    }


def _extract_country(group):
    group = (group or "").strip()
    if not group:
        return "default"
    for sep in SEPARATORS:
        if sep in group:
            return group.split(sep)[0].strip() or "default"
    return group


def load_catalog():
    """Scarica il catalogo completo (una sola volta per run)."""
    global _catalog_cache

    if _catalog_cache is not None:
        return _catalog_cache

    channels = []

    for base in BASE_SITES:
        cursor = None
        try:
            while True:
                body = {
                    "language": LANGUAGE, "region": REGION,
                    "catalogId": "iptv", "id": "iptv",
                    "adult": False, "search": "", "sort": "",
                    "filter": {}, "cursor": cursor,
                    "clientVersion": "3.0.2",
                }
                r = requests.post(
                    f"{base}/mediahubmx-catalog.json",
                    headers=_api_headers(), json=body,
                    timeout=30, verify=False,
                )
                r.raise_for_status()
                data = r.json()

                for item in data.get("items", []):
                    if item.get("type") == "iptv" and item.get("url"):
                        channels.append({
                            "name": item.get("name", "Unknown"),
                            "url": item["url"],
                            "logo": item.get("logo", ""),
                            "country": _extract_country(item.get("group", "")),
                        })

                cursor = data.get("nextCursor")
                if not cursor:
                    break

            if channels:
                logger.info("Vavoo: catalogo caricato (%d canali)", len(channels))
                _catalog_cache = channels
                return channels

        except Exception as e:
            logger.warning("Vavoo: catalogo fallito da %s: %s", base, e)

    raise RuntimeError("Vavoo: catalogo non caricato da nessun mirror")


def _find_in_catalog(query, catalog):
    """Cerca un canale per query (solo Italia)."""
    ita = [c for c in catalog if c["country"].lower() == "italy"]
    q = query.lower()

    # 1. Match esatto
    for ch in ita:
        if ch["name"].lower() == q:
            return ch
    # 2. Contenimento
    for ch in ita:
        n = ch["name"].lower()
        if q in n or n in q:
            return ch
    # 3. Parole
    words = set(q.split())
    best, best_score = None, 0
    for ch in ita:
        score = len(words & set(ch["name"].lower().split()))
        if score > best_score:
            best, best_score = ch, score
    if best and best_score >= max(1, len(words) - 1):
        return best
    return None


def _resolve_url(channel_url):
    body = {
        "language": LANGUAGE, "region": REGION,
        "url": channel_url, "clientVersion": "3.0.2",
    }
    for base in BASE_SITES:
        try:
            r = requests.post(
                f"{base}/mediahubmx-resolve.json",
                headers=_api_headers(), json=body,
                timeout=30, verify=False,
            )
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list) and data and data[0].get("url"):
                return data[0]["url"]
            if isinstance(data, dict):
                return data.get("url") or data.get("streamUrl")
        except Exception as e:
            logger.warning("Vavoo: resolve fallito da %s: %s", base, e)
    return None


def get_stream(query):
    """Dato una query, trova il canale e restituisce l'URL diretto."""
    catalog = load_catalog()
    match = _find_in_catalog(query, catalog)
    if not match:
        raise ValueError(f"Vavoo: canale '{query}' non trovato (Italia)")

    url = _resolve_url(match["url"])
    if not url:
        raise RuntimeError(f"Vavoo: resolve fallito per '{match['name']}'")

    return {
        "url": url,
        "matched_name": match["name"],
        "logo": match.get("logo", ""),
    }


def resolve(channel, stream):
    """Interfaccia richiesta da generate_m3u.py."""
    query = stream.get("query") or channel.get("name", "")
    result = get_stream(query)

    # URL corto via Worker
    worker_url = f"{WORKER_BASE}/?u={quote(result['url'], safe='')}"

    return {
        "url": worker_url,
        "provider": "Vavoo",
        "quality": "HD",
        "headers": {},  # Il worker gestisce tutto
        "extra_vlcopts": [],
        "proxy": "direct",
        "proxy_required": False,
    }
