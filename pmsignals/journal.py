"""Exports the public, append-only signal journal (JSON + static HTML) for GitHub Pages."""
import json, html, datetime as dt
from .config import SITE_DIR, BRAND, FREE_DELAY_MIN
from .db import now

def _row(s):
    return {k: s[k] for k in ("id", "created_ts", "kind", "title", "url", "outcome", "direction",
                              "ref_price", "verify_ts", "verify_price", "verify_resolved", "verdict",
                              "verify24_ts", "verify24_price", "verify24_resolved", "verdict24", "text")}

def _cell24(r):
    if r["verdict24"]: return r["verdict24"]
    if r["direction"] == "info": return "n/a (no direction)"
    if r["created_ts"] > now() - 24 * 3600: return "pending (24h check, only if the market has resolved)"
    return "n/a (market still open at 24h; see 7-day check)"

def export(con, min_age_s=None):
    """Only signals older than the free delay are published (premium gets them first)."""
    min_age_s = FREE_DELAY_MIN * 60 if min_age_s is None else min_age_s
    rows = [_row(s) for s in con.execute("SELECT * FROM signals WHERE created_ts<=? ORDER BY id DESC LIMIT 2000",
                                          (now() - min_age_s,))]
    SITE_DIR.mkdir(exist_ok=True)
    (SITE_DIR / "journal.json").write_text(json.dumps({"generated": now(), "signals": rows}, indent=1))
    def stats(col):
        g = [r for r in rows if r[col] and r["direction"] != "info"]
        c = sum("continued" in r[col] or r[col].startswith("won") for r in g)
        v = sum("reversed" in r[col] or r[col].startswith("lost") for r in g)
        f = len(g) - c - v
        pct = lambda x: f"{x * 100 / len(g):.0f}%" if g else "n/a"
        return g, c, v, f, pct
    g24, w24, l24, _, p24 = stats("verdict24")
    g7, c7, v7, f7, p7 = stats("verdict")
    dirn = [r for r in rows if r["direction"] != "info"]
    old24 = [r for r in dirn if r["created_ts"] <= now() - 24 * 3600]
    stats24 = (f"Resolved within 24h: {len(g24)} of {len(old24)} directional signals older than 24h · "
               f"{w24} won ({p24(w24)}) · {l24} lost ({p24(l24)}). "
               "The rest were still open at 24h and are covered by the 7-day check.")
    stats7 = (f"7-day check: {len(g7)} directional signals graded · {c7} continued ({p7(c7)}) · "
              f"{v7} reversed ({p7(v7)}) · {f7} flat ({p7(f7)})")
    trs = []
    for r in rows:
        t = dt.datetime.utcfromtimestamp(r["created_ts"]).strftime("%Y-%m-%d %H:%M")
        trs.append(f"<tr><td>{t}</td><td>{r['kind']}</td><td><a href='{html.escape(r['url'])}' rel='nofollow noopener'>"
                   f"{html.escape(r['title'] or '')}</a><br><small>{html.escape(r['text'].splitlines()[0])}</small></td>"
                   f"<td>{'' if r['ref_price'] is None else f'{r['ref_price']*100:.1f}¢'}</td>"
                   f"<td>{html.escape(_cell24(r))}</td>"
                   f"<td>{html.escape(r['verdict'] or 'pending (graded after 7 days)')}</td></tr>")
    page = (SITE_DIR / "journal.template.html").read_text()
    page = page.replace("{{ROWS}}", "\n".join(trs) or "<tr><td colspan=6>No signals yet.</td></tr>")
    page = page.replace("{{STATS}}", f"{len(rows)} signals published<br>{stats24}<br>{stats7}<br>"
                        "<small>Percentages describe what the market did after each alert (won = it settled in the alert direction). They are not a trading result or advice.</small>")
    page = page.replace("{{UPDATED}}", dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")).replace("{{BRAND}}", BRAND)
    (SITE_DIR / "journal.html").write_text(page)
    return len(rows)
