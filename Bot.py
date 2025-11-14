# Bot.py
import json
import logging
import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)

# ======================
# Настройки
# ======================
NOTES_FILE = "notes.json"
USERS_FILE = "users.json"
ADMIN_USER_ID = 737163400

# 🔐 Лучше использовать переменную окружения:
TOKEN = os.getenv("BOT_TOKEN")

# ======================
# Логирование
# ======================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# ======================
# Работа с файлами
# ======================
def load_notes():
    if os.path.exists(NOTES_FILE):
        try:
            with open(NOTES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}

def save_notes(notes_dict):
    serializable = {str(uid): notes for uid, notes in notes_dict.items()}
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}

def save_user(user_id: int, user_data: dict):
    users = load_users()
    uid_str = str(user_id)
    if uid_str not in users:
        users[uid_str] = {
            "username": user_data.get("username"),
            "first_name": user_data.get("first_name"),
            "last_name": user_data.get("last_name"),
            "first_seen": datetime.now().isoformat()
        }
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)

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
    save_user(user.id, {
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name
    })
    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n"
        "Я твой личный блокнот в Telegram.\n"
        "Используй кнопки ниже:",
        reply_markup=get_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Сохраняем пользователя при любом сообщении
    user = update.effective_user
    save_user(user.id, {
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name
    })

    text = update.message.text
    user_id = update.effective_user.id
    notes = load_notes()
    if user_id not in notes:
        notes[user_id] = []

    state = context.user_data.get("awaiting")

    if state == "add":
        if text.strip():
            notes[user_id].append(text.strip())
            save_notes(notes)
            await update.message.reply_text("✅ Заметка добавлена!")
        else:
            await update.message.reply_text("❌ Пустая заметка не сохранена.")
        context.user_data["awaiting"] = None

    elif state == "edit_index":
        try:
            index = int(text.strip()) - 1
            if 0 <= index < len(notes[user_id]):
                context.user_data["edit_index"] = index
                context.user_data["awaiting"] = "edit_content"
                await update.message.reply_text("✏️ Введите новый текст заметки:")
            else:
                await update.message.reply_text("❌ Неверный номер заметки.")
                context.user_data["awaiting"] = None
        except ValueError:
            await update.message.reply_text("❌ Введите число.")
            context.user_data["awaiting"] = None

    elif state == "edit_content":
        new_text = text.strip()
        if new_text:
            index = context.user_data["edit_index"]
            notes[user_id][index] = new_text
            save_notes(notes)
            await update.message.reply_text("✅ Заметка обновлена!")
        else:
            await update.message.reply_text("❌ Пустой текст не сохранён.")
        context.user_data["awaiting"] = None

    elif state == "delete":
        try:
            index = int(text.strip()) - 1
            if 0 <= index < len(notes[user_id]):
                deleted = notes[user_id].pop(index)
                save_notes(notes)
                await update.message.reply_text(f"🗑 Удалено: {deleted}")
            else:
                await update.message.reply_text("❌ Неверный номер заметки.")
        except ValueError:
            await update.message.reply_text("❌ Введите число.")
        context.user_data["awaiting"] = None

    elif text == "📝 Добавить":
        context.user_data["awaiting"] = "add"
        await update.message.reply_text("✏️ Введите текст новой заметки:")

    elif text == "📋 Список":
        user_notes = notes.get(user_id, [])
        if not user_notes:
            await update.message.reply_text("📭 У вас пока нет заметок.")
        else:
            msg = "Ваши заметки:\n\n"
            for i, note in enumerate(user_notes, 1):
                msg += f"{i}. {note}\n"
            await update.message.reply_text(msg)

    elif text == "✏️ Редактировать":
        user_notes = notes.get(user_id, [])
        if not user_notes:
            await update.message.reply_text("📭 Нет заметок для редактирования.")
        else:
            msg = "Введите номер заметки, которую хотите изменить:\n\n"
            for i, note in enumerate(user_notes, 1):
                msg += f"{i}. {note}\n"
            context.user_data["awaiting"] = "edit_index"
            await update.message.reply_text(msg)

    elif text == "🗑 Удалить":
        user_notes = notes.get(user_id, [])
        if not user_notes:
            await update.message.reply_text("📭 Нет заметок для удаления.")
        else:
            msg = "Введите номер заметки для удаления:\n\n"
            for i, note in enumerate(user_notes, 1):
                msg += f"{i}. {note}\n"
            context.user_data["awaiting"] = "delete"
            await update.message.reply_text(msg)

    else:
        await update.message.reply_text(
            " ❌ Используй кнопки ниже или команду /start",
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
        await update.message.reply_text(
            "Использование:\n`/send <user_id> <сообщение>`",
            parse_mode="Markdown"
        )
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

    users = load_users()
    if not users:
        await update.message.reply_text("📭 Нет зарегистрированных пользователей.")
        return

    if not context.args:
        msg = f"👥 Всего пользователей: {len(users)}\n\n"
        for uid_str, data in users.items():
            name = (data.get("first_name") or "") + " " + (data.get("last_name") or "")
            uname = f"@{data['username']}" if data.get("username") else "—"
            msg += f"{uid_str} | {name.strip()} | {uname}\n"
        await update.message.reply_text(msg)
    else:
        try:
            target_id = str(int(context.args[0]))
            if target_id not in users:
                await update.message.reply_text(f"🔍 Пользователь {target_id} не найден.")
                return

            data = users[target_id]
            name = (data.get("first_name") or "") + " " + (data.get("last_name") or "")
            uname = data.get("username") or "—"
            first_seen = data.get("first_seen", "—")
            notes = load_notes()
            note_count = len(notes.get(int(target_id), []))

            msg = (
                f"👤 Информация о пользователе\n\n"
                f"ID: {target_id}\n"
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

    print("✅ Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()



