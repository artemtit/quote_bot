"""Telegram-бот-цитатник с рассылкой по московскому времени, защитой от спама и сохранением состояния."""

import random
import os
import re
import logging
import json
import atexit
from datetime import time
from collections import defaultdict, deque
import pytz
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
)
from dotenv import load_dotenv

# === Настройки ===
load_dotenv()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Переменная BOT_TOKEN не задана! Укажи её в файле .env")

MOSCOW_TZ = pytz.timezone('Europe/Moscow')
STATE_FILE = "bot_state.json"

# Глобальные переменные
ALL_QUOTES = []
USER_STATE = {}
USER_MESSAGE_TIMES = defaultdict(list)

# === Вспомогательные функции ===
def load_quotes(filename="quotes.txt"):
    """Загружает цитаты из файла."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, filename)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            quotes = [line.strip() for line in f if line.strip()]
        return quotes
    except FileNotFoundError:
        return ["Файл quotes.txt не найден. Создай его рядом с bot.py!"]

def save_state(application):
    """Сохраняет данные о цитатах, статистике и рассылках."""
    try:
        data = {}

        if 'user_queues' in application.bot_data:
            data['user_queues'] = {str(k): list(v) for k, v in application.bot_data['user_queues'].items()}
        if 'user_history' in application.bot_data:
            data['user_history'] = {str(k): v for k, v in application.bot_data['user_history'].items()}

        jobs_info = []
        for job in application.job_queue.jobs():
            if job.data and "chat_id" in job.data:
                job_info = {
                    "chat_id": str(job.data["chat_id"]),
                    "type": job.data.get("job_type", "unknown")
                }
                if job.data.get("time"):
                    job_info["time"] = job.data["time"]
                jobs_info.append(job_info)

        data['scheduled_jobs'] = jobs_info

        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("Состояние сохранено в %s", STATE_FILE)
    except Exception as e:
        logger.error("Ошибка сохранения состояния: %s", e)

def load_state(application):
    """Загружает данные и восстанавливает рассылки."""
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if 'user_queues' in application.bot_data:
            application.bot_data['user_queues'] = {
                int(k): deque(v) for k, v in data.get('user_queues', {}).items()
            }
        if 'user_history' in application.bot_data:
            application.bot_data['user_history'] = {
                int(k): v for k, v in data.get('user_history', {}).items()
            }

        for job_info in data.get('scheduled_jobs', []):
            chat_id = int(job_info["chat_id"])
            job_type = job_info["type"]
            time_str = job_info.get("time")

            if job_type == "hourly":
                application.job_queue.run_repeating(
                    send_quote_job,
                    interval=3600,
                    first=60,
                    chat_id=chat_id,
                    name=f"{chat_id}_hourly",
                    data={"chat_id": chat_id, "job_type": "hourly"}
                )
            elif job_type in ("daily", "custom") and time_str:
                hour, minute = map(int, time_str.split(":"))
                send_time = time(hour=hour, minute=minute, tzinfo=MOSCOW_TZ)
                application.job_queue.run_daily(
                    send_quote_job,
                    time=send_time,
                    chat_id=chat_id,
                    name=f"{chat_id}_{job_type}_{time_str.replace(':', '-')}",
                    data={"chat_id": chat_id, "job_type": job_type, "time": time_str}
                )

        logger.info("Состояние загружено из %s", STATE_FILE)
    except FileNotFoundError:
        logger.info("Файл состояния не найден — создаём новый.")
    except Exception as e:
        logger.error("Ошибка загрузки состояния: %s", e)

def is_spamming(chat_id: int) -> bool:
    """Проверяет, не спамит ли пользователь."""
    import time
    now = time.time()
    USER_MESSAGE_TIMES[chat_id] = [t for t in USER_MESSAGE_TIMES[chat_id] if now - t < 10]
    if len(USER_MESSAGE_TIMES[chat_id]) >= 5:
        return True
    USER_MESSAGE_TIMES[chat_id].append(now)
    return False

async def send_quote_to_user(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Отправляет цитату и сохраняет её в историю пользователя."""
    if not ALL_QUOTES:
        await context.bot.send_message(chat_id=chat_id, text="Цитаты закончились...")
        return

    bot_data = context.application.bot_data

    if 'user_queues' not in bot_data:
        bot_data['user_queues'] = {}
    if 'user_history' not in bot_data:
        bot_data['user_history'] = {}

    queues = bot_data['user_queues']
    history = bot_data['user_history']

    if chat_id not in queues or not queues[chat_id]:
        shuffled = ALL_QUOTES.copy()
        random.shuffle(shuffled)
        queues[chat_id] = deque(shuffled)

    quote = queues[chat_id].popleft()

    # Сохраняем историю — используем chat_id как int
    if chat_id not in history:
        history[chat_id] = []
    history[chat_id].append(quote)

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"✨ {quote}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Ещё цитату", callback_data="more_quote")]
        ])
    )

