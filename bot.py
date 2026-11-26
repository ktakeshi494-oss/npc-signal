#!/usr/bin/env python3
"""NPC Signal Telegram bot.
- Free channel: every alert, delayed PM_FREE_DELAY_MIN minutes.
- Pro (paid): instant alerts in private chat.
- Crypto payment: unique-amount invoice -> user pastes tx hash -> on-chain check -> Pro activated.
Token comes ONLY from env TELEGRAM_BOT_TOKEN. No keys/seeds are ever stored or requested."""
import argparse, asyncio, logging, os, re, subprocess, sys, time
from telegram import Update, InlineKeyboardButton as B, InlineKeyboardMarkup as KM
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from pmsignals import db, payments
from pmsignals.config import (TELEGRAM_BOT_TOKEN, FREE_CHANNEL_ID, ADMIN_CHAT_IDS, FREE_DELAY_MIN, PLANS,
                              WALLETS, METHODS, active_methods, BRAND, CONTACT_EMAIL, SITE_URL, CHANNEL_URL, BOT_USERNAME)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")
INVOICE_TTL = 3600
HASH_RE = re.compile(r"^(0x)?[0-9a-fA-F]{64}$|^[1-9A-HJ-NP-Za-km-z]{80,90}$|^[A-Za-z0-9+/_=-]{43,44}$")
DISCLAIMER = "Information only, not financial or betting advice. Independent, not affiliated with Polymarket."

TERMS_TEXT = (f"<b>{BRAND}</b>: a few factual prediction-market alerts a day (large trades, sharp moves, volume spikes, hot new markets).\n\n"
    "Before you continue, please confirm that:\n"
    "• you are 18 or older and will use the alerts for your own personal use;\n"
    "• you are <b>not</b> a resident of the Russian Federation, and not located in a sanctioned region (Iran, Syria, Cuba, North Korea, Crimea, Donetsk, Luhansk);\n"
    "• you are not a professional capital-market firm or a market-data reseller;\n"
    "• you understand this is information only, not financial or betting advice, and that prediction-market trading is restricted in many countries.\n\n"
    "Full terms: send /terms")

def con(): return db.connect()

def owner_ids():
    c = con(); r = c.execute("SELECT v FROM meta WHERE k='owner_chat_id'").fetchone()
    return set(ADMIN_CHAT_IDS) | ({int(r[0])} if r else set())

def is_admin(chat_id): return chat_id in owner_ids()

def journal_line():
    return f"Public 7-day grading: {SITE_URL}/journal.html\n" if SITE_URL else ""

TERMS_FULL = (
    f"{BRAND}: terms (short form)\n\n"
    "1. Information service only. Alerts are automated, based on public prediction-market data. Not financial, investment, legal, tax or betting advice. We don't recommend positions, place trades or hold funds.\n"
    "2. No guarantees. Alerts may be late, incomplete or wrong. Past results (including our public 7-day grading) say nothing about the future.\n"
    "3. Eligibility: 18+, personal non-commercial use. Not available to residents of the Russian Federation, persons in sanctioned regions (Iran, Syria, Cuba, North Korea, Crimea, Donetsk, Luhansk), professional capital-market firms (brokers, market makers, prop firms, funds, banks, exchanges) or market-data resellers.\n"
    "4. Trading on prediction markets is restricted in many countries (e.g. US, UK, France, Germany). Our alerts don't make it lawful. Never use a VPN to bypass a venue's restrictions.\n"
    "5. Pro alerts are for your own use: no resale, republishing or redistribution.\n"
    "6. Payments: one-time crypto payments for a fixed period, no auto-renewal. Wrong network or address = lost funds. If Pro doesn't work because of us, write within 7 days for an extension or refund in the same asset.\n"
    "7. Independent project, not affiliated with or endorsed by Polymarket or any exchange. Trademarks belong to their owners.\n"
    "8. Privacy: we store your Telegram chat ID, username, chosen plan and submitted transaction hashes only to run the service.\n"
    f"Contact: {CONTACT_EMAIL}")

