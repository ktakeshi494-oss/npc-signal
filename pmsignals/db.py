import sqlite3, time
from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS markets(
  condition_id TEXT PRIMARY KEY, market_id TEXT, question TEXT, slug TEXT, event_slug TEXT,
  outcomes TEXT, token_ids TEXT, created_at TEXT, end_date TEXT, closed INTEGER,
  volume24 REAL, volume1wk REAL, liquidity REAL, updated_ts INTEGER);
CREATE TABLE IF NOT EXISTS snapshots(
  ts INTEGER, condition_id TEXT, price0 REAL, volume24 REAL, PRIMARY KEY(ts, condition_id));
CREATE INDEX IF NOT EXISTS ix_snap_cid ON snapshots(condition_id, ts);
CREATE TABLE IF NOT EXISTS trades(
  tx_hash TEXT, token_id TEXT, proxy_wallet TEXT, side TEXT, outcome TEXT, size REAL, price REAL,
  usd REAL, ts INTEGER, condition_id TEXT, title TEXT, slug TEXT, event_slug TEXT, trader TEXT,
  PRIMARY KEY(tx_hash, token_id, proxy_wallet, side));
CREATE INDEX IF NOT EXISTS ix_trades_ts ON trades(ts);
CREATE TABLE IF NOT EXISTS signals(
  id INTEGER PRIMARY KEY AUTOINCREMENT, created_ts INTEGER, kind TEXT, condition_id TEXT,
  token_id TEXT, outcome TEXT, direction TEXT, ref_price REAL, title TEXT, url TEXT, text TEXT,
  details TEXT, sent_premium INTEGER DEFAULT 0, sent_free INTEGER DEFAULT 0,
  verify_ts INTEGER, verify_price REAL, verify_resolved TEXT, verdict TEXT);
CREATE INDEX IF NOT EXISTS ix_sig_kind ON signals(kind, condition_id, created_ts);
CREATE TABLE IF NOT EXISTS users(
  chat_id INTEGER PRIMARY KEY, username TEXT, joined_ts INTEGER, accepted_terms INTEGER DEFAULT 0,
  paid_until INTEGER DEFAULT 0, alerts_on INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS payments(
  id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, plan TEXT, method TEXT, tx_hash TEXT UNIQUE,
  amount REAL, asset TEXT, usd REAL, status TEXT, reason TEXT, created_ts INTEGER);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
"""

# Columns added after the first release (24h grading). Added in place if missing.
MIGRATIONS = (("signals", "verify24_ts", "INTEGER"), ("signals", "verify24_price", "REAL"),
              ("signals", "verify24_resolved", "TEXT"), ("signals", "verdict24", "TEXT"))

def migrate(con):
    for table, col, typ in MIGRATIONS:
        cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        if col not in cols:
            try:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
            except sqlite3.OperationalError as e:  # concurrent migration
                if "duplicate column" not in str(e).lower(): raise
    con.commit()

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    migrate(con)
    return con

def now():
    return int(time.time())
