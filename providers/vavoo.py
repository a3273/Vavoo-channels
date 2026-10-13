"""Provider Vavoo - stream via Val.town Edge Function (self-healing)."""

import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)

# PROVIDER PRINCIPALE: Val.town
WORKER_BASE = "https://simone11.val.run/vavoo-stream"

# BACKUP: Azion (se Val.town va in limitazione)
# WORKER_BASE = "https://vavoo-stream.azion.app"


def resolve(channel, stream):
    """URL stabile: l'Edge Function risolve il canale Vavoo a ogni richiesta manifest."""
    query = stream.get("query") or channel.get("name", "")
    if not query:
        raise ValueError("Vavoo: nessuna query/canale configurato")

    encoded = quote(query)
    stable_url = f"{WORKER_BASE}/live?ch={encoded}"

    logger.info("Vavoo: %s -> %s", query, stable_url)

    return {
        "url": stable_url,
        "provider": "Vavoo",
        "quality": "HD",
        "headers": {},
        "extra_vlcopts": [],
        "proxy": "direct",
        "proxy_required": False,
    }
