"""
Provider Vavoo - stream via Worker Cloudflare self-healing.

Il Worker risolve l'URL fresco a ogni richiesta manifest.
"""

import logging

logger = logging.getLogger(__name__)

# IL TUO WORKER VAVOO
WORKER_BASE = "https://vavoo-stream.simone-scorrano-2011.workers.dev"


def resolve(channel, stream):
    """URL stabile: il Worker self-healing risolve Vavoo al volo."""
    query = stream.get("query") or channel.get("name", "")
    
    # URL encode della query per sicurezza
    from urllib.parse import quote
    encoded_query = quote(query)
    
    stable_url = f"{WORKER_BASE}/live?ch={encoded_query}"

    return {
        "url": stable_url,
        "provider": "Vavoo",
        "quality": "HD",
        "headers": {},  # Il worker gestisce tutto
        "extra_vlcopts": [],
        "proxy": "direct",
        "proxy_required": False,
    }
