"""On-chain payment checks through free public endpoints (no API keys, no custody).
Anti-fraud: every invoice gets a UNIQUE amount, so a stolen/foreign tx hash won't match;
tx hashes are single-use (UNIQUE in DB); tx must be newer than the invoice and confirmed."""
import base64, hashlib, random, time
from decimal import Decimal
from .config import WALLETS, METHODS, TOKENS, RPC, PRICE_API, COINGECKO_IDS, PAYMENT_MAX_AGE_H
from .http import get_json, post_json

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
NATIVE_DECIMALS = {"BTC": 8, "ETH": 18, "BNB": 18, "SOL": 9, "TON": 9}
MIN_CONF = {"eth": 3, "bsc": 5, "btc": 1}

class Result(dict):
    ok = property(lambda s: s.get("ok", False))

def fail(reason, **kw): return Result(ok=False, reason=reason, **kw)

# ---------------- pricing / invoices ----------------
def usd_price(asset):
    if asset in ("USDT", "USDC"): return 1.0
    d = get_json(PRICE_API, {"ids": COINGECKO_IDS[asset], "vs_currencies": "usd"})
    return float(d[COINGECKO_IDS[asset]]["usd"])

def quote(method, usd):
    """Amount to request. Stablecoins: usd + unique 0.001-0.999 tag. Native coins: converted
    at current price with a unique tail in the last digits."""
    chain, asset, _, _ = METHODS[method]
    if asset in ("USDT", "USDC"):
        return round(usd + random.randint(1, 999) / 1000, 3)
    px = usd_price(asset)
    digits = {"BTC": 8, "ETH": 6, "BNB": 5, "SOL": 4, "TON": 3}[asset]
    amt = round(usd / px, digits - 2)
    return float(Decimal(str(amt)) + Decimal(random.randint(1, 99)) / Decimal(10 ** digits))

def amount_matches(asset, expected, got):
    if asset in ("USDT", "USDC"):
        return abs(got - expected) < 0.0005 or got >= expected + 1.0  # exact tag, or clearly overpaid
    return got >= expected * 0.995  # native: the unique tail + small tolerance

# ---------------- address helpers ----------------
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
def b58decode(s):
    n = 0
    for c in s: n = n * 58 + B58.index(c)
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return b"\x00" * (len(s) - len(s.lstrip("1"))) + raw

def tron_to_hex20(addr):
    raw = b58decode(addr); body, chk = raw[:-4], raw[-4:]
    assert hashlib.sha256(hashlib.sha256(body).digest()).digest()[:4] == chk, "bad tron checksum"
    return body[1:].hex()  # drop 0x41 prefix -> 20-byte hex

def ton_to_raw(addr):
    if ":" in addr: wc, h = addr.split(":"); return f"{int(wc)}:{h.lower()}"
    b = base64.urlsafe_b64decode(addr + "=" * (-len(addr) % 4))
    return f"{int.from_bytes(b[1:2], 'big', signed=True)}:{b[2:34].hex()}"

def norm_hash_ton(h):
    h = h.strip()
    if len(h) == 64 and all(c in "0123456789abcdefABCDEF" for c in h): return h.lower()
    return base64.urlsafe_b64decode(h.replace("+", "-").replace("/", "_") + "=" * (-len(h) % 4)).hex()

