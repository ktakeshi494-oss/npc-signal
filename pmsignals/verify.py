"""Auto-grades every signal 7 days later, in public. Grading describes what the price did;
it is NOT a profit claim."""
import json, time
from .config import VERIFY_AFTER_DAYS
from .collector import market_by_condition
from .db import now

def _token_price(m, token_id):
    toks = json.loads(m.get("clobTokenIds") or "[]"); prices = json.loads(m.get("outcomePrices") or "[]")
    if token_id in toks and len(prices) == len(toks):
        return float(prices[toks.index(token_id)])
    return None

def verdict(direction, ref, later, resolved):
    if direction == "info" or ref is None or later is None:
        return "info: price now {:.0f}¢".format(later * 100) if later is not None else "info"
    d = (later - ref) * 100 * (1 if direction == "up" else -1)
    tag = "resolved, " if resolved else ""
    if d >= 2:  return f"{tag}price continued in signal direction ({d:+.0f} pts)"
    if d <= -2: return f"{tag}price reversed ({d:+.0f} pts)"
    return f"{tag}flat ({d:+.0f} pts)"

def run(con, force_older_than_s=None):
    age = force_older_than_s if force_older_than_s is not None else VERIFY_AFTER_DAYS * 86400
    rows = con.execute("SELECT * FROM signals WHERE verify_ts IS NULL AND created_ts<=?", (now() - age,)).fetchall()
    n = 0
    for s in rows:
        m = market_by_condition(s["condition_id"]); time.sleep(0.1)
        if not m: continue
        p = _token_price(m, s["token_id"])
        resolved = "yes" if m.get("closed") else "no"
        con.execute("UPDATE signals SET verify_ts=?, verify_price=?, verify_resolved=?, verdict=? WHERE id=?",
                    (now(), p, resolved, verdict(s["direction"], s["ref_price"], p, m.get("closed")), s["id"]))
        n += 1
    con.commit()
    return n
