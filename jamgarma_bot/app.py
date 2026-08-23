import hashlib
import hmac
import json
import os
import urllib.parse
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import db

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
WEBHOOK_PATH = "/webhook"

CATEGORIES = {
    "ovqat": ("Ovqat", "🍲"),
    "transport": ("Transport", "🚌"),
    "kiyim": ("Kiyim", "👕"),
    "kongilochar": ("Ko'ngilochar", "🎬"),
    "kommunal": ("Kommunal", "💡"),
    "sogliq": ("Sog'liq", "💊"),
    "talim": ("Ta'lim", "📚"),
    "boshqa": ("Boshqa", "🗂️"),
}

MENU_EXPENSE = "📉 Xarajat"
MENU_INCOME = "📈 Kirim"
MENU_SAVE_ADD = "🏦 Jamg'armaga qo'shish"
MENU_SAVE_WITHDRAW = "🔓 Jamg'armadan yechish"
MENU_SAVE_VIEW = "🎯 Jamg'arma"
MENU_BALANCE = "📊 Balans"
MENU_HISTORY = "🗒 Tarix"

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [MENU_EXPENSE, MENU_INCOME],
        [MENU_SAVE_ADD, MENU_SAVE_WITHDRAW],
        [MENU_SAVE_VIEW, MENU_BALANCE],
        [MENU_HISTORY],
    ],
    resize_keyboard=True,
)

CURRENCY_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton("🇺🇿 so'm", callback_data="cur:UZS"), InlineKeyboardButton("💵 $", callback_data="cur:USD")]]
)

app = FastAPI()
application = Application.builder().token(BOT_TOKEN).build()


def fmt_uzs(n):
    return f"{n:,.0f}".replace(",", " ")


def fmt_usd(n):
    return f"{n:,.2f}"


def fmt_amount(n, currency):
    return f"{fmt_usd(n)} $" if currency == "USD" else f"{fmt_uzs(n)} so'm"


