import random
import os
import re
import logging
from datetime import time
from collections import deque
import pytz
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
)
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Переменная BOT_TOKEN не задана! Укажи её в файле .env")

# Часовой пояс Москвы
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

# Загрузка цитат
def load_quotes(filename="quotes.txt"):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, filename)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            quotes = [line.strip() for line in f if line.strip()]
        return quotes
    except FileNotFoundError:
        return ["Файл quotes.txt не найден. Создай его рядом с bot.py!"]

ALL_QUOTES = load_quotes()
USER_STATE = {}

# --- Отправка цитаты без повторов ---
async def send_quote_to_user(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    if not ALL_QUOTES:
        await context.bot.send_message(chat_id=chat_id, text="Цитаты закончились...")
        return

    if 'user_queues' not in context.application.bot_data:
        context.application.bot_data['user_queues'] = {}
    queues = context.application.bot_data['user_queues']

    if chat_id not in queues or not queues[chat_id]:
        shuffled = ALL_QUOTES.copy()
        random.shuffle(shuffled)
        queues[chat_id] = deque(shuffled)

    quote = queues[chat_id].popleft()
    await context.bot.send_message(chat_id=chat_id, text=f"✨ {quote}")

# --- Клавиатура ---
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("✨ Получить цитату")],
            [KeyboardButton("⏰ Ежедневно в 9:00")],
            [KeyboardButton("🕒 Выбрать своё время")],
            [KeyboardButton("📅 Каждый час")],
            [KeyboardButton("🛑 Управление рассылками")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

# --- Вспомогательная функция: получить задачи пользователя ---
def get_user_jobs(job_queue, chat_id):
    prefix = f"{chat_id}_"
    return [job for job in job_queue.jobs() if job.name and job.name.startswith(prefix)]

# --- Обработчики ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! 🌟 Я бот-цитатник. Все рассылки работают по **московскому времени**.",
        reply_markup=get_main_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id

    if text == "✨ Получить цитату":
        await send_quote_to_user(context, chat_id)

    elif text == "📅 Каждый час":
        job_name = f"{chat_id}_hourly"
        existing = [j for j in context.job_queue.jobs() if j.name == job_name]
        if existing:
            await update.message.reply_text("✅ Рассылка «Каждый час» уже активна.")
        else:
            context.job_queue.run_repeating(
                lambda ctx: send_quote_to_user(ctx, chat_id),
                interval=3600,
                first=1,
                chat_id=chat_id,
                name=job_name
            )
            await update.message.reply_text("✅ Рассылка «Каждый час» включена (по Москве).")

    elif text == "⏰ Ежедневно в 9:00":
        job_name = f"{chat_id}_daily_09-00"
        existing = [j for j in context.job_queue.jobs() if j.name == job_name]
        if existing:
            await update.message.reply_text("✅ Рассылка «Ежедневно в 9:00» уже активна.")
        else:
            send_time = time(hour=9, minute=0, tzinfo=MOSCOW_TZ)
            context.job_queue.run_daily(
                lambda ctx: send_quote_to_user(ctx, chat_id),
                time=send_time,
                chat_id=chat_id,
                name=job_name
            )
            await update.message.reply_text("✅ Рассылка «Ежедневно в 9:00 по Москве» включена.")

    elif text == "🕒 Выбрать своё время":
        USER_STATE[chat_id] = "awaiting_time"
        await update.message.reply_text("Напиши время в формате ЧЧ:ММ (по московскому времени).\nПример: 14:30")

    elif text == "🛑 Управление рассылками":
        jobs = get_user_jobs(context.job_queue, chat_id)
        if not jobs:
            await update.message.reply_text("У тебя нет активных рассылок.")
        else:
            buttons = []
            for job in jobs:
                name = job.name.replace(f"{chat_id}_", "")
                if name == "hourly":
                    label = "Каждый час"
                elif name.startswith("daily_"):
                    time_part = name.replace("daily_", "").replace("-", ":")
                    label = f"Ежедневно в {time_part}"
                elif name.startswith("custom_"):
                    time_part = name.replace("custom_", "").replace("-", ":")
                    label = f"В {time_part}"
                else:
                    label = name
                buttons.append([InlineKeyboardButton(f"❌ {label}", callback_data=f"remove_{job.name}")])
            buttons.append([InlineKeyboardButton("❌ Отменить всё", callback_data="remove_all")])
            await update.message.reply_text(
                "Выбери рассылку для отключения:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    else:
        if USER_STATE.get(chat_id) == "awaiting_time":
            del USER_STATE[chat_id]
            if not re.match(r"^\d{1,2}:\d{2}$", text):
                await update.message.reply_text("❌ Неверный формат. Пример: 14:30")
                return
            try:
                hour, minute = map(int, text.split(":"))
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    time_str = f"{hour:02d}:{minute:02d}"
                    job_name = f"{chat_id}_custom_{time_str.replace(':', '-')}"
                    existing = [j for j in context.job_queue.jobs() if j.name == job_name]
                    if existing:
                        await update.message.reply_text(f"✅ Рассылка «В {time_str}» уже активна.")
                    else:
                        send_time = time(hour=hour, minute=minute, tzinfo=MOSCOW_TZ)
                        context.job_queue.run_daily(
                            lambda ctx: send_quote_to_user(ctx, chat_id),
                            time=send_time,
                            chat_id=chat_id,
                            name=job_name
                        )
                        await update.message.reply_text(f"✅ Рассылка «В {time_str} по Москве» включена.")
                else:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("❌ Время должно быть от 00:00 до 23:59.")
        else:
            await update.message.reply_text("Неизвестная команда.", reply_markup=get_main_keyboard())

# --- Обработка inline-кнопок ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = update.effective_chat.id

    if data == "remove_all":
        jobs = get_user_jobs(context.job_queue, chat_id)
        for job in jobs:
            job.schedule_removal()
        await query.edit_message_text(f"⏹ Отключено {len(jobs)} рассылок.")
    elif data.startswith("remove_"):
        job_name = data.replace("remove_", "")
        jobs = [j for j in context.job_queue.jobs() if j.name == job_name]
        if jobs:
            jobs[0].schedule_removal()
            await query.edit_message_text("⏹ Рассылка отключена.")
        else:
            await query.edit_message_text("Рассылка уже отключена.")

# --- Запуск ---
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_handler))
    print("Bot is running! Send /start in Telegram.")
    application.run_polling()

if __name__ == "__main__":
    main()