def user(c, chat_id):
    return c.execute("SELECT * FROM users WHERE chat_id=?", (chat_id,)).fetchone()

def is_pro(u): return bool(u and u["paid_until"] > time.time())

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    c = con(); ch = update.effective_chat
    c.execute("INSERT OR IGNORE INTO users(chat_id, username, joined_ts) VALUES(?,?,?)", (ch.id, update.effective_user.username, db.now())); c.commit()
    u = user(c, ch.id)
    if not u["accepted_terms"]:
        await update.message.reply_html(TERMS_TEXT, reply_markup=KM([[B("✅ I confirm", callback_data="terms_ok")], [B("❌ I don't qualify", callback_data="terms_no")]]))
        return
    await menu(update.message.reply_html, u)

async def menu(reply, u):
    st = f"Pro until {time.strftime('%Y-%m-%d', time.gmtime(u['paid_until']))} UTC ✅" if is_pro(u) else "Free plan"
    await reply(f"<b>{BRAND}</b>: {st}\n\nFree: every alert, {FREE_DELAY_MIN} min late, in our channel.\n"
                f"Pro: instant alerts here.\n{journal_line()}Free channel: {CHANNEL_URL}\n\n<i>{DISCLAIMER}</i>",
                reply_markup=KM([[B("⚡ Get Pro", callback_data="plans")], [B("ℹ️ Status", callback_data="status"), B("🔕 Alerts on/off", callback_data="toggle")]]))

async def on_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); c = con(); cid = q.message.chat.id; d = q.data
    u = user(c, cid)
    if d == "terms_ok":
        c.execute("UPDATE users SET accepted_terms=1 WHERE chat_id=?", (cid,)); c.commit()
        await q.edit_message_text("Thanks, confirmed."); return await menu(q.message.reply_html, user(c, cid))
    if d == "terms_no":
        return await q.edit_message_text("Sorry, the service isn't available to you. Nothing has been charged.")
    if not u or not u["accepted_terms"]:
        return await q.message.reply_text("Please run /start and confirm the terms first.")
    if d == "plans":
        rows = [[B(f"{p['label']}: ${p['usd']:.0f}", callback_data=f"plan:{k}")] for k, p in PLANS.items()]
        return await q.message.reply_text("Choose a plan (one-time payment, no auto-renewal):", reply_markup=KM(rows))
    if d.startswith("plan:"):
        plan = d.split(":")[1]
        rows = [[B(lbl, callback_data=f"pay:{plan}:{k}")] for k, (_, _, _, lbl) in active_methods().items()]
        return await q.message.reply_text(f"{PLANS[plan]['label']} (${PLANS[plan]['usd']:.0f}). Pay with:", reply_markup=KM(rows))
    if d.startswith("pay:"):
        _, plan, method = d.split(":")
        chain, asset, wkey, lbl = METHODS[method]
        try: amount = payments.quote(method, PLANS[plan]["usd"])
        except Exception: return await q.message.reply_text("Price feed is busy, please try again in a minute.")
        c.execute("UPDATE payments SET status='expired' WHERE chat_id=? AND status='invoice'", (cid,))
        c.execute("INSERT INTO payments(chat_id,plan,method,amount,asset,usd,status,created_ts) VALUES(?,?,?,?,?,?,?,?)",
                  (cid, plan, method, amount, asset, PLANS[plan]["usd"], "invoice", db.now())); c.commit()
        return await q.message.reply_html(
            f"Send <b>exactly</b> <code>{amount}</code> {asset}\nNetwork: <b>{lbl}</b>\nTo: <code>{WALLETS[wkey]}</code>\n\n"
            f"The amount is unique to your order, so please send it exactly (exchange withdrawals: make sure the fee isn't deducted from it). "
            f"This invoice is valid for 60 minutes{' and the rate is locked' if asset not in ('USDT','USDC') else ''}.\n\n"
            "After sending, paste the <b>transaction hash</b> (TxID) here.\n⚠️ Wrong network or asset = lost funds.")
    if d == "status":
        return await q.message.reply_text(("Pro until " + time.strftime('%Y-%m-%d %H:%M', time.gmtime(u['paid_until'])) + " UTC") if is_pro(u) else "Free plan.")
    if d == "toggle":
        c.execute("UPDATE users SET alerts_on=1-alerts_on WHERE chat_id=?", (cid,)); c.commit()
        return await q.message.reply_text("Alerts " + ("on" if user(c, cid)["alerts_on"] else "off") + ".")

