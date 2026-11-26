"""Exports the public, append-only signal journal (JSON + static HTML) for GitHub Pages."""
import json, html, datetime as dt
from .config import SITE_DIR, BRAND, FREE_DELAY_MIN
from .db import now

def _row(s):
    return {k: s[k] for k in ("id", "created_ts", "kind", "title", "url", "outcome", "direction",
                              "ref_price", "verify_ts", "verify_price", "verify_resolved", "verdict", "text")}

def export(con, min_age_s=None):
    """Only signals older than the free delay are published (premium gets them first)."""
    min_age_s = FREE_DELAY_MIN * 60 if min_age_s is None else min_age_s
    rows = [_row(s) for s in con.execute("SELECT * FROM signals WHERE created_ts<=? ORDER BY id DESC LIMIT 2000",
                                          (now() - min_age_s,))]
    SITE_DIR.mkdir(exist_ok=True)
    (SITE_DIR / "journal.json").write_text(json.dumps({"generated": now(), "signals": rows}, indent=1))
    graded = [r for r in rows if r["verdict"] and r["direction"] != "info"]
    cont = sum("continued" in r["verdict"] for r in graded); rev = sum("reversed" in r["verdict"] for r in graded)
    trs = []
    for r in rows:
        t = dt.datetime.utcfromtimestamp(r["created_ts"]).strftime("%Y-%m-%d %H:%M")
        trs.append(f"<tr><td>{t}</td><td>{r['kind']}</td><td><a href='{html.escape(r['url'])}' rel='nofollow noopener'>"
                   f"{html.escape(r['title'] or '')}</a><br><small>{html.escape(r['text'].splitlines()[0])}</small></td>"
                   f"<td>{'' if r['ref_price'] is None else f'{r['ref_price']*100:.1f}¢'}</td>"
                   f"<td>{html.escape(r['verdict'] or 'pending (graded after 7 days)')}</td></tr>")
    page = (SITE_DIR / "journal.template.html").read_text()
    page = page.replace("{{ROWS}}", "\n".join(trs) or "<tr><td colspan=5>No signals yet.</td></tr>")
    page = page.replace("{{STATS}}", f"{len(rows)} signals published · {len(graded)} directional signals graded · "
                        f"{cont} continued · {rev} reversed · {len(graded)-cont-rev} flat")
    page = page.replace("{{UPDATED}}", dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")).replace("{{BRAND}}", BRAND)
    (SITE_DIR / "journal.html").write_text(page)
    return len(rows)