# ---------------- chain checkers: return list of (asset, amount, ts, confirmed) paid to address ----------------
def _evm(chain, tx, to):
    rpc = RPC[chain]
    call = lambda m, p: post_json(rpc, {"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).get("result")
    t = call("eth_getTransactionByHash", [tx]); rc = call("eth_getTransactionReceipt", [tx])
    if not t or not rc: return None, "transaction not found (yet)"
    if rc.get("status") != "0x1": return None, "transaction failed on-chain"
    latest = int(call("eth_blockNumber", []), 16); bn = int(rc["blockNumber"], 16)
    ts = int(call("eth_getBlockByNumber", [rc["blockNumber"], False])["timestamp"], 16)
    conf = latest - bn + 1 >= MIN_CONF[chain]
    out, to = [], to.lower()
    if (t.get("to") or "").lower() == to and int(t["value"], 16) > 0:
        out.append(("ETH" if chain == "eth" else "BNB", int(t["value"], 16) / 1e18, ts, conf))
    for lg in rc["logs"]:
        if lg["topics"] and lg["topics"][0] == TRANSFER_TOPIC and len(lg["topics"]) == 3 \
           and lg["topics"][2][-40:].lower() == to[2:]:
            for (c, sym), (addr, dec) in TOKENS.items():
                if c == chain and addr.lower() == lg["address"].lower():
                    out.append((sym, int(lg["data"], 16) / 10 ** dec, ts, conf))
    return out, None

def _btc(tx, to):
    try: t = get_json(f"{RPC['btc']}/tx/{tx}")
    except Exception: t = get_json(f"https://blockstream.info/api/tx/{tx}")  # fallback explorer
    st = t.get("status", {})
    out = [("BTC", v["value"] / 1e8, st.get("block_time") or int(time.time()), bool(st.get("confirmed")))
           for v in t["vout"] if v.get("scriptpubkey_address") == to]
    return out, None

def _tron(tx, to):
    info = post_json(f"{RPC['tron']}/wallet/gettransactioninfobyid", {"value": tx})
    if not info: return None, "transaction not found (yet)"
    if info.get("receipt", {}).get("result") not in (None, "SUCCESS"): return None, "transaction failed on-chain"
    to_hex = tron_to_hex20(to); usdt_hex = tron_to_hex20(TOKENS[("tron", "USDT")][0])
    out = []
    for lg in info.get("log", []):
        if lg.get("address", "").lower()[-40:] == usdt_hex and lg["topics"][0] == TRANSFER_TOPIC[2:] \
           and lg["topics"][2][-40:].lower() == to_hex:
            out.append(("USDT", int(lg["data"], 16) / 1e6, info["blockTimeStamp"] // 1000, True))
    # TRC-20 on Tron is final after ~19 blocks (~1 min); info only exists once included in a block
    return out, None

def _sol(tx, to):
    r = post_json(RPC["sol"], {"jsonrpc": "2.0", "id": 1, "method": "getTransaction",
        "params": [tx, {"encoding": "jsonParsed", "commitment": "confirmed", "maxSupportedTransactionVersion": 1}]}).get("result")
    if not r: return None, "transaction not found (yet)"
    meta = r["meta"]
    if meta.get("err"): return None, "transaction failed on-chain"
    keys = [k["pubkey"] if isinstance(k, dict) else k for k in r["transaction"]["message"]["accountKeys"]]
    out, ts = [], r.get("blockTime") or int(time.time())
    if to in keys:
        i = keys.index(to); d = (meta["postBalances"][i] - meta["preBalances"][i]) / 1e9
        if d > 0: out.append(("SOL", d, ts, True))
    mints = {TOKENS[("sol", s)][0]: s for s in ("USDT", "USDC")}
    def bal(lst):
        return {(b["mint"], b.get("owner")): float(b["uiTokenAmount"]["uiAmount"] or 0) for b in lst or []}
    pre, post = bal(meta.get("preTokenBalances")), bal(meta.get("postTokenBalances"))
    for (mint, owner), v in post.items():
        if owner == to and mint in mints and v - pre.get((mint, owner), 0) > 0:
            out.append((mints[mint], v - pre.get((mint, owner), 0), ts, True))
    return out, None

def _ton(tx, to):
    raw = ton_to_raw(to); h = norm_hash_ton(tx); out = []
    base = RPC["ton"]
    js = get_json(f"{base}/jetton/transfers", {"owner_address": to, "direction": "in",
                  "jetton_master": TOKENS[("ton", "USDT")][0], "limit": 100, "sort": "desc"})
    for j in js.get("jetton_transfers", []):
        hashes = {norm_hash_ton(j.get("transaction_hash", "")), norm_hash_ton(j.get("trace_id", "") or "00" * 32)}
        if h in hashes and not j.get("transaction_aborted"):
            out.append(("USDT", int(j["amount"]) / 1e6, j["transaction_now"], True))
    time.sleep(1.1)  # toncenter free tier ~1 rps without key
    txs = get_json(f"{base}/transactions", {"account": to, "limit": 100, "sort": "desc"})
    for t in txs.get("transactions", []):
        im = t.get("in_msg") or {}
        # buyers usually paste THEIR wallet's tx hash = trace id of the chain of txs
        if h in {norm_hash_ton(t["hash"]), norm_hash_ton(im.get("hash") or "00" * 32), norm_hash_ton(t.get("trace_id") or "00" * 32)} \
           and (im.get("destination") or "").lower() == raw and int(im.get("value") or 0) > 0 \
           and not t.get("description", {}).get("aborted"):
            out.append(("TON", int(im["value"]) / 1e9, t["now"], True))
    return out, None

def check_tx(method, tx_hash, expected_amount, invoice_ts, address_override=None):
    chain, asset, wkey, _ = METHODS[method]
    to = address_override or WALLETS[wkey]
    if not to: return fail("this payment method is not enabled")
    tx = tx_hash.strip()
    try:
        if chain in ("eth", "bsc"):
            if not tx.startswith("0x"): tx = "0x" + tx
            found, err = _evm(chain, tx, to)
        elif chain == "btc": found, err = _btc(tx, to)
        elif chain == "tron": found, err = _tron(tx.removeprefix("0x"), to)
        elif chain == "sol": found, err = _sol(tx, to)
        elif chain == "ton": found, err = _ton(tx, to)
        else: return fail("unknown chain")
    except Exception as e:
        return fail(f"could not check the transaction right now ({type(e).__name__}); try again in a minute")
    if err: return fail(err)
    got = sum(a for s, a, ts, c in found if s == asset)
    if not found or got <= 0: return fail(f"no {asset} transfer to our {chain.upper()} address in this transaction")
    ts = min(ts for s, a, ts, c in found if s == asset)
    if invoice_ts and ts < invoice_ts - 300: return fail("this transaction is older than the invoice")
    if ts < time.time() - PAYMENT_MAX_AGE_H * 3600: return fail("transaction is too old")
    if not all(c for s, a, t, c in found if s == asset): return fail("waiting for confirmations, try again in a few minutes", pending=True)
    if expected_amount is not None and not amount_matches(asset, expected_amount, got):
        return fail(f"amount {got} {asset} does not match the invoice ({expected_amount} {asset})", amount=got)
    return Result(ok=True, amount=got, asset=asset, chain=chain, ts=ts)
