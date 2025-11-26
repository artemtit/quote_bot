"""
─────────────────────────────────────────────────────────────────────
🌟 Цитатум — Telegram бот вдохновения
─────────────────────────────────────────────────────────────────────

📝 Назначение:
    Telegram-бот для ежедневных мотивационных, мудрых и красивых цитат

💡 Возможности:
    • Тематические подборки: 💪 Мотивация, ❤️ Любовь, 🧠 Мудрость, 🌱 Жизнь
    • Выбор любимых тем
    • Красивое оформление с авторами
    • Гибкие рассылки: каждый час, ежедневно, в своё время
    • Статистика и управление рассылками
    • Настройка часового пояса через /timezone

─────────────────────────────────────────────────────────────────────
Автор: @artemtit
GitHub: github.com/artemtit/quote_bot
─────────────────────────────────────────────────────────────────────
"""

import os
import re
import logging
import json
import signal
import sys
import asyncio
import time as time_module
from datetime import time as dt_time, timedelta, timezone
import datetime
from collections import defaultdict
import pytz
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
)
from telegram.helpers import escape_markdown as tg_escape
from dotenv import load_dotenv

# Настройки
load_dotenv()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Переменная BOT_TOKEN не задана! Укажи её в файле .env")

MOSCOW_TZ = 'Europe/Moscow'
STATE_FILE = "bot_state.json"

# Темы и их эмодзи
THEMES = {
    "motivation": "💪 Мотивация",
    "love": "❤️ Любовь",
    "wisdom": "🧠 Мудрость",
    "life": "🌱 Жизнь"
}

# English labels for themes
THEMES_EN = {
    "motivation": "💪 Motivation",
    "love": "❤️ Love",
    "wisdom": "🧠 Wisdom",
    "life": "🌱 Life"
}

# UTC смещения для часовых поясов
UTC_OFFSETS = {
    "UTC-12": "UTC-12:00",
    "UTC-11": "UTC-11:00",
    "UTC-10": "UTC-10:00",
    "UTC-9": "UTC-9:00",
    "UTC-8": "UTC-8:00",
    "UTC-7": "UTC-7:00",
    "UTC-6": "UTC-6:00",
    "UTC-5": "UTC-5:00",
    "UTC-4": "UTC-4:00",
    "UTC-3": "UTC-3:00",
    "UTC-2": "UTC-2:00",
    "UTC-1": "UTC-1:00",
    "UTC+0": "UTC+0:00 (Гринвич)",
    "UTC+1": "UTC+1:00",
    "UTC+2": "UTC+2:00",
    "UTC+3": "UTC+3:00 (Москва)",
    "UTC+4": "UTC+4:00",
    "UTC+5": "UTC+5:00",
    "UTC+6": "UTC+6:00",
    "UTC+7": "UTC+7:00",
    "UTC+8": "UTC+8:00",
    "UTC+9": "UTC+9:00",
    "UTC+10": "UTC+10:00",
    "UTC+11": "UTC+11:00",
    "UTC+12": "UTC+12:00",
    "UTC+13": "UTC+13:00",
}

# Глобальные переменные
ALL_QUOTES = {}
USER_MESSAGE_TIMES = defaultdict(list)
USER_LOCKS = defaultdict(lambda: asyncio.Lock())

# Языки
LANGUAGES = {
    'ru': 'Русский',
    'en': 'English'
}

