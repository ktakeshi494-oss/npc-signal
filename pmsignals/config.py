"""Central configuration. Secrets come ONLY from environment variables."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("PM_DB_PATH", ROOT / "data" / "pmsignals.sqlite"))
SITE_DIR = ROOT / "site"
SITE_URL = os.environ.get("PM_SITE_URL", "").rstrip("/")   # empty until the site is live
BOT_USERNAME = "npc_signal_ai"
CHANNEL_URL = "https://t.me/ainpcsignal"

BRAND = "NPC Signal"          # working name; must NOT contain "Polymarket" (trademark)
CONTACT_EMAIL = "v5yn9jr3@mail.grokbot.com"
USER_AGENT = f"{BRAND}/0.1 (independent analytics; contact {CONTACT_EMAIL})"

GAMMA = "https://gamma-api.polymarket.com"
DATA = "https://data-api.polymarket.com"

# --- signal thresholds (few, high-quality alerts) ---
WHALE_MIN_USD = float(os.environ.get("PM_WHALE_MIN_USD", 25000))
MOVE_MIN_PP = float(os.environ.get("PM_MOVE_MIN_PP", 10))        # percentage points
MOVE_WINDOW_MIN = int(os.environ.get("PM_MOVE_WINDOW_MIN", 120))  # compare to snapshot this old
MOVE_MIN_VOL24 = float(os.environ.get("PM_MOVE_MIN_VOL24", 100000))
VOLUME_SPIKE_X = float(os.environ.get("PM_VOLUME_SPIKE_X", 3.0))  # 24h vol vs avg daily of last week
VOLUME_SPIKE_MIN = float(os.environ.get("PM_VOLUME_SPIKE_MIN", 250000))
HOT_NEW_MAX_AGE_H = 72
HOT_NEW_MIN_VOL24 = float(os.environ.get("PM_HOT_NEW_MIN_VOL24", 250000))
COOLDOWN_H = 12                      # one alert per market per type per 12h
MAX_SIGNALS_PER_RUN = 8
VERIFY_AFTER_DAYS = 7
# skip ultra-short "Up or Down" 5/15-minute crypto markets: pure noise for alerts
SKIP_SLUG_PATTERNS = ("updown", "up-or-down")
TOP_MARKETS = 300                    # markets snapshotted per run (by 24h volume)

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
FREE_CHANNEL_ID = os.environ.get("PM_FREE_CHANNEL_ID", "")       # e.g. @predictionpulse_free or -100...
ADMIN_CHAT_IDS = {int(x) for x in os.environ.get("PM_ADMIN_CHAT_IDS", "").split(",") if x.strip()}
FREE_DELAY_MIN = int(os.environ.get("PM_FREE_DELAY_MIN", 30))

# --- plans (USD) ---
PLANS = {
    "week":  {"usd": 5.0,  "days": 7,   "label": "Weekly pass"},
    "month": {"usd": 12.0, "days": 30,  "label": "Monthly"},
    "year":  {"usd": 99.0, "days": 365, "label": "Yearly"},
}
PAYMENT_TOLERANCE = 0.03   # accept up to 3% under (price moves / fees)
PAYMENT_MAX_AGE_H = 72     # tx must be newer than this

# --- payout wallets (owner's PUBLIC addresses; see ../WALLETS.md). Never put keys/seeds here. ---
WALLETS = {
    "BTC":  os.environ.get("PM_WALLET_BTC",  "bc1qplkhmamefv04aragraha7efd23rpwwq02w44xu"),
    "EVM":  os.environ.get("PM_WALLET_EVM",  "0xA38e763c548A1A16D75E4Dfab0Ab920C95B8C731"),  # ETH + BSC
    "TRON": os.environ.get("PM_WALLET_TRON", "TEWbCEht6kSrg7a3EWapjFmyHgdfxD35rU"),
    "SOL":  os.environ.get("PM_WALLET_SOL",  "2T6iYCT7yegvbpSw4MtWAwnFN3pd3WiiCMedbsges5Sp"),
    "TON":  os.environ.get("PM_WALLET_TON",  "UQDHWu4TpGJwVohgJhaHE6bw0CsgC8wCr5p6VFPFGXFr_hvY"),  # optional: "" disables
}

# Payment methods shown to buyers: key -> (chain, asset, wallet key, human label)
METHODS = {
    "usdt_trc20": ("tron", "USDT", "TRON", "USDT on Tron (TRC-20) - lowest fee"),
    "usdt_ton":   ("ton",  "USDT", "TON",  "USDT on TON"),
    "ton":        ("ton",  "TON",  "TON",  "Toncoin (TON)"),
    "usdt_sol":   ("sol",  "USDT", "SOL",  "USDT on Solana (SPL)"),
    "usdc_sol":   ("sol",  "USDC", "SOL",  "USDC on Solana (SPL)"),
    "sol":        ("sol",  "SOL",  "SOL",  "Solana (SOL)"),
    "usdt_bsc":   ("bsc",  "USDT", "EVM",  "USDT on BNB Smart Chain (BEP-20)"),
    "bnb":        ("bsc",  "BNB",  "EVM",  "BNB (BNB Smart Chain)"),
    "usdt_eth":   ("eth",  "USDT", "EVM",  "USDT on Ethereum (ERC-20)"),
    "usdc_eth":   ("eth",  "USDC", "EVM",  "USDC on Ethereum (ERC-20)"),
    "eth":        ("eth",  "ETH",  "EVM",  "Ether (ETH)"),
    "btc":        ("btc",  "BTC",  "BTC",  "Bitcoin (BTC)"),
}

def active_methods():
    return {k: v for k, v in METHODS.items() if WALLETS.get(v[2])}

# Token contracts (mainnet)
TOKENS = {
    ("eth", "USDT"): ("0xdAC17F958D2ee523a2206206994597C13D831ec7", 6),
    ("eth", "USDC"): ("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6),
    ("bsc", "USDT"): ("0x55d398326f99059fF775485246999027B3197955", 18),
    ("tron", "USDT"): ("TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t", 6),
    ("sol", "USDT"): ("Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB", 6),
    ("sol", "USDC"): ("EPjFWdd5AufqSSqeM2qrpiTkU3rXsxHVyF5BxzoGJkU8", 6),
    ("ton", "USDT"): ("EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs", 6),
}
# Free public endpoints (no keys). Override via env if one is down.
RPC = {
    "eth": os.environ.get("PM_RPC_ETH", "https://ethereum-rpc.publicnode.com"),
    "bsc": os.environ.get("PM_RPC_BSC", "https://bsc-rpc.publicnode.com"),
    "sol": os.environ.get("PM_RPC_SOL", "https://api.mainnet-beta.solana.com"),
    "tron": os.environ.get("PM_API_TRON", "https://api.trongrid.io"),
    "btc": os.environ.get("PM_API_BTC", "https://mempool.space/api"),
    "ton": os.environ.get("PM_API_TON", "https://toncenter.com/api/v3"),
}
PRICE_API = "https://api.coingecko.com/api/v3/simple/price"
COINGECKO_IDS = {"BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin", "SOL": "solana", "TON": "the-open-network"}
