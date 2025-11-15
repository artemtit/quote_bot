"""
╔══════════════════════════════════════════════════════════════════╗
║                     Цитатум от Артема                            ║
╠══════════════════════════════════════════════════════════════════╣
║  Назначение: Telegram-бот для вдохновения цитатами               ║
║  Новые возможности:                                              ║
║    • Тематические цитаты (мотивация, любовь, мудрость, жизнь)   ║
║    • Выбор нескольких тем                                        ║
║    • Красивое оформление с авторами                              ║
║    • Всё остальное (рассылки, статистика, приватность)           ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import re
import logging
import json
import signal
import sys
from datetime import time
from collections import defaultdict
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

# Темы и их эмодзи
THEMES = {
    "motivation": "💪 Мотивация",
    "love": "❤️ Любовь",
    "wisdom": "🧠 Мудрость",
    "life": "🌱 Жизнь"
}

# Глобальные переменные
ALL_QUOTES = {}
USER_STATE = {}
USER_MESSAGE_TIMES = defaultdict(list)

# === Загрузка цитат по темам ===
def load_quotes():
    quotes = {}
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for theme in THEMES:
        file_path = os.path.join(current_dir, f"quotes_{theme}.txt")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
                quotes[theme] = lines
                logger.info(f"Загружено {len(lines)} цитат для темы '{theme}'")
        except FileNotFoundError:
            quotes[theme] = [f"Файл quotes_{theme}.txt не найден."]
            logger.warning(f"Файл {file_path} не найден.")
    return quotes

# === Сохранение и загрузка состояния ===
def save_state(application):
    try:
        data = {}

        # Статистика и выбор тем
        if 'user_stats' in application.bot_data:
            data['user_stats'] = application.bot_data['user_stats']

        # Рассылки
        scheduled_jobs = []
        for job in application.job_queue.jobs():
            if job.data and "chat_id" in job.data:
                job_info = {
                    "chat_id": str(job.data["chat_id"]),
                    "type": job.data.get("job_type", "unknown")
                }
                if job.data.get("time"):
                    job_info["time"] = job.data["time"]
                if job.data.get("themes"):
                    job_info["themes"] = job.data["themes"]
                scheduled_jobs.append(job_info)

        data['scheduled_jobs'] = scheduled_jobs

        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("Состояние сохранено.")
    except Exception as e:
        logger.error("Ошибка сохранения: %s", e)

def load_state(application):
    application.bot_data.setdefault('user_stats', {})  # <-- Гарантируем наличие
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if 'user_stats' in data:
            application.bot_data['user_stats'] = {
                int(k): {
                    "count": v.get("count", 0),
                    "selected_topics": v.get("selected_topics", list(THEMES.keys()))
                }
                for k, v in data['user_stats'].items()
            }

        # Рассылки
        if 'scheduled_jobs' in application.bot_data:
            for job_info in data['scheduled_jobs']:
                chat_id = int(job_info["chat_id"])
                job_type = job_info["type"]
                time_str = job_info.get("time")
                themes = job_info.get("themes", list(THEMES.keys()))

                if job_type == "hourly":
                    application.job_queue.run_repeating(
                        send_quote_job,
                        interval=3600,
                        first=60,
                        chat_id=chat_id,
                        name=f"{chat_id}_hourly",
                        data={"chat_id": chat_id, "job_type": "hourly", "themes": themes}
                    )
                elif job_type in ("daily", "custom") and time_str:
                    hour, minute = map(int, time_str.split(":"))
                    send_time = time(hour=hour, minute=minute, tzinfo=MOSCOW_TZ)
                    application.job_queue.run_daily(
                        send_quote_job,
                        time=send_time,
                        chat_id=chat_id,
                        name=f"{chat_id}_{job_type}_{time_str.replace(':', '-')}",
                        data={"chat_id": chat_id, "job_type": job_type, "time": time_str, "themes": themes}
                    )

        logger.info("Состояние загружено.")
    except FileNotFoundError:
        logger.info("Файл состояния не найден — создаём новый.")
        application.bot_data['user_stats'] = {}
    except Exception as e:
        logger.error("Ошибка загрузки: %s", e)
        application.bot_data['user_stats'] = {}

# === Вспомогательные функции ===
def is_spamming(chat_id: int) -> bool:
    import time
    now = time.time()
    USER_MESSAGE_TIMES[chat_id] = [t for t in USER_MESSAGE_TIMES[chat_id] if now - t < 10]
    if len(USER_MESSAGE_TIMES[chat_id]) >= 5:
        return True
    USER_MESSAGE_TIMES[chat_id].append(now)
    return False

def parse_quote(quote_line: str):
    """Разделяет цитату и автора по ' — ' или ' - '."""
    if " — " in quote_line:
        text, author = quote_line.rsplit(" — ", 1)
    elif " - " in quote_line:
        text, author = quote_line.rsplit(" - ", 1)
    else:
        text, author = quote_line, ""
    return text.strip('“”"'), author.strip()

def escape_markdown_v2(text: str) -> str:
    """Экранирует спецсимволы для MarkdownV2."""
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    for char in escape_chars:
        text = text.replace(char, '\\' + char)
    return text

async def send_quote_to_user(context: ContextTypes.DEFAULT_TYPE, chat_id: int, themes_list=None):
    if not ALL_QUOTES:
        await context.bot.send_message(chat_id=chat_id, text="Цитаты не загружены.")
        return

    # Получаем или создаём статистику
    stats = context.application.bot_data['user_stats'].setdefault(chat_id, {
        "count": 0,
        "selected_topics": list(THEMES.keys())
    })
    stats["count"] += 1

    # Темы для выбора
    available_themes = themes_list or stats.get("selected_topics", list(THEMES.keys()))
    if not available_themes:
        available_themes = list(THEMES.keys())

    # Выбираем случайную тему из доступных
    import random
    chosen_theme = random.choice(available_themes)
    theme_quotes = ALL_QUOTES.get(chosen_theme, [])
    if not theme_quotes:
        await context.bot.send_message(chat_id=chat_id, text="Цитаты в этой теме закончились.")
        return

    quote_line = random.choice(theme_quotes)
    text, author = parse_quote(quote_line)

    # Форматируем
    theme_name = THEMES[chosen_theme].split(" ", 1)[1]
    emoji = THEMES[chosen_theme].split(" ", 1)[0]
    author_str = f"\n— *{escape_markdown_v2(author)}*" if author else ""

    message = (
        f"{emoji} **{escape_markdown_v2(theme_name)}**\n\n"
        f"*“{escape_markdown_v2(text)}”*"
        f"{author_str}\n\n"
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=message,
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Ещё цитату", callback_data="more_quote")],
        ])
    )

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("✨ Получить цитату")],
            [KeyboardButton("📚 Выбрать темы")],
            [KeyboardButton("⏰ Ежедневно в 7:00")],
            [KeyboardButton("🕒 Выбрать своё время")],
            [KeyboardButton("📅 Каждый час")],
            [KeyboardButton("🛑 Управление рассылками"), KeyboardButton("📊 Статистика")],
        ],
        resize_keyboard=True
    )

def get_topics_keyboard(selected):
    buttons = []
    for theme_key, theme_name in THEMES.items():
        mark = "✅" if theme_key in selected else "⬜"
        buttons.append([InlineKeyboardButton(f"{mark} {theme_name}", callback_data=f"toggle_{theme_key}")])
    buttons.append([InlineKeyboardButton("✔️ Готово", callback_data="topics_done")])
    return InlineKeyboardMarkup(buttons)

# === Обработчики ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! 🌟 Я — бот вдохновляющих цитат.\n\n"
        "Выбери темы, которые тебе интересны, и получай мудрость, мотивацию или любовь каждый день 💬",
        reply_markup=get_main_keyboard()
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    stats_data = context.application.bot_data.get('user_stats', {}).get(chat_id, {})
    count = stats_data.get("count", 0)
    await update.message.reply_text(f"📊 Ты получил(а) {count} цитат!")

async def show_topic_selector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    # Гарантируем, что user_stats существует
    context.application.bot_data.setdefault('user_stats', {})
    stats = context.application.bot_data['user_stats'].setdefault(chat_id, {
        "count": 0,
        "selected_topics": list(THEMES.keys())
    })
    selected = stats.get("selected_topics", list(THEMES.keys()))
    await update.message.reply_text(
        "✅ Выбери темы, которые тебе интересны.\nМожно выбрать несколько:",
        reply_markup=get_topics_keyboard(selected)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_spamming(update.effective_chat.id):
        await update.message.reply_text("⏳ Не спами, пожалуйста.")
        return

    text = update.message.text
    chat_id = update.effective_chat.id

    if text == "✨ Получить цитату":
        await send_quote_to_user(context, chat_id)

    elif text == "📚 Выбрать темы":
        await show_topic_selector(update, context)

    elif text == "📊 Статистика":
        await stats(update, context)

    elif text == "📅 Каждый час":
        job_name = f"{chat_id}_hourly"
        existing = [j for j in context.job_queue.jobs() if j.name == job_name]
        if existing:
            await update.message.reply_text("✅ Рассылка «Каждый час» уже активна.")
        else:
            user_stats_data = context.application.bot_data['user_stats'].get(chat_id, {})
            themes = user_stats_data.get("selected_topics", list(THEMES.keys()))  # ← ИСПРАВЛЕНО
            context.job_queue.run_repeating(
                send_quote_job,
                interval=3600,
                first=1,
                chat_id=chat_id,
                name=job_name,
                data={"chat_id": chat_id, "job_type": "hourly", "themes": themes}
            )
            await update.message.reply_text("✅ Рассылка «Каждый час» включена (по МСК).")

    elif text == "⏰ Ежедневно в 7:00":
        job_name = f"{chat_id}_daily_07-00"
        existing = [j for j in context.job_queue.jobs() if j.name == job_name]
        if existing:
            await update.message.reply_text("✅ Рассылка уже активна.")
        else:
            user_stats_data = context.application.bot_data['user_stats'].get(chat_id, {})
            themes = user_stats_data.get("selected_topics", list(THEMES.keys()))  # ← ИСПРАВЛЕНО
            send_time = time(hour=7, minute=0, tzinfo=MOSCOW_TZ)
            context.job_queue.run_daily(
                send_quote_job,
                time=send_time,
                chat_id=chat_id,
                name=job_name,
                data={"chat_id": chat_id, "job_type": "daily", "time": "07:00", "themes": themes}
            )
            await update.message.reply_text("✅ Ежедневная рассылка в 7:00 по МСК включена.")

    elif text == "🕒 Выбрать своё время":
        USER_STATE[chat_id] = "awaiting_time"
        await update.message.reply_text("Напиши время в формате ЧЧ:ММ (по МСК).\nПример: 14:30")

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
                else:
                    label = f"В {time_str}"
                buttons.append([InlineKeyboardButton(f"❌ {label}", callback_data=f"remove_{job.name}")])
            buttons.append([InlineKeyboardButton("❌ Отменить всё", callback_data="remove_all")])
            await update.message.reply_text(
                "Выбери рассылку для отключения:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    else:
        if USER_STATE.get(chat_id) == "awaiting_time":
            del USER_STATE[chat_id]
            if re.match(r"^\d{1,2}:\d{2}$", text):
                try:
                    hour, minute = map(int, text.split(":"))
                    if 0 <= hour <= 23 and 0 <= minute <= 59:
                        time_str = f"{hour:02d}:{minute:02d}"
                        job_name = f"{chat_id}_custom_{time_str.replace(':', '-')}"
                        existing = [j for j in context.job_queue.jobs() if j.name == job_name]
                        if existing:
                            await update.message.reply_text(f"✅ Рассылка «В {time_str}» уже активна.")
                        else:
                            user_stats_data = context.application.bot_data['user_stats'].get(chat_id, {})
                            themes = user_stats_data.get("selected_topics", list(THEMES.keys()))  # ← ИСПРАВЛЕНО
                            send_time = time(hour=hour, minute=minute, tzinfo=MOSCOW_TZ)
                            context.job_queue.run_daily(
                                send_quote_job,
                                time=send_time,
                                chat_id=chat_id,
                                name=job_name,
                                data={"chat_id": chat_id, "job_type": "custom", "time": time_str, "themes": themes}
                            )
                            await update.message.reply_text(f"✅ Рассылка «В {time_str} по МСК» включена.")
                    else:
                        raise ValueError
                except ValueError:
                    await update.message.reply_text("❌ Время должно быть от 00:00 до 23:59.")
            else:
                await update.message.reply_text("❌ Неверный формат. Пример: 14:30")
        else:
            await update.message.reply_text("Неизвестная команда.", reply_markup=get_main_keyboard())

async def send_quote_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    themes = context.job.data.get("themes", list(THEMES.keys()))
    await send_quote_to_user(context, chat_id, themes)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = update.effective_chat.id

    if data == "more_quote":
        await send_quote_to_user(context, chat_id)

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

    elif data == "topics_done":
        await query.edit_message_text("✅ Темы сохранены! Теперь ты будешь получать цитаты только по выбранным темам.")
    
    elif data.startswith("toggle_"):
        theme_key = data.replace("toggle_", "")
        if theme_key in THEMES:
            stats = context.application.bot_data['user_stats'].setdefault(chat_id, {
                "count": 0,
                "selected_topics": list(THEMES.keys())
            })
            selected = stats.setdefault("selected_topics", list(THEMES.keys()))
            if theme_key in selected:
                selected.remove(theme_key)
            else:
                selected.append(theme_key)
            # Обновляем сообщение
            await query.edit_message_reply_markup(reply_markup=get_topics_keyboard(selected))

# === Запуск ===
def main():
    global ALL_QUOTES
    ALL_QUOTES = load_quotes()

    application = Application.builder().token(BOT_TOKEN).build()
    load_state(application)

    def signal_handler(signum, frame):
        logger.info("Получен сигнал завершения. Сохраняем состояние...")
        save_state(application)
        logger.info("Бот остановлен.")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Бот запущен!")
    try:
        application.run_polling()
    except KeyboardInterrupt:
        logger.info("Принудительная остановка (Ctrl+C). Сохраняем состояние...")
        save_state(application)
        logger.info("Бот остановлен.")

if __name__ == "__main__":
    main()    return quotes

# === Сохранение и загрузка состояния ===
def save_state(application):
    try:
        data = {}

        # Статистика и выбор тем
        if 'user_stats' in application.bot_data:
            data['user_stats'] = application.bot_data['user_stats']

        # Рассылки
        scheduled_jobs = []
        for job in application.job_queue.jobs():
            if job.data and "chat_id" in job.data:
                job_info = {
                    "chat_id": str(job.data["chat_id"]),
                    "type": job.data.get("job_type", "unknown")
                }
                if job.data.get("time"):
                    job_info["time"] = job.data["time"]
                if job.data.get("themes"):
                    job_info["themes"] = job.data["themes"]
                scheduled_jobs.append(job_info)

        data['scheduled_jobs'] = scheduled_jobs

        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("Состояние сохранено.")
    except Exception as e:
        logger.error("Ошибка сохранения: %s", e)

def load_state(application):
    application.bot_data.setdefault('user_stats', {})  # <-- Гарантируем наличие
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if 'user_stats' in data:
            application.bot_data['user_stats'] = {
                int(k): {
                    "count": v.get("count", 0),
                    "selected_topics": v.get("selected_topics", list(THEMES.keys()))
                }
                for k, v in data['user_stats'].items()
            }

        # Рассылки
        if 'scheduled_jobs' in application.bot_data:
            for job_info in data['scheduled_jobs']:
                chat_id = int(job_info["chat_id"])
                job_type = job_info["type"]
                time_str = job_info.get("time")
                themes = job_info.get("themes", list(THEMES.keys()))

                if job_type == "hourly":
                    application.job_queue.run_repeating(
                        send_quote_job,
                        interval=3600,
                        first=60,
                        chat_id=chat_id,
                        name=f"{chat_id}_hourly",
                        data={"chat_id": chat_id, "job_type": "hourly", "themes": themes}
                    )
                elif job_type in ("daily", "custom") and time_str:
                    hour, minute = map(int, time_str.split(":"))
                    send_time = time(hour=hour, minute=minute, tzinfo=MOSCOW_TZ)
                    application.job_queue.run_daily(
                        send_quote_job,
                        time=send_time,
                        chat_id=chat_id,
                        name=f"{chat_id}_{job_type}_{time_str.replace(':', '-')}",
                        data={"chat_id": chat_id, "job_type": job_type, "time": time_str, "themes": themes}
                    )

        logger.info("Состояние загружено.")
    except FileNotFoundError:
        logger.info("Файл состояния не найден — создаём новый.")
        application.bot_data['user_stats'] = {}
    except Exception as e:
        logger.error("Ошибка загрузки: %s", e)
        application.bot_data['user_stats'] = {}

# === Вспомогательные функции ===
def is_spamming(chat_id: int) -> bool:
    import time
    now = time.time()
    USER_MESSAGE_TIMES[chat_id] = [t for t in USER_MESSAGE_TIMES[chat_id] if now - t < 10]
    if len(USER_MESSAGE_TIMES[chat_id]) >= 5:
        return True
    USER_MESSAGE_TIMES[chat_id].append(now)
    return False

def parse_quote(quote_line: str):
    """Разделяет цитату и автора по ' — ' или ' - '."""
    if " — " in quote_line:
        text, author = quote_line.rsplit(" — ", 1)
    elif " - " in quote_line:
        text, author = quote_line.rsplit(" - ", 1)
    else:
        text, author = quote_line, ""
    return text.strip('“”"'), author.strip()

def escape_markdown_v2(text: str) -> str:
    """Экранирует спецсимволы для MarkdownV2."""
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    for char in escape_chars:
        text = text.replace(char, '\\' + char)
    return text

async def send_quote_to_user(context: ContextTypes.DEFAULT_TYPE, chat_id: int, themes_list=None):
    if not ALL_QUOTES:
        await context.bot.send_message(chat_id=chat_id, text="Цитаты не загружены.")
        return

    # Получаем или создаём статистику
    stats = context.application.bot_data['user_stats'].setdefault(chat_id, {
        "count": 0,
        "selected_topics": list(THEMES.keys())
    })
    stats["count"] += 1

    # Темы для выбора
    available_themes = themes_list or stats.get("selected_topics", list(THEMES.keys()))
    if not available_themes:
        available_themes = list(THEMES.keys())

    # Выбираем случайную тему из доступных
    import random
    chosen_theme = random.choice(available_themes)
    theme_quotes = ALL_QUOTES.get(chosen_theme, [])
    if not theme_quotes:
        await context.bot.send_message(chat_id=chat_id, text="Цитаты в этой теме закончились.")
        return

    quote_line = random.choice(theme_quotes)
    text, author = parse_quote(quote_line)

    # Форматируем
    theme_name = THEMES[chosen_theme].split(" ", 1)[1]
    emoji = THEMES[chosen_theme].split(" ", 1)[0]
    author_str = f"\n— *{escape_markdown_v2(author)}*" if author else ""

    message = (
        f"{emoji} **{escape_markdown_v2(theme_name)}**\n\n"
        f"*“{escape_markdown_v2(text)}”*"
        f"{author_str}\n\n"
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=message,
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Ещё цитату", callback_data="more_quote")],
        ])
    )

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("✨ Получить цитату")],
            [KeyboardButton("📚 Выбрать темы")],
            [KeyboardButton("⏰ Ежедневно в 7:00")],
            [KeyboardButton("🕒 Выбрать своё время")],
            [KeyboardButton("📅 Каждый час")],
            [KeyboardButton("🛑 Управление рассылками"), KeyboardButton("📊 Статистика")],
        ],
        resize_keyboard=True
    )

def get_topics_keyboard(selected):
    buttons = []
    for theme_key, theme_name in THEMES.items():
        mark = "✅" if theme_key in selected else "⬜"
        buttons.append([InlineKeyboardButton(f"{mark} {theme_name}", callback_data=f"toggle_{theme_key}")])
    buttons.append([InlineKeyboardButton("✔️ Готово", callback_data="topics_done")])
    return InlineKeyboardMarkup(buttons)

# === Обработчики ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! 🌟 Я — бот вдохновляющих цитат.\n\n"
        "Выбери темы, которые тебе интересны, и получай мудрость, мотивацию или любовь каждый день 💬",
        reply_markup=get_main_keyboard()
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    stats_data = context.application.bot_data.get('user_stats', {}).get(chat_id, {})
    count = stats_data.get("count", 0)
    await update.message.reply_text(f"📊 Ты получил(а) {count} цитат!")

async def show_topic_selector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    # Гарантируем, что user_stats существует
    context.application.bot_data.setdefault('user_stats', {})
    stats = context.application.bot_data['user_stats'].setdefault(chat_id, {
        "count": 0,
        "selected_topics": list(THEMES.keys())
    })
    selected = stats.get("selected_topics", list(THEMES.keys()))
    await update.message.reply_text(
        "✅ Выбери темы, которые тебе интересны.\nМожно выбрать несколько:",
        reply_markup=get_topics_keyboard(selected)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_spamming(update.effective_chat.id):
        await update.message.reply_text("⏳ Не спами, пожалуйста.")
        return

    text = update.message.text
    chat_id = update.effective_chat.id

    if text == "✨ Получить цитату":
        await send_quote_to_user(context, chat_id)

    elif text == "📚 Выбрать темы":
        await show_topic_selector(update, context)

    elif text == "📊 Статистика":
        await stats(update, context)

    elif text == "📅 Каждый час":
        job_name = f"{chat_id}_hourly"
        existing = [j for j in context.job_queue.jobs() if j.name == job_name]
        if existing:
            await update.message.reply_text("✅ Рассылка «Каждый час» уже активна.")
        else:
            user_stats_data = context.application.bot_data['user_stats'].get(chat_id, {})
            themes = user_stats_data.get("selected_topics", list(THEMES.keys()))  # ← ИСПРАВЛЕНО
            context.job_queue.run_repeating(
                send_quote_job,
                interval=3600,
                first=1,
                chat_id=chat_id,
                name=job_name,
                data={"chat_id": chat_id, "job_type": "hourly", "themes": themes}
            )
            await update.message.reply_text("✅ Рассылка «Каждый час» включена (по МСК).")

    elif text == "⏰ Ежедневно в 7:00":
        job_name = f"{chat_id}_daily_07-00"
        existing = [j for j in context.job_queue.jobs() if j.name == job_name]
        if existing:
            await update.message.reply_text("✅ Рассылка уже активна.")
        else:
            user_stats_data = context.application.bot_data['user_stats'].get(chat_id, {})
            themes = user_stats_data.get("selected_topics", list(THEMES.keys()))  # ← ИСПРАВЛЕНО
            send_time = time(hour=7, minute=0, tzinfo=MOSCOW_TZ)
            context.job_queue.run_daily(
                send_quote_job,
                time=send_time,
                chat_id=chat_id,
                name=job_name,
                data={"chat_id": chat_id, "job_type": "daily", "time": "07:00", "themes": themes}
            )
            await update.message.reply_text("✅ Ежедневная рассылка в 7:00 по МСК включена.")

    elif text == "🕒 Выбрать своё время":
        USER_STATE[chat_id] = "awaiting_time"
        await update.message.reply_text("Напиши время в формате ЧЧ:ММ (по МСК).\nПример: 14:30")

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
                else:
                    label = f"В {time_str}"
                buttons.append([InlineKeyboardButton(f"❌ {label}", callback_data=f"remove_{job.name}")])
            buttons.append([InlineKeyboardButton("❌ Отменить всё", callback_data="remove_all")])
            await update.message.reply_text(
                "Выбери рассылку для отключения:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    else:
        if USER_STATE.get(chat_id) == "awaiting_time":
            del USER_STATE[chat_id]
            if re.match(r"^\d{1,2}:\d{2}$", text):
                try:
                    hour, minute = map(int, text.split(":"))
                    if 0 <= hour <= 23 and 0 <= minute <= 59:
                        time_str = f"{hour:02d}:{minute:02d}"
                        job_name = f"{chat_id}_custom_{time_str.replace(':', '-')}"
                        existing = [j for j in context.job_queue.jobs() if j.name == job_name]
                        if existing:
                            await update.message.reply_text(f"✅ Рассылка «В {time_str}» уже активна.")
                        else:
                            user_stats_data = context.application.bot_data['user_stats'].get(chat_id, {})
                            themes = user_stats_data.get("selected_topics", list(THEMES.keys()))  # ← ИСПРАВЛЕНО
                            send_time = time(hour=hour, minute=minute, tzinfo=MOSCOW_TZ)
                            context.job_queue.run_daily(
                                send_quote_job,
                                time=send_time,
                                chat_id=chat_id,
                                name=job_name,
                                data={"chat_id": chat_id, "job_type": "custom", "time": time_str, "themes": themes}
                            )
                            await update.message.reply_text(f"✅ Рассылка «В {time_str} по МСК» включена.")
                    else:
                        raise ValueError
                except ValueError:
                    await update.message.reply_text("❌ Время должно быть от 00:00 до 23:59.")
            else:
                await update.message.reply_text("❌ Неверный формат. Пример: 14:30")
        else:
            await update.message.reply_text("Неизвестная команда.", reply_markup=get_main_keyboard())

async def send_quote_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    themes = context.job.data.get("themes", list(THEMES.keys()))
    await send_quote_to_user(context, chat_id, themes)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = update.effective_chat.id

    if data == "more_quote":
        await send_quote_to_user(context, chat_id)

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

    elif data == "topics_done":
        await query.edit_message_text("✅ Темы сохранены! Теперь ты будешь получать цитаты только по выбранным темам.")
    
    elif data.startswith("toggle_"):
        theme_key = data.replace("toggle_", "")
        if theme_key in THEMES:
            stats = context.application.bot_data['user_stats'].setdefault(chat_id, {
                "count": 0,
                "selected_topics": list(THEMES.keys())
            })
            selected = stats.setdefault("selected_topics", list(THEMES.keys()))
            if theme_key in selected:
                selected.remove(theme_key)
            else:
                selected.append(theme_key)
            # Обновляем сообщение
            await query.edit_message_reply_markup(reply_markup=get_topics_keyboard(selected))

# === Запуск ===
def main():
    global ALL_QUOTES
    ALL_QUOTES = load_quotes()

    application = Application.builder().token(BOT_TOKEN).build()
    load_state(application)

    def signal_handler(signum, frame):
        logger.info("Получен сигнал завершения. Сохраняем состояние...")
        save_state(application)
        logger.info("Бот остановлен.")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Бот запущен!")
    try:
        application.run_polling()
    except KeyboardInterrupt:
        logger.info("Принудительная остановка (Ctrl+C). Сохраняем состояние...")
        save_state(application)
        logger.info("Бот остановлен.")

if __name__ == "__main__":
    main()
