import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN", "7443235479:AAF3Kit_Dc74eFRpQr95ZvLjnMlV77Vy2tU")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))  # твой Telegram ID — заполни в Railway
PHONE = "79189934064"
PHONE_DISPLAY = "+7 (918) 993-40-64"

# Тарифы
TARIFFS = [
    {"id": "ind", "name": "📋 Индивидуальный проект", "price": 1200},
]

# Состояния разговора
ASK_FIO, ASK_GROUP, ASK_THEME, ASK_DEADLINE = range(4)

# Временное хранилище заказов
orders = {}  # chat_id -> данные заказа
all_orders = {}  # номер чека -> данные


def make_main_menu():
    keyboard = [
        [InlineKeyboardButton("📋 Индивидуальный проект — 1 200 ₽", callback_data="tariff_ind")],
        [InlineKeyboardButton("📞 Связаться с исполнителем", url="https://t.me/Inikoss")],
    ]
    return InlineKeyboardMarkup(keyboard)


def make_check_number():
    rnd = datetime.now().strftime("%m%d%H%M")
    return f"2025-{rnd}"


def format_receipt(order: dict) -> str:
    summa = order["price"]
    cn = order["cn"]
    date = order["date"]
    fio = order["fio"]
    group = order["group"]
    theme = order["theme"]
    deadline = order["deadline"]
    sbp_url = f"https://qr.nspk.ru/AS10004{PHONE}?type=02&sum={summa * 100}&cur=RUB"

    text = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"        🧾 АЛЁХИН М.Д.\n"
        f"  ИНДИВИДУАЛЬНЫЕ УЧЕБНЫЕ ПРОЕКТЫ\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"ЧЕК №      {cn}\n"
        f"ДАТА       {date}\n"
        f"СТАТУС     🟡 ОЖИДАНИЕ ОПЛАТЫ\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"ЗАКАЗЧИК\n"
        f"  {fio}\n"
        f"  {group}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"УСЛУГА\n"
        f"  📋 Индивидуальный проект\n"
        f"  Тема: {theme}\n"
        f"  Срок: {deadline}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"К ОПЛАТЕ:  {summa:,} ₽\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💳 ОПЛАТА ЧЕРЕЗ СБП\n"
        f"  Получатель: Алёхин Максим Дмитриевич\n"
        f"  Телефон: {PHONE_DISPLAY}\n\n"
        f"👇 Нажми кнопку своего банка ниже\n"
        f"или перейди по ссылке:\n"
        f"{sbp_url}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ Возврат не предусмотрен.\n"
        f"Договор-оферта: Алёхин М.Д."
    )
    return text