# Локализованные сообщения (используем минимальный набор ключей)
MESSAGES = {
    'ru': {
        'start_full': (
            "Привет! 🌟 Я — бот вдохновляющих цитат!\n\n"
            "Ты можешь получать мотивацию, мудрость, любовь и жизненные советы каждый день.\n\n"
            "• Выбирай темы — кнопка \"📚 Выбрать темы\"\n"
            "• Настраивай рассылки: ежедневно, каждый час или в своё время\n"
            "• Статистика — команда /stats\n\n"
            "Если хочешь изменить язык, используй команду /language\n"
            "Если нужно скорректировать время рассылок, используй команду /timezone"
        ),
        'choose_language': "Выбери язык / Choose your language:",
        'timezone_note': "Если тебе нужно изменить часовой пояс для рассылок, используй команду /timezone и выбери свой UTC!",
        'awaiting_time_expired': "⏳ Время ожидания ввода истекло. Повторите команду.",
        'invalid_time_format': "❌ Неверный формат. Пример: 14:00",
        'hourly_already': "✅ Рассылка «Каждый час» уже активна.",
        'spam': "⏳ Не спами, пожалуйста.",
        'unknown_command': "Неизвестная команда.",
        'btn_get_quote': "✨ Получить цитату",
        'btn_choose_topics': "📚 Выбрать темы",
        'btn_daily_7': "⏰ Ежедневно в 7:00",
        'btn_choose_time': "🕒 Выбрать своё время",
        'btn_hourly': "📅 Каждый час",
        'btn_manage_jobs': "🛑 Управление рассылками",
        'btn_stats': "📊 Статистика",
        'btn_create_delivery': "➕ Создать новую рассылку",
        'btn_more_quote': "🔄 Ещё цитату",
        'btn_topics_done': "✔️ Готово",
        'prompt_custom_time': "Напиши время в формате ЧЧ:ММ.\nПример: 14:30",
        'prompt_hourly_time': "Укажи время, с которого начинать рассылку каждый час (формат ЧЧ:ММ).\nПример: 13:00",
        'create_delivery_title': "Создание рассылки",
        'choose_frequency': "Выберите частоту отправки:",
        'freq_hourly': "📅 Каждый час",
        'freq_daily': "⏰ Ежедневно в 7:00",
        'freq_once': "🕒 Один раз",
        'enter_start_time_freq': "Укажи время начала рассылки в формате ЧЧ:ММ.\nПример: 13:00",
        'confirm_create_delivery': "✅ Рассылка создана: {freq} — {time}",
        'creation_cancelled': "❌ Создание рассылки отменено.",
        'no_active_jobs': "У тебя нет активных рассылок.",
        'choose_job_to_disable': "Выбери рассылку для отключения:",
        'removed_jobs': "⏹ Отключено {n} рассылки.",
        'job_disabled': "⏹ Рассылка отключена.",
        'job_already_disabled': "Рассылка уже отключена.",
            'hourly_enabled_first': "✅ Рассылка «Каждый час» включена! Первая цитата придёт в {time} , далее — каждый час.",
            'daily_enabled': "✅ Ежедневная рассылка в {time} включена .",
            'timezone_changed': "✅ Часовой пояс изменён на: {tz}",
            'invalid_timezone': "❌ Неизвестный часовой пояс: {tz}\n\nПроверьте правильность написания. Примеры:\n• Europe/Moscow\n• America/New_York\n• Asia/Tokyo",
            'timezone_already': "ℹ️ Этот часовой пояс уже установлен:\n{tz}\n\nВыбери другой пояс или нажми /start для возврата в меню.",
            'language_set': "✅ Язык установлен: {lang}",
            'custom_already_active': "✅ Рассылка «В {time}» уже активна.",
            'custom_enabled': "✅ Рассылка «В {time}» включена.",
            'invalid_time_range': "❌ Время должно быть от 00:00 до 23:59.",
        'topics_saved': "✅ Темы сохранены! Теперь ты будешь получать цитаты только по выбранным темам.",
        'btn_remove_all': "Отменить всё",
        'label_at_time': "В {time}",
        'choose_topics_prompt': "✅ Выбери темы, которые тебе интересны.\nМожно выбрать несколько:",
        'quotes_not_loaded': "Цитаты не загружены.",
        'no_quotes_in_topics': "Нет доступных цитат в выбранных темах. Выберите другие темы.",
        'stats_received': "📊 Ты получил(а) {n} цитат!",
    },
    'en': {
        'start_full': (
            "Hi! 🌟 I'm a quotes inspiration bot!\n\n"
            "You can receive motivation, wisdom, love and life quotes every day.\n\n"
            "• Choose topics — button \"📚 Choose topics\"\n"
            "• Configure deliveries: daily, hourly or at your time\n"
            "• Stats — command /stats\n\n"
            "To change language, use /language\n"
            "To adjust deliveries time, use /timezone"
        ),
        'choose_language': "Choose your language / Выберите язык:",
        'timezone_note': "To change timezone for deliveries, use /timezone and pick your UTC!",
        'awaiting_time_expired': "⏳ Time to input expired. Please repeat the command.",
        'invalid_time_format': "❌ Invalid format. Example: 14:00",
        'hourly_already': "✅ Hourly delivery is already active.",
        'spam': "⏳ Please don't spam.",
        'unknown_command': "Unknown command.",
        'btn_get_quote': "✨ Get quote",
        'btn_choose_topics': "📚 Choose topics",
        'btn_daily_7': "⏰ Daily at 7:00",
        'btn_choose_time': "🕒 Choose your time",
        'btn_hourly': "📅 Every hour",
        'btn_manage_jobs': "🛑 Manage deliveries",
        'btn_stats': "📊 Statistics",
        'btn_create_delivery': "➕ Create new delivery",
        'btn_more_quote': "🔄 More quote",
        'btn_topics_done': "✔️ Done",
        'prompt_custom_time': "Send time in HH:MM format (your timezone).\nExample: 14:30",
        'prompt_hourly_time': "Specify start time to begin hourly delivery (HH:MM).\nExample: 13:00",
        'create_delivery_title': "Create delivery",
        'choose_frequency': "Choose frequency:",
        'freq_hourly': "📅 Every hour",
        'freq_daily': "⏰ Daily at 7:00",
        'freq_once': "🕒 Once",
        'enter_start_time_freq': "Enter start time in HH:MM format (your timezone).\nExample: 13:00",
        'confirm_create_delivery': "✅ Delivery created: {freq} — {time}",
        'creation_cancelled': "❌ Delivery creation cancelled.",
        'no_active_jobs': "You have no active deliveries.",
        'choose_job_to_disable': "Choose delivery to disable:",
        'removed_jobs': "⏹ Disabled {n} deliveries.",
        'job_disabled': "⏹ Delivery disabled.",
        'job_already_disabled': "Delivery already disabled.",
            'hourly_enabled_first': "✅ Hourly delivery enabled! First quote will arrive at {time} (your timezone), then every hour.",
            'daily_enabled': "✅ Daily delivery at {time} enabled (in your timezone).",
            'timezone_changed': "✅ Timezone changed to: {tz}",
            'invalid_timezone': "❌ Unknown timezone: {tz}\n\nCheck spelling. Examples:\n• Europe/Moscow\n• America/New_York\n• Asia/Tokyo",
            'timezone_already': "ℹ️ This timezone is already set:\n{tz}\n\nChoose another timezone or press /start to return to menu.",
            'language_set': "✅ Language set to: {lang}",
            'custom_already_active': "✅ Delivery at {time} is already active.",
            'custom_enabled': "✅ Delivery at {time} enabled (in your timezone).",
            'invalid_time_range': "❌ Time must be between 00:00 and 23:59.",
        'topics_saved': "✅ Topics saved! You will now receive quotes only for selected topics.",
        'btn_remove_all': "Remove all",
        'label_at_time': "At {time}",
        'choose_topics_prompt': "✅ Choose topics you like.\nYou can select multiple:",
        'quotes_not_loaded': "Quotes are not loaded.",
        'no_quotes_in_topics': "No available quotes in selected topics. Choose other topics.",
        'stats_received': "📊 You received {n} quotes!",
    }
}

def get_msg(lang: str, key: str) -> str:
    return MESSAGES.get(lang, MESSAGES['ru']).get(key, MESSAGES['ru'].get(key, ''))

