"""Turns raw data into a SHORT list of factual alerts. No betting advice, no predictions."""
import json, time, calendar
from .config import *
from .db import now
from .collector import price_history, _skip

def url_for(event_slug, slug):
    return f"https://polymarket.com/event/{event_slug or slug}"

def _cooldown_ok(con, kind, cid):
    r = con.execute("SELECT 1 FROM signals WHERE kind=? AND condition_id=? AND created_ts>?",
                    (kind, cid, now() - COOLDOWN_H * 3600)).fetchone()
    return r is None

def _ts(iso):
    try: return calendar.timegm(time.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S"))
    except Exception: return None

def _ends_within(iso, hours):
    t = _ts(iso or "")
    return t is not None and t < time.time() + hours * 3600

def _money(x):
    return f"${x/1e6:.2f}M" if x >= 1e6 else f"${x/1e3:.0f}K"

def _add(con, kind, cid, token_id, outcome, direction, ref_price, title, url, text, details):
    con.execute("""INSERT INTO signals(created_ts,kind,condition_id,token_id,outcome,direction,ref_price,
        title,url,text,details) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (now(), kind, cid, token_id, outcome, direction, ref_price, title, url, text, json.dumps(details)))

def whale_signals(con, since_ts):
    out = []
    rows = con.execute("""SELECT condition_id, token_id, side, outcome, title, slug, event_slug,
        SUM(usd) usd, SUM(size*price)/SUM(size) avgp, COUNT(*) n, MAX(ts) ts, MIN(trader) trader, proxy_wallet
        FROM trades WHERE ts>? AND usd>=? GROUP BY condition_id, token_id, side, proxy_wallet
        ORDER BY usd DESC""", (since_ts, WHALE_MIN_USD)).fetchall()
    for r in rows:
        if _skip(r["slug"]) or not _cooldown_ok(con, "whale", r["condition_id"]): continue
        if not (0.03 < r["avgp"] < 0.97): continue   # near-certain prices = position closing, not information
        m = con.execute("SELECT volume24 FROM markets WHERE condition_id=?", (r["condition_id"],)).fetchone()
        vol = f" | market 24h volume {_money(m['volume24'])}" if m and m["volume24"] else ""
        verb = "bought" if r["side"] == "BUY" else "sold"
        text = (f"🐋 Large trade: {_money(r['usd'])} of \"{r['outcome']}\" {verb} at {r['avgp']*100:.1f}¢"
                f" ({r['n']} fill{'s' if r['n']>1 else ''})\n{r['title']}{vol}\nWallet: {r['proxy_wallet'][:6]}…{r['proxy_wallet'][-4:]}")
        _add(con, "whale", r["condition_id"], r["token_id"], r["outcome"],
             "up" if r["side"] == "BUY" else "down", r["avgp"], r["title"], url_for(r["event_slug"], r["slug"]),
             text, {"usd": r["usd"], "wallet": r["proxy_wallet"], "fills": r["n"]})
        out.append(text)
    return out

def move_signals(con, candidates=60):
    out = []
    ms = con.execute("""SELECT * FROM markets WHERE closed=0 AND volume24>=? ORDER BY volume24 DESC LIMIT ?""",
                     (MOVE_MIN_VOL24, candidates)).fetchall()
    cutoff = now() - MOVE_WINDOW_MIN * 60
    for m in ms:
        if not _cooldown_ok(con, "move", m["condition_id"]): continue
        try: tok = json.loads(m["token_ids"])[0]; outcome = json.loads(m["outcomes"])[0]
        except Exception: continue
        hist = price_history(tok, "6h", 600); time.sleep(0.1)
        if len(hist) < 3: continue
        old = [p for t, p in hist if t <= cutoff] or [hist[0][1]]
        p_old, p_new = old[-1], hist[-1][1]
        d = (p_new - p_old) * 100
        # skip resolutions (price pinned to 0/1) and in-play markets ending within 6h: not information
        if abs(d) < MOVE_MIN_PP or not (0.03 < p_new < 0.97): continue
        if _ends_within(m["end_date"], 6): continue
        arrow = "📈" if d > 0 else "📉"
        text = (f"{arrow} Price move: \"{outcome}\" {p_old*100:.0f}¢ → {p_new*100:.0f}¢ ({d:+.0f} pts in ~{MOVE_WINDOW_MIN//60}h)\n"
                f"{m['question']} | 24h volume {_money(m['volume24'])}")
        _add(con, "move", m["condition_id"], tok, outcome, "up" if d > 0 else "down", p_new, m["question"],
             url_for(m["event_slug"], m["slug"]), text, {"from": p_old, "to": p_new})
        out.append(text)
    return out

def volume_and_new_signals(con):
    out = []
    ms = con.execute("SELECT * FROM markets WHERE closed=0 AND updated_ts>=?", (now() - 3600,)).fetchall()
    for m in ms:
        try: tok = json.loads(m["token_ids"])[0]; outcome = json.loads(m["outcomes"])[0]
        except Exception: continue
        snap = con.execute("SELECT price0 FROM snapshots WHERE condition_id=? ORDER BY ts DESC LIMIT 1",
                           (m["condition_id"],)).fetchone()
        p0 = snap["price0"] if snap else None
        age_h = (time.time() - calendar.timegm(time.strptime(m["created_at"][:19], "%Y-%m-%dT%H:%M:%S"))) / 3600 if m["created_at"] else 999
        price_s = f" | \"{outcome}\" at {p0*100:.0f}¢" if p0 is not None else ""
        if p0 is not None and not (0.02 < p0 < 0.98): continue   # practically decided markets
        if age_h <= HOT_NEW_MAX_AGE_H and not _ends_within(m["end_date"], 72) and m["volume24"] >= HOT_NEW_MIN_VOL24 and _cooldown_ok(con, "new", m["condition_id"]):
            text = f"🔥 New market heating up: {_money(m['volume24'])} traded in 24h, opened {age_h:.0f}h ago\n{m['question']}{price_s}"
            _add(con, "new", m["condition_id"], tok, outcome, "info", p0, m["question"], url_for(m["event_slug"], m["slug"]), text, {"age_h": age_h})
            out.append(text); continue
        avg = (m["volume1wk"] - m["volume24"]) / 6 if m["volume1wk"] else 0
        if age_h > 7 * 24 and avg > 0 and m["volume24"] >= VOLUME_SPIKE_MIN and m["volume24"] >= VOLUME_SPIKE_X * avg \
           and _cooldown_ok(con, "volume", m["condition_id"]):
            text = (f"📊 Volume spike: {_money(m['volume24'])} in 24h, {m['volume24']/avg:.1f}× its daily average this week\n"
                    f"{m['question']}{price_s}")
            _add(con, "volume", m["condition_id"], tok, outcome, "info", p0, m["question"], url_for(m["event_slug"], m["slug"]), text, {"x": m["volume24"]/avg})
            out.append(text)
    return out

def run(con, whale_since_ts):
    sigs = whale_signals(con, whale_since_ts) + move_signals(con) + volume_and_new_signals(con)
    con.commit()
    # keep the feed short: per-kind quotas, biggest first
    quota = {"whale": 3, "move": 2, "volume": 2, "new": 1}
    rows = con.execute("SELECT id, kind, details FROM signals WHERE created_ts>=? AND sent_premium=0", (now() - 120,)).fetchall()
    def score(r):
        d = json.loads(r["details"])
        return d.get("usd") or abs(d.get("to", 0) - d.get("from", 0)) or d.get("x") or 0
    drop = []
    for k, q in quota.items():
        ks = sorted([r for r in rows if r["kind"] == k], key=score, reverse=True)
        drop += [r["id"] for r in ks[q:]]
    con.executemany("DELETE FROM signals WHERE id=?", [(i,) for i in drop]); con.commit()
    return sigs
