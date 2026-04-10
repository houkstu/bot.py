import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes

# ====== Хранение данных ======
DATA_FILE = "residents.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ====== Состояния для регистрации ======
NAME, ROOM = range(2)

# Допустимые комнаты
VALID_ROOMS = [str(i) for i in range(300, 307)]

# ====== Старт / главное меню ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id in data:
        await update.message.reply_text(
            f"✅ Вы уже зарегистрированы как {data[user_id]['name']} (комната {data[user_id]['room']}).\n\n"
            "Используйте /list, чтобы увидеть всех жильцов."
        )
    else:
        await update.message.reply_text(
            "👋 Добро пожаловать! Давайте зарегистрируем вас.\n\n"
            "Введите ваше имя:"
        )
        return NAME

# ====== Регистрация: получение имени ======
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Пожалуйста, введите имя текстом.")
        return NAME
    context.user_data['reg_name'] = name
    await update.message.reply_text(
        f"Приятно познакомиться, {name}!\n"
        "Теперь укажите номер комнаты (от 300 до 306):"
    )
    return ROOM

# ====== Регистрация: получение комнаты ======
async def get_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    room = update.message.text.strip()
    if room not in VALID_ROOMS:
        await update.message.reply_text(
            "❌ Неверный номер комнаты. Допустимые значения: 300, 301, 302, 303, 304, 305, 306.\n"
            "Попробуйте снова:"
        )
        return ROOM

    user_id = str(update.effective_user.id)
    name = context.user_data['reg_name']

    data = load_data()
    data[user_id] = {
        "name": name,
        "room": room,
        "telegram_username": update.effective_user.username or "нет username"
    }
    save_data(data)

    await update.message.reply_text(
        f"✅ Регистрация завершена!\n\n"
        f"Имя: {name}\nКомната: {room}\n\n"
        f"Используйте /list, чтобы увидеть всех жильцов."
    )
    return ConversationHandler.END

# ====== Отмена регистрации ======
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Регистрация отменена. Для начала заново введите /start")
    return ConversationHandler.END

# ====== Показать всех жильцов ======
async def list_residents(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if not data:
        await update.message.reply_text("Пока никто не зарегистрирован.")
        return

    # Группировка по комнатам
    rooms = {room: [] for room in VALID_ROOMS}
    for user_id, info in data.items():
        rooms[info['room']].append(info['name'])

    text = "🏠 *Список жильцов по комнатам:*\n\n"
    for room in VALID_ROOMS:
        if rooms[room]:
            text += f"🚪 *Комната {room}*: {', '.join(rooms[room])}\n"
        else:
            text += f"🚪 Комната {room}: (пусто)\n"

    await update.message.reply_text(text, parse_mode="Markdown")

# ====== Показать мои данные ======
async def my_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data:
        await update.message.reply_text("Вы не зарегистрированы. Введите /start для регистрации.")
        return
    info = data[user_id]
    await update.message.reply_text(
        f"📋 Ваши данные:\nИмя: {info['name']}\nКомната: {info['room']}"
    )

# ====== Главная функция ======
def main():
    # Вставьте сюда токен вашего бота
    TOKEN = "8297655807:AAH5THLmX-dQGtO41gDYU6xG8V59fTWE1AY"

    app = Application.builder().token(TOKEN).build()

    # Регистрация через ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            ROOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_room)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("list", list_residents))
    app.add_handler(CommandHandler("my", my_data))

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()