# Служебные константы
AWAITING_TIME_TIMEOUT = 60
AUTOSAVE_INTERVAL = 300

# Загрузка цитат по темам
def load_quotes():
    """Load quotes for both Russian (default) and English (suffix _en)."""
    quotes = {'ru': {}, 'en': {}}
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for theme in THEMES:
        # Russian
        file_path_ru = os.path.join(current_dir, f"quotes_{theme}.txt")
        try:
            with open(file_path_ru, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
                quotes['ru'][theme] = lines
                logger.info(f"Loaded {len(lines)} RU quotes for '{theme}'")
        except FileNotFoundError:
            quotes['ru'][theme] = []
            logger.warning(f"RU file {file_path_ru} not found for theme '{theme}'")

        # English
        file_path_en = os.path.join(current_dir, f"quotes_{theme}_en.txt")
        try:
            with open(file_path_en, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
                quotes['en'][theme] = lines
                logger.info(f"Loaded {len(lines)} EN quotes for '{theme}'")
        except FileNotFoundError:
            quotes['en'][theme] = []
            logger.warning(f"EN file {file_path_en} not found for theme '{theme}'")

    return quotes

# Сохранение и загрузка состояния
def save_state(application):
    try:
        data = {}

        # Статистика и выбор тем
        if 'user_stats' in application.bot_data:
            # JSON требует строковые ключи
            data['user_stats'] = {
                str(k): v for k, v in application.bot_data['user_stats'].items()
            }

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
                job_info["name"] = job.name
                scheduled_jobs.append(job_info)

        data['scheduled_jobs'] = scheduled_jobs

        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("Состояние сохранено.")
    except Exception as e:
        logger.exception("Ошибка сохранения: %s", e)

async def save_state_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        save_state(context.application)
    except Exception as e:
        logger.exception("Ошибка автосохранения: %s", e)


def _remove_job_if_exists(job_queue, name):
    for j in job_queue.jobs():
        if j.name == name:
            j.schedule_removal()


def load_state(application):
    import shutil
    import datetime as _dt
    application.bot_data.setdefault('user_stats', {})

    # Try to open and parse the state file. If it's corrupt, back it up and start fresh.
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

    except FileNotFoundError:
        logger.info("Файл состояния не найден — создаём новый.")
        application.bot_data['user_stats'] = {}
        return
    except json.JSONDecodeError as e:
        logger.exception("Файл состояния повреждён (JSONDecodeError): %s", e)
        try:
            ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            broken_name = f"{STATE_FILE}.broken-{ts}"
            shutil.copy2(STATE_FILE, broken_name)
            logger.info("Создана резервная копия повреждённого файла: %s", broken_name)
        except Exception as ex:
            logger.exception("Не удалось создать резервную копию повреждённого файла: %s", ex)
        application.bot_data['user_stats'] = {}
        return
    except Exception as e:
        logger.exception("Ошибка загрузки состояния: %s", e)
        application.bot_data['user_stats'] = {}
        return

    # Если чтение прошло успешно — применяем данные
    try:
        if 'user_stats' in data:
            # keys in file are strings -> convert to int
            application.bot_data['user_stats'] = {
                int(k): v for k, v in data['user_stats'].items()
            }
            # Ensure every user has a language set (migration for older files)
            for uid, us in application.bot_data['user_stats'].items():
                if 'lang' not in us:
                    us['lang'] = 'ru'

        # Рассылки
        if 'scheduled_jobs' in data:
            for job_info in data['scheduled_jobs']:
                chat_id = int(job_info["chat_id"])
                job_type = job_info["type"]
                time_str = job_info.get("time")
                themes = job_info.get("themes", list(THEMES.keys()))
                job_name = job_info.get("name") or f"{chat_id}_{job_type}_{time_str or 'unknown'}"

                _remove_job_if_exists(application.job_queue, job_name)

                user_stats = application.bot_data.get('user_stats', {}).get(chat_id, {})
                user_tz = user_stats.get('tz', MOSCOW_TZ)
                tzobj = pytz.timezone(user_tz) if user_tz.startswith("UTC") == False else parse_utc_offset(user_tz)

                if job_type == "hourly":
                    application.job_queue.run_repeating(
                        send_quote_job,
                        interval=3600,
                        first=60,
                        chat_id=chat_id,
                        name=job_name,
                        data={"chat_id": chat_id, "job_type": "hourly", "themes": themes}
                    )
                elif job_type == 'once' and time_str:
                    # one-shot job: schedule only if time still in the future
                    hour, minute = map(int, time_str.split(":"))
                    now = datetime.datetime.now(tzobj)
                    first_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if first_time <= now:
                        logger.info("Пропускаем восстановление one-shot рассылки %s — время уже прошло: %s", job_name, time_str)
                    else:
                        first_delay = (first_time - now).total_seconds()
                        application.job_queue.run_once(
                            send_quote_job,
                            when=first_delay,
                            chat_id=chat_id,
                            name=job_name,
                            data={"chat_id": chat_id, "job_type": "once", "time": time_str, "themes": themes}
                        )
                elif job_type in ("daily", "custom") and time_str:
                    hour, minute = map(int, time_str.split(":"))
                    send_time = dt_time(hour=hour, minute=minute, tzinfo=tzobj)
                    application.job_queue.run_daily(
                        send_quote_job,
                        time=send_time,
                        chat_id=chat_id,
                        name=job_name,
                        data={"chat_id": chat_id, "job_type": job_type, "time": time_str, "themes": themes}
                    )

        logger.info("Состояние загружено.")
    except Exception as e:
        logger.exception("Ошибка обработки загруженных данных состояния: %s", e)
        application.bot_data['user_stats'] = {}

# Вспомогательные функции
def is_spamming(chat_id: int) -> bool:
    now = time_module.time()
    USER_MESSAGE_TIMES[chat_id] = [t for t in USER_MESSAGE_TIMES[chat_id] if now - t < 10]
    if len(USER_MESSAGE_TIMES[chat_id]) >= 5:
        return True
    USER_MESSAGE_TIMES[chat_id].append(now)
    return False


def parse_utc_offset(utc_str: str):
    """Преобразует UTC+3 в timezone объект."""
    try:
        if utc_str.startswith("UTC"):
            offset_str = utc_str[3:]
            offset_hours = int(offset_str)
            return timezone(timedelta(hours=offset_hours))
    except:
        pass
    return timezone.utc


def parse_quote(quote_line: str):
    """Разделяет цитату и автора по ' — ' или ' - '."""
    if " — " in quote_line:
        text, author = quote_line.rsplit(" — ", 1)
    elif " - " in quote_line:
        text, author = quote_line.rsplit(" - ", 1)
    else:
        text, author = quote_line, ""
    return text.strip('“”"'), author.strip()


async def send_quote_to_user(context: ContextTypes.DEFAULT_TYPE, chat_id: int, themes_list=None):
    async with USER_LOCKS[chat_id]:
        # Ensure user stats and language are available
        context.application.bot_data.setdefault('user_stats', {})
        user_stats = context.application.bot_data['user_stats'].setdefault(chat_id, {
            "count": 0,
            "selected_topics": list(THEMES.keys()),
            "tz": MOSCOW_TZ,
            "lang": 'ru'
        })
        lang = user_stats.get('lang', 'ru')

        if not ALL_QUOTES:
            await context.bot.send_message(chat_id=chat_id, text=get_msg(lang, 'quotes_not_loaded'))
            return

        selected_topics = user_stats.get("selected_topics", list(THEMES.keys()))
        available_themes = themes_list or selected_topics
        # Проверяем, есть ли цитаты для тем в текущем языке или в RU (fallback)
        def has_quotes_for_theme(t):
            return bool(ALL_QUOTES.get(lang, {}).get(t)) or bool(ALL_QUOTES.get('ru', {}).get(t))

        available_themes = [t for t in available_themes if has_quotes_for_theme(t)]
        if not available_themes:
            await context.bot.send_message(chat_id=chat_id, text=get_msg(lang, 'no_quotes_in_topics'))
            return

        user_stats["count"] = user_stats.get("count", 0) + 1

        import random
        chosen_theme = random.choice(available_themes)
        lang = user_stats.get('lang', 'ru')
        theme_quotes = ALL_QUOTES.get(lang, ALL_QUOTES.get('ru', {})).get(chosen_theme, [])
        if not theme_quotes:
            # fallback to ru if en list is empty
            theme_quotes = ALL_QUOTES.get('ru', {}).get(chosen_theme, [])

        quote_line = random.choice(theme_quotes)
        text, author = parse_quote(quote_line)

        emoji, theme_name = get_theme_parts(chosen_theme, lang)
        author_str = f"\n— *{tg_escape(author, version=2)}*" if author else ""

        message = (
            f"{emoji} *{tg_escape(theme_name, version=2)}*\n\n"
            f"_{tg_escape(text, version=2)}_"
            f"{author_str}\n\n"
        )

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(get_msg(lang, 'btn_more_quote'), callback_data="more_quote")],
                ])
            )
        except Exception as e:
                logger.exception("Ошибка отправки сообщения: %s", e)
                user_stats["count"] = max(0, user_stats["count"] - 1)