async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip(); cid = update.effective_chat.id; c = con()
    if not HASH_RE.match(text):
        return await update.message.reply_text("Send /start for the menu, or paste a transaction hash to confirm a payment.")
    inv = c.execute("SELECT * FROM payments WHERE chat_id=? AND status IN ('invoice','pending') ORDER BY id DESC LIMIT 1", (cid,)).fetchone()
    if not inv or inv["created_ts"] < time.time() - INVOICE_TTL * 3:
        return await update.message.reply_text("No open invoice. Tap ⚡ Get Pro to create one first.")
    if c.execute("SELECT 1 FROM payments WHERE tx_hash=?", (text,)).fetchone():
        return await update.message.reply_text("This transaction was already used.")
    await update.message.reply_text("Checking on-chain…")
    res = await asyncio.to_thread(payments.check_tx, inv["method"], text, inv["amount"], inv["created_ts"])
    if res.ok:
        days = PLANS[inv["plan"]]["days"]; u = user(c, cid)
        base = max(u["paid_until"], db.now())
        c.execute("UPDATE users SET paid_until=? WHERE chat_id=?", (base + days * 86400, cid))
        c.execute("UPDATE payments SET status='paid', tx_hash=?, reason=NULL WHERE id=?", (text, inv["id"])); c.commit()
        await update.message.reply_text(f"✅ Payment confirmed: {res['amount']} {res['asset']}. Pro is active for {days} days. Thank you!")
        for a in owner_ids():
            await ctx.bot.send_message(a, f"💰 New payment: {res['amount']} {res['asset']} ({inv['method']}), plan {inv['plan']}, chat {cid}, tx {text}")
    else:
        st = "pending" if res.get("pending") else "invoice"
        c.execute("UPDATE payments SET status=?, reason=? WHERE id=?", (st, res["reason"], inv["id"])); c.commit()
        await update.message.reply_text(f"Not confirmed yet: {res['reason']}.\nIf you just sent it, wait a few minutes and paste the hash again. "
                                        f"Problems? {CONTACT_EMAIL}")
        for a in owner_ids():
            await ctx.bot.send_message(a, f"⚠️ Payment check failed for chat {cid}: {res['reason']} (tx {text}). Use /grant if it's valid.")

async def terms_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(TERMS_FULL, disable_web_page_preview=True)