def category_keyboard():
    buttons, row = [], []
    for key, (label, emoji) in CATEGORIES.items():
        row.append(InlineKeyboardButton(f"{emoji} {label}", callback_data=f"cat:{key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def parse_amount(text):
    cleaned = text.replace(" ", "").replace("so'm", "").replace("som", "").replace("$", "").replace(",", ".")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if value > 0 else None


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if PUBLIC_URL:
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📊 Mini App'ni ochish", web_app=WebAppInfo(url=PUBLIC_URL))]]
        )
        await update.message.reply_text("Xarajat va jamg'arma ilovangiz tayyor 👇", reply_markup=kb)
    await update.message.reply_text(
        "Yoki quyidagi tugmalar orqali to'g'ridan-to'g'ri botdan foydalanishingiz mumkin:",
        reply_markup=MAIN_KEYBOARD,
    )


async def balans_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bal_uzs = db.get_balance(user_id, "UZS")
    bal_usd = db.get_balance(user_id, "USD")
    inc_uzs, exp_uzs = db.get_monthly_totals(user_id, "UZS")
    inc_usd, exp_usd = db.get_monthly_totals(user_id, "USD")
    sav_uzs = db.get_savings_total(user_id, "UZS")
    sav_usd = db.get_savings_total(user_id, "USD")

    lines = [
        "📊 <b>Umumiy balans:</b>",
        f"  🇺🇿 {fmt_uzs(bal_uzs)} so'm",
        f"  💵 {fmt_usd(bal_usd)} $",
        "",
        f"📈 Bu oy kirim: {fmt_uzs(inc_uzs)} so'm | {fmt_usd(inc_usd)} $",
        f"📉 Bu oy chiqim: {fmt_uzs(exp_uzs)} so'm | {fmt_usd(exp_usd)} $",
        "",
        f"🏦 Jamg'armada: {fmt_uzs(sav_uzs)} so'm | {fmt_usd(sav_usd)} $",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def jamgarma_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    sav_uzs = db.get_savings_total(user_id, "UZS")
    sav_usd = db.get_savings_total(user_id, "USD")
    log = db.get_savings_log(user_id, 8)
    lines = [
        "🎯 <b>Jamg'armangiz:</b>",
        f"  🇺🇿 {fmt_uzs(sav_uzs)} so'm",
        f"  💵 {fmt_usd(sav_usd)} $",
        "",
    ]
    if not log:
        lines.append("Hali jamg'armaga hech narsa qo'shilmagan.")
    else:
        lines.append("Oxirgi harakatlar:")
        for row in log:
            sign = "+" if row["amount"] >= 0 else ""
            note = f" — {row['note']}" if row["note"] else ""
            lines.append(f"{sign}{fmt_amount(row['amount'], row['currency'])} ({row['tx_date']}){note}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def tarix_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rows = db.get_all_transactions(user_id, 10)
    if not rows:
        await update.message.reply_text("Hali hech qanday yozuv yo'q.")
        return
    lines = ["🗒 <b>Oxirgi yozuvlar:</b>", ""]
    for row in rows:
        amt = fmt_amount(row["amount"], row["currency"])
        if row["type"] == "income":
            lines.append(f"📈 +{amt} — {row['tx_date']}")
        else:
            label, emoji = CATEGORIES.get(row["category"], ("Boshqa", "🗂️"))
            lines.append(f"📉 -{amt} {emoji} {label} — {row['tx_date']}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def ask_currency(update: Update, context: ContextTypes.DEFAULT_TYPE, next_awaiting: str):
    context.user_data["next_awaiting"] = next_awaiting
    await update.message.reply_text("Qaysi valyutada?", reply_markup=CURRENCY_KEYBOARD)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    awaiting = context.user_data.get("awaiting")

    if text == MENU_EXPENSE:
        await ask_currency(update, context, "exp_amount")
        return
    if text == MENU_INCOME:
        await ask_currency(update, context, "inc_amount")
        return
    if text == MENU_SAVE_ADD:
        await ask_currency(update, context, "sav_add_amount")
        return
    if text == MENU_SAVE_WITHDRAW:
        await ask_currency(update, context, "sav_out_amount")
        return
    if text == MENU_SAVE_VIEW:
        await jamgarma_cmd(update, context)
        return
    if text == MENU_BALANCE:
        await balans_cmd(update, context)
        return
    if text == MENU_HISTORY:
        await tarix_cmd(update, context)
        return

    currency = context.user_data.get("currency", "UZS")
    unit = "$" if currency == "USD" else "so'm"

    if awaiting == "exp_amount":
        amount = parse_amount(text)
        if not amount:
            await update.message.reply_text(f"Iltimos, faqat musbat raqam kiriting ({unit}).")
            return
        context.user_data["pending_amount"] = amount
        context.user_data["awaiting"] = "exp_category"
        await update.message.reply_text("Qaysi kategoriya?", reply_markup=category_keyboard())
        return

    if awaiting == "inc_amount":
        amount = parse_amount(text)
        if not amount:
            await update.message.reply_text(f"Iltimos, faqat musbat raqam kiriting ({unit}).")
            return
        db.add_transaction(user_id, "income", amount, None, None, currency=currency)
        context.user_data.clear()
        await update.message.reply_text(
            f"✅ Kirim qo'shildi: +{fmt_amount(amount, currency)}\n"
            f"Yangi balans ({unit}): {fmt_amount(db.get_balance(user_id, currency), currency)}",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    if awaiting == "sav_add_amount":
        amount = parse_amount(text)
        if not amount:
            await update.message.reply_text(f"Iltimos, faqat musbat raqam kiriting ({unit}).")
            return
        db.add_savings(user_id, amount, None, currency=currency)
        context.user_data.clear()
        await update.message.reply_text(
            f"✅ Jamg'armaga qo'shildi: +{fmt_amount(amount, currency)}\n"
            f"Jami jamg'arma ({unit}): {fmt_amount(db.get_savings_total(user_id, currency), currency)}",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    if awaiting == "sav_out_amount":
        amount = parse_amount(text)
        if not amount:
            await update.message.reply_text(f"Iltimos, faqat musbat raqam kiriting ({unit}).")
            return
        current = db.get_savings_total(user_id, currency)
        if amount > current:
            await update.message.reply_text(
                f"Jamg'armangizda faqat {fmt_amount(current, currency)} bor, {fmt_amount(amount, currency)} yecha olmaysiz."
            )
            context.user_data.clear()
            return
        db.add_savings(user_id, -amount, "yechildi", currency=currency)
        context.user_data.clear()
        await update.message.reply_text(
            f"✅ Jamg'armadan yechildi: -{fmt_amount(amount, currency)}\n"
            f"Jami jamg'arma ({unit}): {fmt_amount(db.get_savings_total(user_id, currency), currency)}",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    await update.message.reply_text("Quyidagi tugmalardan birini tanlang 👇", reply_markup=MAIN_KEYBOARD)


async def handle_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    currency = query.data.split(":", 1)[1]
    context.user_data["currency"] = currency
    next_awaiting = context.user_data.pop("next_awaiting", None)
    context.user_data["awaiting"] = next_awaiting
    unit = "$" if currency == "USD" else "so'm"
    await query.edit_message_text(f"Summani kiriting ({unit}):")


async def handle_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    key = query.data.split(":", 1)[1]
    amount = context.user_data.get("pending_amount")
    currency = context.user_data.get("currency", "UZS")
    if amount is None:
        await query.edit_message_text("Xatolik: summa topilmadi, qaytadan urinib ko'ring.")
        return
    db.add_transaction(user_id, "expense", amount, key, None, currency=currency)
    context.user_data.clear()
    label, emoji = CATEGORIES[key]
    await query.edit_message_text(
        f"✅ Xarajat qo'shildi: -{fmt_amount(amount, currency)} {emoji} {label}\n"
        f"Yangi balans: {fmt_amount(db.get_balance(user_id, currency), currency)}"
    )


application.add_handler(CommandHandler("start", start_cmd))
application.add_handler(CommandHandler("balans", balans_cmd))
application.add_handler(CommandHandler("jamgarma", jamgarma_cmd))
application.add_handler(CommandHandler("tarix", tarix_cmd))
application.add_handler(CallbackQueryHandler(handle_currency, pattern=r"^cur:"))
application.add_handler(CallbackQueryHandler(handle_category, pattern=r"^cat:"))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))


@app.on_event("startup")
async def on_startup():
    db.init_db()
    await application.initialize()
    if PUBLIC_URL and BOT_TOKEN:
        await application.bot.set_webhook(url=PUBLIC_URL + WEBHOOK_PATH)


@app.on_event("shutdown")
async def on_shutdown():
    await application.shutdown()


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}


def verify_init_data(init_data: str) -> Optional[dict]:
    try:
        parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if computed_hash != received_hash:
            return None
        user_json = parsed.get("user")
        if not user_json:
            return None
        return json.loads(user_json)
    except Exception:
        return None


def get_user_id(x_init_data: Optional[str]) -> int:
    if not x_init_data:
        raise HTTPException(401, "initData yo'q")
    user = verify_init_data(x_init_data)
    if not user:
        raise HTTPException(401, "Tekshiruv muvaffaqiyatsiz")
    return user["id"]


class TxIn(BaseModel):
    type: str
    amount: float
    currency: str = "UZS"
    category: Optional[str] = None
    date: str


class SavingsIn(BaseModel):
    amount: float
    currency: str = "UZS"
    note: Optional[str] = None


@app.get("/api/categories")
def api_categories():
    return {"categories": [{"id": k, "label": v[0], "emoji": v[1]} for k, v in CATEGORIES.items()]}


@app.get("/api/summary")
def api_summary(x_init_data: Optional[str] = Header(None)):
    uid = get_user_id(x_init_data)
    inc_uzs, exp_uzs = db.get_monthly_totals(uid, "UZS")
    inc_usd, exp_usd = db.get_monthly_totals(uid, "USD")
    return {
        "balances": {"UZS": db.get_balance(uid, "UZS"), "USD": db.get_balance(uid, "USD")},
        "monthly": {
            "UZS": {"income": inc_uzs, "expense": exp_uzs},
            "USD": {"income": inc_usd, "expense": exp_usd},
        },
        "savings": {"UZS": db.get_savings_total(uid, "UZS"), "USD": db.get_savings_total(uid, "USD")},
        "transactions": db.get_all_transactions(uid),
    }


@app.post("/api/tx")
def api_add_tx(tx: TxIn, x_init_data: Optional[str] = Header(None)):
    uid = get_user_id(x_init_data)
    if tx.amount <= 0:
        raise HTTPException(400, "Summa musbat bo'lishi kerak")
    if tx.type not in ("income", "expense"):
        raise HTTPException(400, "Noto'g'ri tur")
    if tx.currency not in ("UZS", "USD"):
        raise HTTPException(400, "Noto'g'ri valyuta")
    if tx.type == "expense" and tx.category not in CATEGORIES:
        raise HTTPException(400, "Noto'g'ri kategoriya")
    db.add_transaction(
        uid, tx.type, tx.amount, tx.category if tx.type == "expense" else None, None, tx.date, tx.currency
    )
    return {"ok": True}


@app.delete("/api/tx/{tx_id}")
def api_delete_tx(tx_id: int, x_init_data: Optional[str] = Header(None)):
    uid = get_user_id(x_init_data)
    db.delete_transaction(uid, tx_id)
    return {"ok": True}


@app.get("/api/savings")
def api_savings(x_init_data: Optional[str] = Header(None)):
    uid = get_user_id(x_init_data)
    return {
        "totals": {"UZS": db.get_savings_total(uid, "UZS"), "USD": db.get_savings_total(uid, "USD")},
        "log": db.get_savings_log(uid),
    }


@app.post("/api/savings")
def api_add_savings(s: SavingsIn, x_init_data: Optional[str] = Header(None)):
    uid = get_user_id(x_init_data)
    if s.amount == 0:
        raise HTTPException(400, "Summa 0 bo'lmasligi kerak")
    if s.currency not in ("UZS", "USD"):
        raise HTTPException(400, "Noto'g'ri valyuta")
    db.add_savings(uid, s.amount, s.note, currency=s.currency)
    return {"ok": True}


app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True), name="static")