def make_bank_keyboard(cn: str, summa: int):
    amt = summa * 100
    nspk = f"https://qr.nspk.ru/AS10004{PHONE}?type=02&sum={amt}&cur=RUB"
    keyboard = [
        [
            InlineKeyboardButton("🟢 Сбербанк", url=nspk),
            InlineKeyboardButton("🟡 Т-Банк", url=nspk),
        ],
        [
            InlineKeyboardButton("🔵 ВТБ", url=nspk),
            InlineKeyboardButton("🔴 Альфа", url=nspk),
        ],
        [
            InlineKeyboardButton("🟠 Райффайзен", url=nspk),
            InlineKeyboardButton("🏦 Другой банк", url=nspk),
        ],
        [InlineKeyboardButton("✅ Я оплатил!", callback_data=f"paid_{cn}")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ── /test ──
async def test_notify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    await update.message.reply_text(f"Твой ID: `{uid}`\nOWNER_ID в боте: `{OWNER_ID}`", parse_mode="Markdown")
    if OWNER_ID and uid == OWNER_ID:
        await update.message.reply_text("✅ Ты исполнитель! Уведомления будут приходить сюда.")
    else:
        await update.message.reply_text(f"⚠️ Твой ID ({uid}) не совпадает с OWNER_ID ({OWNER_ID})")
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Это бот Алёхина М.Д.\n"
        "Здесь ты можешь заказать индивидуальный учебный проект и получить электронный чек.\n\n"
        "Выбери услугу:",
        reply_markup=make_main_menu()
    )


# ── Выбор тарифа ──
async def tariff_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tariff = TARIFFS[0]
    orders[query.from_user.id] = {"tariff": tariff, "price": tariff["price"]}
    await query.message.reply_text(
        f"📋 *{tariff['name']}*\n"
        f"Цена: *{tariff['price']:,} ₽*\n\n"
        f"Заполним данные для чека. Как тебя зовут?\n"
        f"_Напиши ФИО полностью:_",
        parse_mode="Markdown"
    )
    return ASK_FIO


# ── Сбор данных ──
async def ask_fio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    orders[uid]["fio"] = update.message.text.strip()
    await update.message.reply_text("📚 Курс и группа? (например: 2 курс, группа ИС-21)")
    return ASK_GROUP

async def ask_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    orders[uid]["group"] = update.message.text.strip()
    await update.message.reply_text("📝 Тема проекта?")
    return ASK_THEME

async def ask_theme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    orders[uid]["theme"] = update.message.text.strip()
    await update.message.reply_text("📅 Срок сдачи? (например: 10 июня 2025)")
    return ASK_DEADLINE

async def ask_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    order = orders[uid]
    order["deadline"] = update.message.text.strip()
    order["cn"] = make_check_number()
    order["date"] = datetime.now().strftime("%d.%m.%Y %H:%M")

    # Сохраняем
    all_orders[order["cn"]] = {**order, "user_id": uid, "username": update.message.from_user.username}

    receipt = format_receipt(order)
    kb = make_bank_keyboard(order["cn"], order["price"])

    await update.message.reply_text(
        f"```\n{receipt}\n```",
        parse_mode="Markdown",
        reply_markup=kb
    )

    # Уведомление исполнителю
    if OWNER_ID:
        try:
            await context.bot.send_message(
                OWNER_ID,
                f"🔔 *Новый заказ!*\n\n"
                f"Чек: `{order['cn']}`\n"
                f"Заказчик: {order['fio']}\n"
                f"Группа: {order['group']}\n"
                f"Тема: {order['theme']}\n"
                f"Срок: {order['deadline']}\n"
                f"Сумма: *{order['price']:,} ₽*\n"
                f"TG: @{update.message.from_user.username or '—'}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление: {e}")

    return ConversationHandler.END


# ── Нажал "Я оплатил" ──
async def paid_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Спасибо! Исполнитель проверит оплату.", show_alert=True)
    cn = query.data.replace("paid_", "")
    order = all_orders.get(cn, {})

    # Обновляем чек
    await query.message.edit_text(
        query.message.text.replace("🟡 ОЖИДАНИЕ ОПЛАТЫ", "✅ ОПЛАЧЕНО"),
        parse_mode="Markdown"
    )

    # Уведомление исполнителю
    if OWNER_ID:
        try:
            await context.bot.send_message(
                OWNER_ID,
                f"💰 *Заказчик нажал «Я оплатил»!*\n\n"
                f"Чек: `{cn}`\n"
                f"Заказчик: {order.get('fio', '—')}\n"
                f"Сумма: *{order.get('price', '—'):,} ₽*\n"
                f"Проверь поступление на телефон {PHONE_DISPLAY}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Ошибка уведомления: {e}")


# ── /cancel ──
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено. Напиши /start чтобы начать заново.")
    return ConversationHandler.END


def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(tariff_chosen, pattern="^tariff_")],
        states={
            ASK_FIO:      [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_fio)],
            ASK_GROUP:    [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_group)],
            ASK_THEME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_theme)],
            ASK_DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_deadline)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test_notify))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(paid_callback, pattern="^paid_"))

    logger.info("Бот запущен!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
