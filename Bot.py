# advanced_notes_bot.py
import json
import logging
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

NOTES_FILE = "notes.json"

# Загрузка заметок из файла
def load_notes():
    if os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                # Убедимся, что ключи — строки (JSON не поддерживает int-ключи)
                return {int(k): v for k, v in data.items()}
            except json.JSONDecodeError:
                return {}
    return {}

# Сохранение заметок в файл
def save_notes(notes_dict):
    # Преобразуем ключи в строки, т.к. JSON не поддерживает int как ключи объекта
    serializable = {str(uid): notes for uid, notes in notes_dict.items()}
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)

# Клавиатура
def get_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📝 Добавить"), KeyboardButton("📋 Список")],
            [KeyboardButton("✏️ Редактировать"), KeyboardButton("🗑 Удалить")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

# Состояния (для упрощения — через контекст)
# Мы не используем ConversationHandler для простоты, но будем запоминать ожидание ввода в context.user_data

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n"
        "Я твой личный блокнот в Telegram.\n"
        "Используй кнопки ниже или команды:",
        reply_markup=get_keyboard()
    )

# ------------------------------
# Обработка кнопок и команд
# ------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    notes = load_notes()

    if user_id not in notes:
        notes[user_id] = []

    # Инициализация состояния, если нужно
    state = context.user_data.get("awaiting")

    if state == "add":
        # Пользователь должен был ввести текст заметки
        if text.strip():
            notes[user_id].append(text.strip())
            save_notes(notes)
            await update.message.reply_text("✅ Заметка добавлена!")
        else:
            await update.message.reply_text("❌ Пустая заметка не сохранена.")
        context.user_data["awaiting"] = None

    elif state == "edit_index":
        # Ожидаем номер заметки для редактирования
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

    # ------------------------------
    # Основные действия по кнопкам
    # ------------------------------

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
        # Неизвестная команда
        await update.message.reply_text(
            " кнопкИспользуй кнопки ниже или команду /start",
            reply_markup=get_keyboard()
        )

def main():
    TOKEN = "8526539150:AAGPBmux72y8EQGlZydw_1N9NxuVUwv8Ukg"  # ← замени на свой!

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Запуск бота...")
    app.run_polling()

if __name__ == "__main__":

    main()

# ------------------------------
# Консоль админа
# ------------------------------

ADMIN_USER_ID = 8526539150

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

        # Отправляем сообщение от имени бота
        await context.bot.send_message(
            chat_id=target_user_id,
            text=message_text
        )
        await update.message.reply_text(f"✅ Сообщение отправлено пользователю {target_user_id}")
    except ValueError:
        await update.message.reply_text("❌ user_id должен быть числом.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
