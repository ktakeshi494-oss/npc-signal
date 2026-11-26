#!/usr/bin/env python3
"""One collection cycle: markets + whale trades -> signals -> 7-day grading -> journal export.
Schedule every 10 minutes (see README). Safe to re-run; dedup + cooldowns are in the DB."""
import argparse, json, sys
from pmsignals import db, collector, signals, verify, journal

ap = argparse.ArgumentParser()
ap.add_argument("--print", action="store_true", help="print new signals")
a = ap.parse_args()
con = db.connect()
prev = int((con.execute("SELECT v FROM meta WHERE k='last_run_ts'").fetchone() or [db.now() - 7200])[0])
nm = collector.collect_markets(con)
nt = collector.collect_whale_trades(con)
new = signals.run(con, whale_since_ts=prev - 600)
nv = verify.run(con)
nj = journal.export(con)
con.execute("INSERT OR REPLACE INTO meta VALUES('last_run_ts',?)", (str(db.now()),)); con.commit()
kept = con.execute("SELECT text FROM signals WHERE created_ts>=? ORDER BY id", (db.now() - 300,)).fetchall()
print(json.dumps({"markets": nm, "whale_trades_added": nt, "signals_new": len(kept), "verified": nv, "journal_rows": nj}))
if a.print:
    for r in kept: print("\n" + r["text"])