def get_main_keyboard():
    """Возвращает основную клавиатуру."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("✨ Получить цитату")],
            [KeyboardButton("⏰ Ежедневно в 9:00")],
            [KeyboardButton("🕒 Выбрать своё время")],
            [KeyboardButton("📅 Каждый час")],
            [KeyboardButton("🛑 Управление рассылками")],
            [KeyboardButton("📊 Статистика")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

# === Обработчики ===
async def start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Команда /start."""
    await update.message.reply_text(
        "Привет! 🌟 Я бот-цитатник. Все рассылки работают по московскому времени.",
        reply_markup=get_main_keyboard()
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику."""
    chat_id = update.effective_chat.id  # ← int, а не str!
    history_data = context.application.bot_data.get('user_history', {})
    count = len(history_data.get(chat_id, []))
    await update.message.reply_text(
        f"📊 Ты получил(а) **{count}** цитат!\n"
        "Хочешь посмотреть все? Напиши /history"
    )

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает историю полученных цитат."""
    chat_id = update.effective_chat.id  # ← int!
    history_data = context.application.bot_data.get('user_history', {})
    user_history = history_data.get(chat_id, [])

    if not user_history:
        await update.message.reply_text("Ты ещё не получил(а) ни одной цитаты.")
        return

    chunks = []
    current = ""
    for i, q in enumerate(user_history, 1):
        line = f"{i}. {q}\n\n"
        if len(current) + len(line) > 3500:
            chunks.append(current)
            current = line
        else:
            current += line
    if current:
        chunks.append(current)

    for chunk in chunks:
        await update.message.reply_text(chunk)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений."""
    if is_spamming(update.effective_chat.id):
        await update.message.reply_text("⏳ Пожалуйста, не спами. Подожди немного.")
        return

    text = update.message.text
    chat_id = update.effective_chat.id  # ← int

    if text == "✨ Получить цитату":
        await send_quote_to_user(context, chat_id)

    elif text == "📊 Статистика":
        await stats(update, context)

    elif text == "📅 Каждый час":
        job_name = f"{chat_id}_hourly"
        existing = [j for j in context.job_queue.jobs() if j.name == job_name]
        if existing:
            await update.message.reply_text("✅ Рассылка «Каждый час» уже активна.")
        else:
            context.job_queue.run_repeating(
                send_quote_job,
                interval=3600,
                first=1,
                chat_id=chat_id,
                name=job_name,
                data={"chat_id": chat_id, "job_type": "hourly"}
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
                send_quote_job,
                time=send_time,
                chat_id=chat_id,
                name=job_name,
                data={"chat_id": chat_id, "job_type": "daily", "time": "09:00"}
            )
            await update.message.reply_text("✅ Рассылка «Ежедневно в 9:00 по Москве» включена.")

    elif text == "🕒 Выбрать своё время":
        USER_STATE[chat_id] = "awaiting_time"
        await update.message.reply_text("Напиши время в формате ЧЧ:ММ (по московскому времени).\nПример: 14:30")

    elif text == "🛑 Управление рассылками":
        jobs = [j for j in context.job_queue.jobs() if j.data and j.data.get("chat_id") == chat_id]
        if not jobs:
            await update.message.reply_text("У тебя нет активных рассылок.")
        else:
            buttons = []
            for job in jobs:
                job_type = job.data.get("job_type", "unknown")
                time_str = job.data.get("time", "")
                if job_type == "hourly":
                    label = "Каждый час"
                elif job_type == "daily":
                    label = f"Ежедневно в {time_str}"
                elif job_type == "custom":
                    label = f"В {time_str}"
                else:
                    label = job.name
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
                            send_quote_job,
                            time=send_time,
                            chat_id=chat_id,
                            name=job_name,
                            data={"chat_id": chat_id, "job_type": "custom", "time": time_str}
                        )
                        await update.message.reply_text(f"✅ Рассылка «В {time_str} по Москве» включена.")
                else:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("❌ Время должно быть от 00:00 до 23:59.")
        else:
            await update.message.reply_text("Неизвестная команда.", reply_markup=get_main_keyboard())

async def send_quote_job(context: ContextTypes.DEFAULT_TYPE):
    """Задача JobQueue для отправки цитаты."""
    chat_id = context.job.data["chat_id"]
    await send_quote_to_user(context, chat_id)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка inline-кнопок."""
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = update.effective_chat.id

    if data == "more_quote":
        await send_quote_to_user(context, chat_id)
        return

    elif data == "remove_all":
        jobs = [j for j in context.job_queue.jobs() if j.data and j.data.get("chat_id") == chat_id]
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

# === Запуск ===
def main():
    global ALL_QUOTES
    ALL_QUOTES = load_quotes()

    application = Application.builder().token(BOT_TOKEN).build()
    load_state(application)
    atexit.register(save_state, application)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("history", history))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Бот запущен! Отправь /start в Telegram.")
    application.run_polling()

if __name__ == "__main__":
    main()