# Bot.py
import logging
import os
import psycopg2
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)

# ======================
# Настройки
# ======================
ADMIN_USER_ID = 737163400
TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if not TOKEN:
    raise ValueError("❌ BOT_TOKEN не установлен")
if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL не установлен")

# ======================
# Логирование
# ======================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# ======================
# Работа с базой данных
# ======================
def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # Таблица пользователей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Таблица заметок
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    cur.close()
    conn.close()

def save_user(user_id, username, first_name, last_name):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (user_id, username, first_name, last_name)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id) DO NOTHING
    """, (user_id, username, first_name, last_name))
    conn.commit()
    cur.close()
    conn.close()

def get_all_users():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, first_name, last_name, first_seen FROM users")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_user_by_id(user_id):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        SELECT user_id, username, first_name, last_name, first_seen 
        FROM users WHERE user_id = %s
    """, (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

def save_note(user_id, text):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("INSERT INTO notes (user_id, text) VALUES (%s, %s)", (user_id, text))
    conn.commit()
    cur.close()
    conn.close()

def get_notes(user_id):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT text FROM notes WHERE user_id = %s ORDER BY created_at", (user_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [row[0] for row in rows]

def delete_note_by_index(user_id, index):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM notes 
        WHERE id IN (
            SELECT id FROM notes 
            WHERE user_id = %s 
            ORDER BY created_at 
            LIMIT 1 OFFSET %s
        )
    """, (user_id, index))
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return deleted > 0

def update_note_by_index(user_id, index, new_text):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        UPDATE notes 
        SET text = %s
        WHERE id IN (
            SELECT id FROM notes 
            WHERE user_id = %s 
            ORDER BY created_at 
            LIMIT 1 OFFSET %s
        )
    """, (new_text, user_id, index))
    updated = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return updated > 0

def count_notes(user_id):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM notes WHERE user_id = %s", (user_id,))
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count

# ======================
# Инициализация базы при запуске
# ======================
init_db()

# ======================
# Клавиатура
# ======================
def get_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📝 Добавить"), KeyboardButton("📋 Список")],
            [KeyboardButton("✏️ Редактировать"), KeyboardButton("🗑 Удалить")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

# ======================
# Обработчики
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id, user.username, user.first_name, user.last_name)
    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n"
        "Я твой личный блокнот в Telegram.\n"
        "Используй кнопки ниже:",
        reply_markup=get_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id, user.username, user.first_name, user.last_name)

    text = update.message.text
    user_id = update.effective_user.id

    state = context.user_data.get("awaiting")

    if state == "add":
        if text.strip():
            save_note(user_id, text.strip())
            await update.message.reply_text("✅ Заметка добавлена!")
        else:
            await update.message.reply_text("❌ Пустая заметка не сохранена.")
        context.user_data["awaiting"] = None

    elif state == "edit_index":
        try:
            index = int(text.strip()) - 1
            if index >= 0:
                notes = get_notes(user_id)
                if index < len(notes):
                    context.user_data["edit_index"] = index
                    context.user_data["awaiting"] = "edit_content"
                    await update.message.reply_text("✏️ Введите новый текст заметки:")
                else:
                    await update.message.reply_text("❌ Неверный номер заметки.")
                    context.user_data["awaiting"] = None
            else:
                await update.message.reply_text("❌ Номер должен быть >= 1.")
                context.user_data["awaiting"] = None
        except ValueError:
            await update.message.reply_text("❌ Введите число.")
            context.user_data["awaiting"] = None

    elif state == "edit_content":
        new_text = text.strip()
        if new_text:
            index = context.user_data["edit_index"]
            if update_note_by_index(user_id, index, new_text):
                await update.message.reply_text("✅ Заметка обновлена!")
            else:
                await update.message.reply_text("❌ Не удалось обновить заметку.")
        else:
            await update.message.reply_text("❌ Пустой текст не сохранён.")
        context.user_data["awaiting"] = None

    elif state == "delete":
        try:
            index = int(text.strip()) - 1
            if index >= 0:
                if delete_note_by_index(user_id, index):
                    await update.message.reply_text("🗑 Заметка удалена!")
                else:
                    await update.message.reply_text("❌ Не удалось удалить заметку.")
            else:
                await update.message.reply_text("❌ Номер должен быть >= 1.")
        except ValueError:
            await update.message.reply_text("❌ Введите число.")
        context.user_data["awaiting"] = None

    elif text == "📝 Добавить":
        context.user_data["awaiting"] = "add"
        await update.message.reply_text("✏️ Введите текст новой заметки:")

    elif text == "📋 Список":
        notes = get_notes(user_id)
        if not notes:
            await update.message.reply_text("📭 У вас пока нет заметок.")
        else:
            msg = "Ваши заметки:\n\n"
            for i, note in enumerate(notes, 1):
                msg += f"{i}. {note}\n"
            await update.message.reply_text(msg)

    elif text == "✏️ Редактировать":
        notes = get_notes(user_id)
        if not notes:
            await update.message.reply_text("📭 Нет заметок для редактирования.")
        else:
            msg = "Введите номер заметки, которую хотите изменить:\n\n"
            for i, note in enumerate(notes, 1):
                msg += f"{i}. {note}\n"
            context.user_data["awaiting"] = "edit_index"
            await update.message.reply_text(msg)

    elif text == "🗑 Удалить":
        notes = get_notes(user_id)
        if not notes:
            await update.message.reply_text("📭 Нет заметок для удаления.")
        else:
            msg = "Введите номер заметки для удаления:\n\n"
            for i, note in enumerate(notes, 1):
                msg += f"{i}. {note}\n"
            context.user_data["awaiting"] = "delete"
            await update.message.reply_text(msg)

    else:
        await update.message.reply_text(
            "❌ Используй кнопки ниже или команду /start",
            reply_markup=get_keyboard()
        )

