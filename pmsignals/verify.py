"""Auto-grades every signal 7 days later (by price), plus a 24h check only for markets already resolved, in public. Grading describes what the price did;
it is NOT a profit claim."""
import json, re, time, datetime as dt
from .config import VERIFY_AFTER_DAYS, VERIFY24_AFTER_HOURS, VERIFY24_WINDOW_H
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

def _grade(con, age):
    """7-day grading: signals older than `age` seconds, by price (unchanged behaviour)."""
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

def run(con, force_older_than_s=None):
    """7-day grading (unchanged) plus the 24h resolved-only check. Returns the number of 7-day grades."""
    age = force_older_than_s if force_older_than_s is not None else VERIFY_AFTER_DAYS * 86400
    n = _grade(con, age)
    run24(con)
    return n

def _closed_ts(m):
    """Gamma closedTime like '2026-11-26 11:04:29.14304+00' -> epoch seconds (UTC), or None."""
    mm = re.match(r"(\d{4}-\d\d-\d\d)[ T](\d\d:\d\d:\d\d)", str(m.get("closedTime") or ""))
    if not mm: return None
    return int(dt.datetime.strptime(f"{mm[1]} {mm[2]}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp())

def verdict24(direction, final_price):
    """Resolved-only: did the market settle in the signal's direction? None if not final yet."""
    if final_price is None: return None
    won = (final_price >= 0.99) if direction == "up" else (final_price <= 0.01)
    lost = (final_price <= 0.01) if direction == "up" else (final_price >= 0.99)
    if won:  return f"won: market resolved in signal direction (final {final_price*100:.0f}¢)"
    if lost: return f"lost: market resolved against signal direction (final {final_price*100:.0f}¢)"
    return None  # closed but not a clean 100/0 settlement: leave to the 7-day check

def run24(con, force_older_than_s=None):
    """24h check, ONLY for markets that already resolved within 24h of the signal. Open markets are skipped
    (no price-based 24h grade); they are graded by the 7-day check. Directional signals only."""
    age = force_older_than_s if force_older_than_s is not None else VERIFY24_AFTER_HOURS * 3600
    t = now()
    # look only in the 24h..(24h+WINDOW) age band so open markets are not re-queried for days
    rows = con.execute("SELECT * FROM signals WHERE verify24_ts IS NULL AND direction!='info' AND created_ts<=? AND created_ts>?",
                       (t - age, t - age - VERIFY24_WINDOW_H * 3600)).fetchall()
    n = 0
    for s in rows:
        m = market_by_condition(s["condition_id"]); time.sleep(0.1)
        if not m or not m.get("closed"): continue
        ct = _closed_ts(m)
        if ct is not None and ct > s["created_ts"] + 24 * 3600: continue  # resolved later than 24h
        p = _token_price(m, s["token_id"])
        v = verdict24(s["direction"], p)
        if not v: continue
        con.execute("UPDATE signals SET verify24_ts=?, verify24_price=?, verify24_resolved='yes', verdict24=? WHERE id=?",
                    (t, p, v, s["id"]))
        n += 1
    con.commit()
    return n
