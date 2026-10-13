"""Provider Vavoo - stream via Deno Deploy (self-healing).

Storia dei provider testati (tutti bloccati dal CDN Vavoo con 403):
- Cloudflare Workers: IP datacenter bloccati
- Val.town: IP bloccati
- GitHub Actions: IP bloccati

Funzionanti:
- Deno Deploy  -> PROVIDER PRINCIPALE (1M richieste/mese, CPU solo su codice attivo)
- Azion        -> BACKUP (8 ore compute/mese)
"""

import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)

# Provider principale: Deno Deploy
WORKER_BASE = "https://vavoo-deno.simone11.deno.net"

# Backup (scommentare se Deno Deploy dovesse dare problemi):
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
        "headers": {},  # tutto gestito dall'Edge Function
        "extra_vlcopts": [],
        "proxy": "direct",
        "proxy_required": False,
    }