def get_topics_keyboard(selected):
    # kept for backward compatibility; prefer get_topics_keyboard_lang
    return get_topics_keyboard_lang(selected, 'ru')


def get_topics_keyboard_lang(selected, lang='ru'):
    buttons = []
    theme_labels = THEMES_EN if lang == 'en' else THEMES
    for theme_key, theme_name in theme_labels.items():
        mark = "✅" if theme_key in selected else "⬜"
        buttons.append([InlineKeyboardButton(f"{mark} {theme_name}", callback_data=f"toggle_{theme_key}")])
    buttons.append([InlineKeyboardButton(get_msg(lang, 'btn_topics_done'), callback_data="topics_done")])
    return InlineKeyboardMarkup(buttons)


def get_theme_parts(theme_key: str, lang: str = 'ru'):
    labels = THEMES_EN if lang == 'en' else THEMES
    label = labels.get(theme_key, theme_key)
    parts = label.split(" ", 1)
    if len(parts) > 1:
        return parts[0], parts[1]
    return "", label


def get_main_keyboard(lang: str = 'ru'):
    return ReplyKeyboardMarkup(
        [   
            [KeyboardButton(get_msg(lang, 'btn_get_quote'))],
            [KeyboardButton(get_msg(lang, 'btn_create_delivery'))],
            [KeyboardButton(get_msg(lang, 'btn_choose_topics'))],
            [KeyboardButton(get_msg(lang, 'btn_manage_jobs')), KeyboardButton(get_msg(lang, 'btn_stats'))],
        ],
        resize_keyboard=True
    )


def get_timezone_keyboard():
    """Создаёт клавиатуру для выбора часового пояса по UTC."""
    buttons = []
    for utc_key, utc_name in UTC_OFFSETS.items():
        buttons.append([InlineKeyboardButton(utc_name, callback_data=f"tz_{utc_key}")])
    return InlineKeyboardMarkup(buttons)


async def timezone_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_stats = context.application.bot_data['user_stats'].setdefault(chat_id, {
        "count": 0,
        "selected_topics": list(THEMES.keys()),
        "tz": MOSCOW_TZ
    })
    current_tz = user_stats.get("tz", MOSCOW_TZ)
    lang = user_stats.get('lang', 'ru')
    tz_display = UTC_OFFSETS.get(current_tz, current_tz)
    await update.message.reply_text(
        f"🌍 {get_msg(lang, 'timezone_note')}\n\n"
        f"{tz_display}",
        reply_markup=get_timezone_keyboard()
    )


