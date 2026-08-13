"""FIX (audit) — every endpoint was previously wide open: no auth at
all, on approve/reject/delete/regenerate/restore-db, everything. For
pure localhost use that's a reasonable default (matches "don't
introduce unnecessary enterprise authentication" for local mode), but
the moment this API is reachable from anywhere else — a home server, a
tunnel, a VPS — that's a real gap, not a stylistic one.

This is deliberately NOT a user-accounts/OAuth/JWT system — that would
be exactly the "unnecessary enterprise authentication complexity" the
project brief warns against for what is fundamentally a single-operator
tool. Instead: one shared secret, set once in .env, checked via a
header.

Local/dev mode (API_ACCESS_TOKEN unset in .env): unchanged behavior,
no auth required, exactly as before.

Protected mode (API_ACCESS_TOKEN set): every mutating/destructive
endpoint requires an `X-API-Key` header matching it. The dashboard
sends this automatically when HOLY_MONTH_API_KEY is set in ITS
environment (see dashboard/api_client.py).
"""

import hmac

from fastapi import Header, HTTPException

from holy_month.config import Config


def verify_api_key(x_api_key: str = Header(default=None)):
    if not Config.API_ACCESS_TOKEN:
        return  # local/dev mode — no token configured, nothing to check
    if not x_api_key or not hmac.compare_digest(x_api_key, Config.API_ACCESS_TOKEN):
        raise HTTPException(401, "Missing or invalid X-API-Key header.")
