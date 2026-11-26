"""Collects public Polymarket data via the documented, unauthenticated Gamma + Data API v2.
Polite: few hundred requests per run, far below published limits; honours Retry-After.
We never scrape polymarket.com pages."""
import json, time
from .config import GAMMA, DATA, TOP_MARKETS, WHALE_MIN_USD, SKIP_SLUG_PATTERNS
from .http import get_json
from .db import now

def _skip(slug):
    s = (slug or "").lower()
    return any(p in s for p in SKIP_SLUG_PATTERNS)

def _upsert_market(con, m, ts):
    ev = (m.get("events") or [{}])[0]
    con.execute("""INSERT INTO markets VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(condition_id) DO UPDATE SET question=excluded.question, closed=excluded.closed,
      volume24=excluded.volume24, volume1wk=excluded.volume1wk, liquidity=excluded.liquidity,
      outcomes=excluded.outcomes, token_ids=excluded.token_ids, updated_ts=excluded.updated_ts""",
      (m["conditionId"], m.get("id"), m.get("question"), m.get("slug"), ev.get("slug"),
       m.get("outcomes"), m.get("clobTokenIds"), m.get("createdAt"), m.get("endDate"),
       int(bool(m.get("closed"))), float(m.get("volume24hr") or 0), float(m.get("volume1wk") or 0),
       float(m.get("liquidityNum") or 0), ts))

def collect_markets(con):
    ts, n = now(), 0
    seen = set()
    for order, limit_total in (("volume24hr", TOP_MARKETS), ("createdAt", 200)):
        for off in range(0, limit_total, 100):
            rows = get_json(f"{GAMMA}/markets", {"limit": 100, "offset": off, "active": "true",
                            "closed": "false", "order": order, "ascending": "false"})
            if not rows: break
            for m in rows:
                if not m.get("conditionId") or _skip(m.get("slug")) or m["conditionId"] in seen: continue
                seen.add(m["conditionId"]); _upsert_market(con, m, ts); n += 1
                try: p0 = float(json.loads(m.get("outcomePrices") or "[]")[0])
                except (ValueError, IndexError): p0 = None
                con.execute("INSERT OR IGNORE INTO snapshots VALUES(?,?,?,?)",
                            (ts, m["conditionId"], p0, float(m.get("volume24hr") or 0)))
            time.sleep(0.2)
    con.commit()
    return n

def collect_whale_trades(con, max_pages=10):
    """Global trade feed filtered server-side to trades >= WHALE_MIN_USD cash."""
    last = int((con.execute("SELECT v FROM meta WHERE k='last_trade_ts'").fetchone() or ["0"])[0])
    params = {"limit": 500, "filter_type": "CASH", "filter_amount": int(WHALE_MIN_USD)}
    newest, added, cursor = last, 0, None
    for _ in range(max_pages):
        p = dict(params, cursor=cursor) if cursor else params
        d = get_json(f"{DATA}/v2/trades", p)
        rows = d.get("data") or []
        for t in rows:
            usd = float(t["size"]) * float(t["price"])
            newest = max(newest, int(t["timestamp"]))
            cur = con.execute("INSERT OR IGNORE INTO trades VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (t["transaction_hash"], t["token_id"], t["proxy_wallet"], t["side"], t.get("outcome"),
                 t["size"], t["price"], usd, t["timestamp"], t["condition_id"], t.get("title"),
                 t.get("slug"), t.get("event_slug"), t.get("name") or t.get("pseudonym")))
            added += cur.rowcount
        cursor = (d.get("pagination") or {}).get("next_cursor")
        if not rows or not cursor or int(rows[-1]["timestamp"]) <= last: break
        time.sleep(0.2)
    con.execute("INSERT OR REPLACE INTO meta VALUES('last_trade_ts',?)", (str(newest),))
    con.commit()
    return added

def price_history(token_id, interval="6h", bucket=600):
    d = get_json(f"{DATA}/v2/prices-history", {"token_id": token_id, "interval": interval, "bucket_seconds": bucket})
    return [(int(x["timestamp"]), float(x["price"])) for x in (d.get("data") or [])]

def market_by_condition(cid):
    rows = get_json(f"{GAMMA}/markets", {"condition_ids": cid})
    if not rows:
        rows = get_json(f"{GAMMA}/markets", {"condition_ids": cid, "closed": "true"})
    return rows[0] if rows else None