async def claim_owner(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """One-time registration of the owner: /claim_owner <code>. The code lives in OWNER_CLAIM_CODE.txt."""
    c = con(); cid = update.effective_chat.id
    if c.execute("SELECT 1 FROM meta WHERE k='owner_chat_id'").fetchone():
        return await update.message.reply_text("Owner is already registered.")
    from pathlib import Path
    f = Path(__file__).parent / "OWNER_CLAIM_CODE.txt"
    if not f.exists() or not ctx.args or ctx.args[0].strip() != f.read_text().strip():
        log.warning("bad claim_owner attempt from %s", cid)
        return await update.message.reply_text("Invalid code.")
    c.execute("INSERT OR REPLACE INTO meta VALUES('owner_chat_id',?)", (str(cid),)); c.commit()
    f.write_text("USED " + f.read_text().strip() + "\n")
    await update.message.reply_text("✅ You are now the owner. Commands: /stats, /grant <chat_id> <days>. Payment notifications will arrive here.")

async def grant(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin: /grant <chat_id> <days>: semi-automatic fallback after a manual explorer check."""
    if not is_admin(update.effective_chat.id): return
    cid, days = int(ctx.args[0]), int(ctx.args[1]); c = con()
    u = user(c, cid); base = max(u["paid_until"] if u else 0, db.now())
    c.execute("INSERT OR IGNORE INTO users(chat_id, joined_ts, accepted_terms) VALUES(?,?,1)", (cid, db.now()))
    c.execute("UPDATE users SET paid_until=? WHERE chat_id=?", (base + days * 86400, cid)); c.commit()
    await update.message.reply_text(f"Granted {days} days to {cid}.")

async def stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_chat.id): return
    c = con()
    pro = c.execute("SELECT COUNT(*) FROM users WHERE paid_until>?", (db.now(),)).fetchone()[0]
    allu = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    rev = c.execute("SELECT COALESCE(SUM(usd),0) FROM payments WHERE status='paid'").fetchone()[0]
    await update.message.reply_text(f"Users {allu}, Pro {pro}, revenue ${rev:.0f}")

async def deliver(ctx: ContextTypes.DEFAULT_TYPE):
    """Every minute: instant to Pro, delayed to the free channel."""
    c = con()
    pros = [r["chat_id"] for r in c.execute("SELECT chat_id FROM users WHERE paid_until>? AND alerts_on=1", (db.now(),))]
    for s in c.execute("SELECT * FROM signals WHERE sent_premium=0 AND created_ts>? ORDER BY id", (db.now() - 6 * 3600,)).fetchall():
        msg = f"{s['text']}\n{s['url']}"
        for cid in pros:
            try: await ctx.bot.send_message(cid, msg, disable_web_page_preview=True)
            except Exception as e: log.warning("send %s: %s", cid, e)
            await asyncio.sleep(0.05)
        c.execute("UPDATE signals SET sent_premium=1 WHERE id=?", (s["id"],)); c.commit()
    if FREE_CHANNEL_ID:
        for s in c.execute("SELECT * FROM signals WHERE sent_free=0 AND created_ts<=? AND created_ts>? ORDER BY id", (db.now() - FREE_DELAY_MIN * 60, db.now() - 8 * 3600)).fetchall():
            try:
                await ctx.bot.send_message(FREE_CHANNEL_ID, f"{s['text']}\n{s['url']}\n\n⏱ Delayed {FREE_DELAY_MIN} min. Pro gets alerts instantly: @{BOT_USERNAME}\n{DISCLAIMER}", disable_web_page_preview=True)
                c.execute("UPDATE signals SET sent_free=1 WHERE id=?", (s["id"],)); c.commit()
            except Exception as e: log.warning("channel: %s", e); break

async def collect(ctx: ContextTypes.DEFAULT_TYPE):
    await asyncio.to_thread(subprocess.run, [sys.executable, "run_cycle.py"], timeout=600)

def session_seconds(argv=None) -> int:
    """How long this process should poll before a clean exit. 0 = run until killed.
    Used by GitHub Actions short getUpdates sessions (PM_SESSION_SECONDS or --session-seconds)."""
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--session-seconds", type=int, default=None)
    args, _ = ap.parse_known_args(argv)
    if args.session_seconds is not None:
        return max(0, args.session_seconds)
    return max(0, int(os.environ.get("PM_SESSION_SECONDS", "0") or 0))

def main():
    if not TELEGRAM_BOT_TOKEN:
        sys.exit("Set TELEGRAM_BOT_TOKEN (from @BotFather) in the environment.")
    seconds = session_seconds()
    async def post_init(app: Application):
        if seconds <= 0:
            return
        async def halt(ctx: ContextTypes.DEFAULT_TYPE):
            log.info("session timebox %ss reached, stopping", seconds)
            ctx.application.stop_running()
        app.job_queue.run_once(halt, when=seconds, name="session_halt")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler(["start", "help", "menu"], start))
    app.add_handler(CommandHandler("terms", terms_cmd)); app.add_handler(CommandHandler("claim_owner", claim_owner))
    app.add_handler(CommandHandler("grant", grant)); app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(on_cb))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, on_text))
    app.job_queue.run_repeating(deliver, interval=60, first=5)
    if os.environ.get("PM_RUN_COLLECTOR_IN_BOT") == "1":
        app.job_queue.run_repeating(collect, interval=600, first=10)
    log.info("polling start (session_seconds=%s)", seconds or "forever")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)

if __name__ == "__main__":
    main()