# Обработчики
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    context.application.bot_data.setdefault('user_stats', {})
    user_stats = context.application.bot_data['user_stats'].get(chat_id, {})
    # If language is not set, ask language first
    if not user_stats or 'lang' not in user_stats:
        # Ask language first
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Русский", callback_data="set_lang_ru"), InlineKeyboardButton("English", callback_data="set_lang_en")]
        ])
        await update.message.reply_text(get_msg('ru', 'choose_language'), reply_markup=kb)
        return
    # If timezone is not set, prompt timezone selection
    if 'tz' not in user_stats:
        lang = user_stats.get('lang', 'ru')
        tz_msg = get_msg(lang, 'timezone_note')
        await update.message.reply_text(f"🌍 {tz_msg}", reply_markup=get_timezone_keyboard())
        return

    lang = user_stats.get('lang', 'ru')
    await update.message.reply_text(get_msg(lang, 'start_full'), reply_markup=get_main_keyboard(lang))



async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    stats_data = context.application.bot_data.get('user_stats', {}).get(chat_id, {})
    count = stats_data.get("count", 0)
    chat_id = update.effective_chat.id
    user_stats = context.application.bot_data.get('user_stats', {}).get(chat_id, {})
    lang = user_stats.get('lang', 'ru')
    await update.message.reply_text(get_msg(lang, 'stats_received').format(n=count))


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to change language."""
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Русский", callback_data="set_lang_ru"), InlineKeyboardButton("English", callback_data="set_lang_en")]
    ])
    chat_id = update.effective_chat.id
    context.application.bot_data.setdefault('user_stats', {})
    user_stats = context.application.bot_data['user_stats'].get(chat_id, {})
    lang = user_stats.get('lang', 'ru')
    await update.message.reply_text(get_msg(lang, 'choose_language'), reply_markup=kb)


async def show_topic_selector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    context.application.bot_data.setdefault('user_stats', {})
    user_stats = context.application.bot_data['user_stats'].setdefault(chat_id, {
        "count": 0,
        "selected_topics": list(THEMES.keys()),
        "tz": MOSCOW_TZ
    })
    selected = user_stats.get("selected_topics", list(THEMES.keys()))
    lang = user_stats.get('lang', 'ru')
    await update.message.reply_text(
        get_msg(lang, 'choose_topics_prompt'),
        reply_markup=get_topics_keyboard_lang(selected, lang)
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик пользовательских сообщений."""
    chat_id = update.effective_chat.id
    # ensure user stats and language
    context.application.bot_data.setdefault('user_stats', {})
    user_stats = context.application.bot_data['user_stats'].setdefault(chat_id, {"count":0, "selected_topics": list(THEMES.keys()), "tz": MOSCOW_TZ, "lang": 'ru'})
    lang = user_stats.get('lang', 'ru')

    if is_spamming(chat_id):
        await update.message.reply_text(get_msg(lang, 'spam'))
        return

    text = update.message.text

    if text == get_msg(lang, 'btn_get_quote'):
        await send_quote_to_user(context, chat_id)
        save_state(context.application)

    elif text == get_msg(lang, 'btn_create_delivery'):
        # Start creation flow: choose frequency
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_msg(lang, 'freq_hourly'), callback_data="cd_freq_hourly")],
            [InlineKeyboardButton(get_msg(lang, 'freq_daily'), callback_data="cd_freq_daily")],
            [InlineKeyboardButton(get_msg(lang, 'freq_once'), callback_data="cd_freq_once")]
        ])
        await update.message.reply_text(get_msg(lang, 'choose_frequency'), reply_markup=kb)
        return

    elif text == get_msg(lang, 'btn_choose_topics'):
        await show_topic_selector(update, context)
    elif text == get_msg(lang, 'btn_stats'):
        await stats(update, context)

    elif text == get_msg(lang, 'btn_hourly'):
        job_name = f"{chat_id}_hourly"
        existing = [j for j in context.job_queue.jobs() if j.name == job_name]
        if existing:
            await update.message.reply_text(get_msg(lang, 'hourly_already'))
        else:
            context.user_data["awaiting_hourly_time"] = True
            context.user_data["awaiting_hourly_time_ts"] = time_module.time() + AWAITING_TIME_TIMEOUT
            await update.message.reply_text(get_msg(lang, 'prompt_hourly_time'))
    elif context.user_data.get("awaiting_hourly_time"):
        expiry = context.user_data.get("awaiting_hourly_time_ts", 0)
        if time_module.time() > expiry:
            context.user_data.pop("awaiting_hourly_time", None)
            context.user_data.pop("awaiting_hourly_time_ts", None)
            await update.message.reply_text(get_msg(lang, 'awaiting_time_expired'))
            return

        context.user_data.pop("awaiting_hourly_time", None)
        context.user_data.pop("awaiting_hourly_time_ts", None)
        if re.match(r"^\d{1,2}:\d{2}$", text):
            try:
                hour, minute = map(int, text.split(":"))
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    user_stats = context.application.bot_data['user_stats'].setdefault(chat_id, {"count":0, "selected_topics": list(THEMES.keys()), "tz": MOSCOW_TZ})
                    user_tz = user_stats.get('tz', MOSCOW_TZ)
                    tzobj = pytz.timezone(user_tz) if not user_tz.startswith("UTC") else parse_utc_offset(user_tz)
                    job_name = f"{chat_id}_hourly"
                    _remove_job_if_exists(context.job_queue, job_name)
                    now = datetime.datetime.now(tzobj)
                    # Вычисляем время до первого запуска
                    first_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if first_time < now:
                        first_time += timedelta(days=1)
                    first_delay = (first_time - now).total_seconds()
                    context.job_queue.run_repeating(
                        send_quote_job,
                        interval=3600,
                        first=first_delay,
                        chat_id=chat_id,
                        name=job_name,
                        data={
                            "chat_id": chat_id,
                            "job_type": "hourly",
                            "themes": user_stats.get('selected_topics', list(THEMES.keys())),
                            "start_time": f"{hour:02d}:{minute:02d}"
                        }
                    )
                    save_state(context.application)
                    await update.message.reply_text(get_msg(lang, 'hourly_enabled_first').format(time=first_time.strftime('%H:%M')))
                else:
                    raise ValueError
            except ValueError:
                await update.message.reply_text(get_msg(lang, 'invalid_time_format'))
        else:
            await update.message.reply_text(get_msg(lang, 'invalid_time_format'))

    # Note: new-delivery inline callbacks and time-input flow removed per user request
    # Re-added: handle awaiting input for new delivery time
    elif context.user_data.get('awaiting_new_delivery_time'):
        expiry = context.user_data.get('awaiting_new_delivery_time_ts', 0)
        if time_module.time() > expiry:
            context.user_data.pop('awaiting_new_delivery_time', None)
            context.user_data.pop('awaiting_new_delivery_time_ts', None)
            context.user_data.pop('new_delivery', None)
            await update.message.reply_text(get_msg(lang, 'awaiting_time_expired'))
            return

        context.user_data.pop('awaiting_new_delivery_time', None)
        context.user_data.pop('awaiting_new_delivery_time_ts', None)
        new_delivery = context.user_data.pop('new_delivery', {})
        freq = new_delivery.get('freq')
        if not freq:
            await update.message.reply_text(get_msg(lang, 'unknown_command'))
            return

        if re.match(r"^\d{1,2}:\d{2}$", text):
            try:
                hour, minute = map(int, text.split(":"))
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError

                user_stats = context.application.bot_data['user_stats'].setdefault(chat_id, {"count":0, "selected_topics": list(THEMES.keys()), "tz": MOSCOW_TZ})
                user_tz = user_stats.get('tz', MOSCOW_TZ)
                tzobj = pytz.timezone(user_tz) if not user_tz.startswith("UTC") else parse_utc_offset(user_tz)

                if freq == 'hourly':
                    # schedule repeating every hour, compute first delay
                    now = datetime.datetime.now(tzobj)
                    first_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if first_time < now:
                        first_time += timedelta(days=1)
                    first_delay = (first_time - now).total_seconds()
                    job_name = f"{chat_id}_delivery_hourly_{hour:02d}{minute:02d}"
                    _remove_job_if_exists(context.job_queue, job_name)
                    context.job_queue.run_repeating(
                        send_quote_job,
                        interval=3600,
                        first=first_delay,
                        chat_id=chat_id,
                        name=job_name,
                        data={"chat_id": chat_id, "job_type": "hourly", "time": f"{hour:02d}:{minute:02d}", "themes": user_stats.get('selected_topics', list(THEMES.keys()))}
                    )

                elif freq == 'once':
                    # One-time delivery -> schedule single run
                    now = datetime.datetime.now(tzobj)
                    first_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if first_time < now:
                        first_time += timedelta(days=1)
                    first_delay = (first_time - now).total_seconds()
                    job_name = f"{chat_id}_delivery_once_{hour:02d}{minute:02d}"
                    _remove_job_if_exists(context.job_queue, job_name)
                    context.job_queue.run_once(
                        send_quote_job,
                        when=first_delay,
                        chat_id=chat_id,
                        name=job_name,
                        data={"chat_id": chat_id, "job_type": "once", "time": f"{hour:02d}:{minute:02d}", "themes": user_stats.get('selected_topics', list(THEMES.keys()))}
                    )

                else:
                    # daily or custom -> schedule daily at specified time
                    send_time = dt_time(hour=hour, minute=minute, tzinfo=tzobj)
                    job_type = 'daily' if freq == 'daily' else 'custom'
                    job_name = f"{chat_id}_delivery_{job_type}_{hour:02d}{minute:02d}"
                    _remove_job_if_exists(context.job_queue, job_name)
                    context.job_queue.run_daily(
                        send_quote_job,
                        time=send_time,
                        chat_id=chat_id,
                        name=job_name,
                        data={"chat_id": chat_id, "job_type": job_type, "time": f"{hour:02d}:{minute:02d}", "themes": user_stats.get('selected_topics', list(THEMES.keys()))}
                    )

                save_state(context.application)
                freq_label = get_msg(lang, 'freq_' + freq)
                await update.message.reply_text(get_msg(lang, 'confirm_create_delivery').format(freq=freq_label, time=f"{hour:02d}:{minute:02d}"))
            except ValueError:
                await update.message.reply_text(get_msg(lang, 'invalid_time_range'))
        else:
            await update.message.reply_text(get_msg(lang, 'invalid_time_format'))

    elif text == get_msg(lang, 'btn_daily_7'):
        user_stats = context.application.bot_data['user_stats'].setdefault(chat_id, {"count":0, "selected_topics": list(THEMES.keys()), "tz": MOSCOW_TZ})
        user_tz = user_stats.get('tz', MOSCOW_TZ)
        tzobj = pytz.timezone(user_tz) if not user_tz.startswith("UTC") else parse_utc_offset(user_tz)

        job_name = f"{chat_id}_daily_07-00"
        existing = [j for j in context.job_queue.jobs() if j.name == job_name]
        if existing:
            await update.message.reply_text(get_msg(lang, 'hourly_already'))
        else:
            _remove_job_if_exists(context.job_queue, job_name)
            send_time = dt_time(hour=7, minute=0, tzinfo=tzobj)
            context.job_queue.run_daily(
                send_quote_job,
                time=send_time,
                chat_id=chat_id,
                name=job_name,
                data={"chat_id": chat_id, "job_type": "daily", "time": "07:00", "themes": user_stats.get('selected_topics', list(THEMES.keys()))}
            )
            save_state(context.application)
            await update.message.reply_text(get_msg(lang, 'daily_enabled').format(time="07:00"))

    elif text == get_msg(lang, 'btn_choose_time'):
        context.user_data["awaiting_time"] = True
        context.user_data["awaiting_time_ts"] = time_module.time() + AWAITING_TIME_TIMEOUT
        await update.message.reply_text(get_msg(lang, 'prompt_custom_time'))

    elif text == get_msg(lang, 'btn_manage_jobs'):
        jobs = [j for j in context.job_queue.jobs() if j.data and j.data.get("chat_id") == chat_id]
        if not jobs:
            await update.message.reply_text(get_msg(lang, 'no_active_jobs'))
        else:
            buttons = []
            for job in jobs:
                job_type = job.data.get("job_type", "unknown")
                time_str = job.data.get("time", "")
                if job_type == "hourly":
                    if time_str:
                        label = f"{get_msg(lang, 'btn_hourly')} ({time_str})"
                    else:
                        label = get_msg(lang, 'btn_hourly')
                else:
                    label = get_msg(lang, 'label_at_time').format(time=time_str)
                buttons.append([InlineKeyboardButton(f"❌ {label}", callback_data=f"remove_{job.name}")])
            buttons.append([InlineKeyboardButton(f"❌ {get_msg(lang, 'btn_remove_all')}", callback_data="remove_all")])
            try:
                await update.message.reply_text(
                    get_msg(lang, 'choose_job_to_disable'),
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            except Exception as e:
                logger.warning("Ошибка отправки списка рассылок (попытка повторной отправки): %s", e)
                try:
                    await asyncio.sleep(1)
                    await update.message.reply_text(
                        get_msg(lang, 'choose_job_to_disable'),
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                except Exception:
                    logger.exception("Не удалось отправить список рассылок после повторной попытки.")

    else:
        if context.user_data.get("awaiting_timezone"):
            expiry = context.user_data.get("awaiting_tz_ts", 0)
            if time_module.time() > expiry:
                context.user_data.pop("awaiting_timezone", None)
                context.user_data.pop("awaiting_tz_ts", None)
                await update.message.reply_text(get_msg(lang, 'awaiting_time_expired'))
                return

            context.user_data.pop("awaiting_timezone", None)
            context.user_data.pop("awaiting_tz_ts", None)
            
            try:
                # Проверяем, является ли это валидным часовым поясом
                if not text.startswith("UTC"):
                    test_tz = pytz.timezone(text)
                else:
                    test_tz = parse_utc_offset(text)
                
                user_stats = context.application.bot_data['user_stats'].setdefault(chat_id, {
                    "count": 0,
                    "selected_topics": list(THEMES.keys()),
                    "tz": MOSCOW_TZ
                })
                user_stats["tz"] = text
                save_state(context.application)
                await update.message.reply_text(get_msg(lang, 'timezone_changed').format(tz=text))
            except pytz.exceptions.UnknownTimeZoneError:
                await update.message.reply_text(get_msg(lang, 'invalid_timezone').format(tz=text))
            return

        if context.user_data.get("awaiting_time"):
            expiry = context.user_data.get("awaiting_time_ts", 0)
            if time_module.time() > expiry:
                context.user_data.pop("awaiting_time", None)
                context.user_data.pop("awaiting_time_ts", None)
                await update.message.reply_text(get_msg(lang, 'awaiting_time_expired'))
                return

            context.user_data.pop("awaiting_time", None)
            context.user_data.pop("awaiting_time_ts", None)
            if re.match(r"^\d{1,2}:\d{2}$", text):
                try:
                    hour, minute = map(int, text.split(":"))
                    if 0 <= hour <= 23 and 0 <= minute <= 59:
                        time_str = f"{hour:02d}:{minute:02d}"
                        job_name = f"{chat_id}_custom_{time_str.replace(':', '-')}"
                        existing = [j for j in context.job_queue.jobs() if j.name == job_name]
                        if existing:
                            await update.message.reply_text(get_msg(lang, 'custom_already_active').format(time=time_str))
                        else:
                            user_stats = context.application.bot_data['user_stats'].setdefault(chat_id, {"count":0, "selected_topics": list(THEMES.keys()), "tz": MOSCOW_TZ})
                            user_tz = user_stats.get('tz', MOSCOW_TZ)
                            tzobj = pytz.timezone(user_tz) if not user_tz.startswith("UTC") else parse_utc_offset(user_tz)
                            send_time = dt_time(hour=hour, minute=minute, tzinfo=tzobj)

                            _remove_job_if_exists(context.job_queue, job_name)
                            context.job_queue.run_daily(
                                send_quote_job,
                                time=send_time,
                                chat_id=chat_id,
                                name=job_name,
                                data={"chat_id": chat_id, "job_type": "custom", "time": time_str, "themes": user_stats.get('selected_topics', list(THEMES.keys()))}
                            )
                            save_state(context.application)
                            await update.message.reply_text(get_msg(lang, 'custom_enabled').format(time=time_str))
                    else:
                        raise ValueError
                except ValueError:
                    await update.message.reply_text(get_msg(lang, 'invalid_time_range'))
            else:
                await update.message.reply_text(get_msg(lang, 'invalid_time_format'))
        else:
            await update.message.reply_text(get_msg(lang, 'unknown_command'), reply_markup=get_main_keyboard(lang))


async def send_quote_job(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data or {}
    job_type = job_data.get('job_type')
    chat_id = job_data.get("chat_id") or context.job.chat_id
    user_stats = context.application.bot_data.get('user_stats', {}).get(chat_id, {})
    themes = job_data.get("themes") or user_stats.get("selected_topics", list(THEMES.keys()))

    try:
        await send_quote_to_user(context, chat_id, themes)
    finally:
        # If this was a one-time delivery, ensure it's removed and state is saved
        if job_type == 'once':
            try:
                # schedule_removal is safe even if job already completed
                context.job.schedule_removal()
            except Exception:
                pass
            try:
                save_state(context.application)
            except Exception:
                logger.exception('Ошибка при сохранении состояния после выполнения one-shot рассылки')


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
        user_stats = context.application.bot_data.get('user_stats', {}).get(chat_id, {})
        lang = user_stats.get('lang', 'ru')
        await query.edit_message_text(get_msg(lang, 'removed_jobs').format(n=len(jobs)))

    elif data.startswith("remove_"):
        job_name = data.replace("remove_", "")
        jobs = [j for j in context.job_queue.jobs() if j.name == job_name]
        if jobs:
            jobs[0].schedule_removal()
            user_stats = context.application.bot_data.get('user_stats', {}).get(chat_id, {})
            lang = user_stats.get('lang', 'ru')
            await query.edit_message_text(get_msg(lang, 'job_disabled'))
        else:
            user_stats = context.application.bot_data.get('user_stats', {}).get(chat_id, {})
            lang = user_stats.get('lang', 'ru')
            await query.edit_message_text(get_msg(lang, 'job_already_disabled'))

    elif data == "topics_done":
        save_state(context.application)
        user_stats = context.application.bot_data.get('user_stats', {}).get(chat_id, {})
        lang = user_stats.get('lang', 'ru')
        await query.edit_message_text(get_msg(lang, 'topics_saved'))
    
    elif data.startswith("tz_"):
        tz_key = data.replace("tz_", "")
        
        if tz_key.startswith("UTC"):
            user_stats = context.application.bot_data['user_stats'].setdefault(chat_id, {
                "count": 0,
                "selected_topics": list(THEMES.keys()),
                "tz": MOSCOW_TZ
            })
            current_tz = user_stats.get("tz", MOSCOW_TZ)
            tz_display = UTC_OFFSETS.get(tz_key, tz_key)
            
            user_stats = context.application.bot_data.get('user_stats', {}).get(chat_id, {})
            lang = user_stats.get('lang', 'ru')
            if current_tz == tz_key:
                await query.edit_message_text(get_msg(lang, 'timezone_already').format(tz=tz_display), reply_markup=get_timezone_keyboard())
            else:
                user_stats = context.application.bot_data['user_stats'].setdefault(chat_id, {
                    "count": 0,
                    "selected_topics": list(THEMES.keys()),
                    "tz": MOSCOW_TZ
                })
                user_stats["tz"] = tz_key
                save_state(context.application)
                await query.edit_message_text(get_msg(lang, 'timezone_changed').format(tz=tz_display))

    # Note: create-delivery callbacks removed per user request
    elif data.startswith("cd_"):
        # create-delivery callbacks
        # selected a frequency
        freq = None
        if data == "cd_freq_hourly":
            freq = 'hourly'
        elif data == "cd_freq_daily":
            freq = 'daily'
        elif data == "cd_freq_once":
            freq = 'once'

        if freq:
            # store selection and ask for start time
            context.user_data['new_delivery'] = {'freq': freq}
            user_stats = context.application.bot_data.get('user_stats', {}).get(chat_id, {})
            lang = user_stats.get('lang', 'ru')
            await query.edit_message_text(f"{get_msg(lang, 'create_delivery_title')} — {get_msg(lang, 'freq_' + freq)}")
            await context.bot.send_message(chat_id=chat_id, text=get_msg(lang, 'enter_start_time_freq'))
            context.user_data['awaiting_new_delivery_time'] = True
            context.user_data['awaiting_new_delivery_time_ts'] = time_module.time() + AWAITING_TIME_TIMEOUT
            return

    elif data.startswith("set_lang_"):
        lang_code = data.replace("set_lang_", "")
        if lang_code in LANGUAGES:
            # Do not force a default tz here: keep tz absent so we can prompt user to pick it
            user_stats = context.application.bot_data['user_stats'].get(chat_id)
            if not user_stats:
                context.application.bot_data['user_stats'][chat_id] = {
                    "count": 0,
                    "selected_topics": list(THEMES.keys()),
                    "lang": lang_code
                }
                user_stats = context.application.bot_data['user_stats'][chat_id]
            else:
                user_stats['lang'] = lang_code

            save_state(context.application)
            # confirm in the newly selected language
            await query.edit_message_text(get_msg(lang_code, 'language_set').format(lang=LANGUAGES[lang_code]))
            # If timezone not set, ask for timezone selection next
            if 'tz' not in user_stats:
                await context.bot.send_message(chat_id=chat_id, text=get_msg(lang_code, 'timezone_note'), reply_markup=get_timezone_keyboard())
    
    elif data.startswith("toggle_"):
        theme_key = data.replace("toggle_", "")
        if theme_key in THEMES:
            user_stats = context.application.bot_data['user_stats'].setdefault(chat_id, {
                "count": 0,
                "selected_topics": list(THEMES.keys()),
                "tz": MOSCOW_TZ
            })
            selected = user_stats.setdefault("selected_topics", list(THEMES.keys()))
            if theme_key in selected:
                selected.remove(theme_key)
            else:
                selected.append(theme_key)
            save_state(context.application)
            user_stats = context.application.bot_data.get('user_stats', {}).get(chat_id, {})
            lang = user_stats.get('lang', 'ru')
            await query.edit_message_reply_markup(reply_markup=get_topics_keyboard_lang(selected, lang))


# Запуск
def main():
    global ALL_QUOTES
    ALL_QUOTES = load_quotes()

    application = Application.builder().token(BOT_TOKEN).build()
    load_state(application)

    application.job_queue.run_repeating(save_state_job, interval=AUTOSAVE_INTERVAL, first=AUTOSAVE_INTERVAL)

    def signal_handler(signum, frame):
        logger.info("Получен сигнал завершения. Сохраняем состояние...")
        save_state(application)
        logger.info("Бот остановлен.")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("timezone", timezone_command))
    application.add_handler(CommandHandler("language", language_command))
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