# ======================
# Админ-команды
# ======================
async def send_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ У вас нет прав на эту команду.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Использование: /send <user_id> <сообщение>")
        return

    try:
        target_user_id = int(context.args[0])
        message_text = " ".join(context.args[1:])
        await context.bot.send_message(chat_id=target_user_id, text=message_text)
        await update.message.reply_text(f"✅ Сообщение отправлено пользователю {target_user_id}")
    except ValueError:
        await update.message.reply_text("❌ user_id должен быть числом.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def check_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ У вас нет доступа к этой команде.")
        return

    if not context.args:
        users = get_all_users()
        if not users:
            await update.message.reply_text("📭 Нет зарегистрированных пользователей.")
            return
        msg = f"👥 Всего пользователей: {len(users)}\n\n"
        for uid, username, first_name, last_name, first_seen in users:
            name = (first_name or "") + " " + (last_name or "")
            uname = f"@{username}" if username else "—"
            msg += f"{uid} | {name.strip()} | {uname}\n"
        await update.message.reply_text(msg)
    else:
        try:
            target_id = int(context.args[0])
            user = get_user_by_id(target_id)
            if not user:
                await update.message.reply_text(f"🔍 Пользователь {target_id} не найден.")
                return

            uid, username, first_name, last_name, first_seen = user
            name = (first_name or "") + " " + (last_name or "")
            uname = username or "—"
            note_count = count_notes(uid)

            msg = (
                f"👤 Информация о пользователе\n\n"
                f"ID: {uid}\n"
                f"Имя: {name.strip()}\n"
                f"Username: {uname}\n"
                f"Первое обращение: {first_seen}\n"
                f"Заметок: {note_count}"
            )
            await update.message.reply_text(msg)
        except ValueError:
            await update.message.reply_text("❌ user_id должен быть числом.")

# ======================
# Запуск
# ======================
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("send", send_to_user))
    app.add_handler(CommandHandler("checkuser", check_user))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Бот запущен с PostgreSQL...")
    app.run_polling()

if __name__ == "__main__":
    main()
