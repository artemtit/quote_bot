import random
import os
import re
import logging
from datetime import time
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# 🔑 ЗАМЕНИ ЭТОТ ТОКЕН НА СВОЙ ОТ @BotFather!
BOT_TOKEN = "TOKEN"

# Загрузка цитат из файла рядом с ботом
def load_quotes(filename="quotes.txt"):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, filename)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            quotes = [line.strip() for line in f if line.strip()]
        return quotes
    except FileNotFoundError:
        return ["Файл quotes.txt не найден. Создай его рядом с bot.py!"]

QUOTES = load_quotes()

# Хранилище состояний пользователей (для ввода времени)
USER_STATE = {}

# Функция отправки цитаты (для рассылки)
async def send_quote_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    if QUOTES:
        quote = random.choice(QUOTES)
        await context.bot.send_message(chat_id=chat_id, text=f"✨ {quote}")
    else:
        await context.bot.send_message(chat_id=chat_id, text="Цитаты закончились...")

# Создание клавиатуры
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("✨ Получить цитату")],
            [KeyboardButton("⏰ Ежедневно в 9:00 UTC")],
            [KeyboardButton("🕒 Выбрать своё время")],
            [KeyboardButton("📅 Каждый час")],
            [KeyboardButton("🛑 Отключить рассылку")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

# /start — показывает меню
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! 🌟 Я бот-цитатник. Нажми на кнопку ниже, чтобы начать:",
        reply_markup=get_main_keyboard()
    )

# Обработка всех текстовых сообщений (включая кнопки)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id

    # Удаляем старые задачи для этого пользователя
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    
    if text == "✨ Получить цитату":
        if QUOTES:
            quote = random.choice(QUOTES)
            await update.message.reply_text(f"✨ {quote}")
        else:
            await update.message.reply_text("Цитаты закончились...")

    elif text == "📅 Каждый час":
        for job in current_jobs:
            job.schedule_removal()
        context.job_queue.run_repeating(
            send_quote_job,
            interval=3600,
            first=1,
            chat_id=chat_id,
            name=str(chat_id)
        )
        await update.message.reply_text(
            "✅ Теперь ты будешь получать цитату каждый час!\n"
            "Нажми «🛑 Отключить рассылку», чтобы остановить."
        )

    elif text == "⏰ Ежедневно в 9:00 UTC":
        for job in current_jobs:
            job.schedule_removal()
        context.job_queue.run_daily(
            send_quote_job,
            time=time(hour=9, minute=0),
            chat_id=chat_id,
            name=str(chat_id)
        )
        await update.message.reply_text(
            "✅ Цитата будет приходить каждый день в 9:00 по UTC.\n"
            "Нажми «🛑 Отключить рассылку», чтобы остановить."
        )

    elif text == "🕒 Выбрать своё время":
        for job in current_jobs:
            job.schedule_removal()
        USER_STATE[chat_id] = "awaiting_time"
        await update.message.reply_text(
            "Напиши время в формате ЧЧ:ММ (по UTC).\n"
            "Пример: 14:30"
        )

    elif text == "🛑 Отключить рассылку":
        if current_jobs:
            for job in current_jobs:
                job.schedule_removal()
            await update.message.reply_text("⏹ Рассылка отключена.")
        else:
            await update.message.reply_text("У тебя нет активной рассылки.")

    else:
        # Проверяем, ожидаем ли ввод времени
        if USER_STATE.get(chat_id) == "awaiting_time":
            del USER_STATE[chat_id]
            if not re.match(r"^\d{1,2}:\d{2}$", text):
                await update.message.reply_text("❌ Неверный формат. Используй ЧЧ:ММ, например: 14:30")
                return
            try:
                hour, minute = map(int, text.split(":"))
                if not (0 <= hour <= 23) or not (0 <= minute <= 59):
                    raise ValueError
                send_time = time(hour=hour, minute=minute)
                context.job_queue.run_daily(
                    send_quote_job,
                    time=send_time,
                    chat_id=chat_id,
                    name=str(chat_id)
                )
                await update.message.reply_text(
                    f"✅ Цитата будет приходить каждый день в {hour:02d}:{minute:02d} по UTC.\n"
                    "Нажми «🛑 Отключить рассылку», чтобы остановить."
                )
            except ValueError:
                await update.message.reply_text("❌ Неверное время! Часы: 0–23, минуты: 0–59.")
        else:
            # Неизвестное сообщение — показываем меню
            await update.message.reply_text(
                "Не понял тебя. Выбери действие на кнопках:",
                reply_markup=get_main_keyboard()
            )

# Запуск бота
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running! Send /start in Telegram.")
    application.run_polling()

if __name__ == "__main__":
    main()