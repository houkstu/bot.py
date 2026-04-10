import json
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)

# ====== Конфигурация ======
DATA_FILE = "residents.json"
PAYMENTS_FILE = "payments.json"
ADMIN_IDS = []  # Сюда добавьте Telegram ID администратора (можно узнать через /id)

# Реквизиты карты (замените на свои)
CARD_DETAILS = """
💳 *Реквизиты для оплаты:*

Карта: 1234 5678 9012 3456
Банк: Т-Банк
Получатель: Иванов Иван Иванович

Сумма: 1000 ₽
Назначение: Оплата уборки за месяц

❗️ После оплаты нажмите кнопку *'Я оплатил'* в боте
"""

# ====== Вспомогательные функции ======
def load_data(file_name):
    if os.path.exists(file_name):
        with open(file_name, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data, file_name):
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_current_month_key():
    now = datetime.now()
    return f"{now.year}-{now.month:02d}"

# ====== Состояния регистрации ======
NAME, ROOM = range(2)
VALID_ROOMS = [str(i) for i in range(300, 307)]

# ====== Регистрация ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data(DATA_FILE)
    
    if user_id in data:
        await show_main_menu(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "👋 Добро пожаловать! Давайте зарегистрируем вас.\n\n"
            "Введите ваше имя:"
        )
        return NAME

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

async def get_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    room = update.message.text.strip()
    if room not in VALID_ROOMS:
        await update.message.reply_text(
            "❌ Неверный номер комнаты. Допустимые значения: 300-306.\n"
            "Попробуйте снова:"
        )
        return ROOM
    
    user_id = str(update.effective_user.id)
    name = context.user_data['reg_name']
    
    data = load_data(DATA_FILE)
    data[user_id] = {
        "name": name,
        "room": room,
        "telegram_username": update.effective_user.username or "нет username"
    }
    save_data(data, DATA_FILE)
    
    await update.message.reply_text(
        f"✅ Регистрация завершена!\n\n"
        f"Имя: {name}\nКомната: {room}\n\n"
        f"Теперь вы можете оплатить уборку."
    )
    await show_main_menu(update, context)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Регистрация отменена. Для начала заново введите /start")
    return ConversationHandler.END

# ====== Главное меню ======
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💳 Оплатить уборку", callback_data="pay")],
        [InlineKeyboardButton("📋 Мои платежи", callback_data="my_payments")],
        [InlineKeyboardButton("🏠 Список жильцов", callback_data="list_residents")],
        [InlineKeyboardButton("📊 Статистика оплат", callback_data="stats")]
    ]
    
    # Добавляем админ-кнопки
    user_id = str(update.effective_user.id)
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.message.edit_text(
            "🏠 *Главное меню*\nВыберите действие:",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "🏠 *Главное меню*\nВыберите действие:",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

# ====== Оплата ======
async def process_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    payments = load_data(PAYMENTS_FILE)
    current_month = get_current_month_key()
    
    # Проверяем, оплатил ли уже в этом месяце
    if user_id in payments and current_month in payments[user_id]:
        await query.edit_message_text(
            "✅ Вы уже оплатили уборку в этом месяце!\n\n"
            "Спасибо за своевременную оплату.",
            parse_mode="Markdown"
        )
        return
    
    # Показываем реквизиты и кнопку подтверждения
    keyboard = [
        [InlineKeyboardButton("✅ Я оплатил", callback_data=f"confirm_payment_{current_month}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"{CARD_DETAILS}\n\n"
        f"📅 Платеж за: {current_month.replace('-', '.')}\n\n"
        f"После перевода нажмите кнопку ниже:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    data = load_data(DATA_FILE)
    payments = load_data(PAYMENTS_FILE)
    
    if user_id not in data:
        await query.edit_message_text("❌ Вы не зарегистрированы. Используйте /start")
        return
    
    current_month = get_current_month_key()
    
    # Сохраняем платеж
    if user_id not in payments:
        payments[user_id] = {}
    
    payments[user_id][current_month] = {
        "date": datetime.now().isoformat(),
        "amount": 1000,
        "status": "paid"
    }
    save_data(payments, PAYMENTS_FILE)
    
    # Уведомляем администратора
    resident = data[user_id]
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"💰 *Новая оплата!*\n\n"
                f"Жилец: {resident['name']}\n"
                f"Комната: {resident['room']}\n"
                f"Месяц: {current_month}\n"
                f"Сумма: 1000 ₽",
                parse_mode="Markdown"
            )
        except:
            pass
    
    await query.edit_message_text(
        f"✅ *Спасибо за оплату!*\n\n"
        f"Сумма: 1000 ₽\n"
        f"Месяц: {current_month.replace('-', '.')}\n\n"
        f"Чек сохранен. До следующего месяца!",
        parse_mode="Markdown"
    )

# ====== Мои платежи ======
async def my_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    data = load_data(DATA_FILE)
    payments = load_data(PAYMENTS_FILE)
    
    if user_id not in data:
        await query.edit_message_text("❌ Вы не зарегистрированы")
        return
    
    resident = data[user_id]
    user_payments = payments.get(user_id, {})
    
    if not user_payments:
        await query.edit_message_text(
            f"📋 *История платежей для {resident['name']}*\n\n"
            "Пока нет ни одного платежа.",
            parse_mode="Markdown"
        )
        return
    
    text = f"📋 *История платежей для {resident['name']}*\n\n"
    for month, info in sorted(user_payments.items(), reverse=True):
        date_obj = datetime.fromisoformat(info['date'])
        text += f"📅 {month.replace('-', '.')}: ✅ {info['amount']} ₽ (оплачено {date_obj.strftime('%d.%m.%Y')})\n"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)

# ====== Список жильцов ======
async def list_residents(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = load_data(DATA_FILE)
    if not data:
        await query.edit_message_text("Пока никто не зарегистрирован.")
        return
    
    rooms = {room: [] for room in VALID_ROOMS}
    for user_id, info in data.items():
        rooms[info['room']].append(info['name'])
    
    text = "🏠 *Список жильцов по комнатам:*\n\n"
    for room in VALID_ROOMS:
        if rooms[room]:
            text += f"🚪 *Комната {room}*: {', '.join(rooms[room])}\n"
        else:
            text += f"🚪 Комната {room}: (пусто)\n"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)

# ====== Статистика оплат ======
async def payment_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = load_data(DATA_FILE)
    payments = load_data(PAYMENTS_FILE)
    current_month = get_current_month_key()
    
    total_residents = len(data)
    paid_count = 0
    paid_list = []
    unpaid_list = []
    
    for user_id, resident in data.items():
        if user_id in payments and current_month in payments[user_id]:
            paid_count += 1
            paid_list.append(f"{resident['name']} (комн. {resident['room']})")
        else:
            unpaid_list.append(f"{resident['name']} (комн. {resident['room']})")
    
    text = f"📊 *Статистика оплат за {current_month.replace('-', '.')}*\n\n"
    text += f"💰 Собрано: {paid_count * 1000} ₽ из {total_residents * 1000} ₽\n"
    text += f"✅ Оплатили: {paid_count}/{total_residents} человек\n\n"
    
    if paid_list:
        text += f"*Оплатили:*\n" + "\n".join(paid_list) + "\n\n"
    if unpaid_list:
        text += f"*Не оплатили:*\n" + "\n".join(unpaid_list)
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)

# ====== Админ-панель ======
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("❌ У вас нет прав администратора.")
        return
    
    keyboard = [
        [InlineKeyboardButton("📢 Напомнить должникам", callback_data="remind_debtors")],
        [InlineKeyboardButton("📊 Полная статистика", callback_data="full_stats")],
        [InlineKeyboardButton("➕ Добавить админа", callback_data="add_admin")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "⚙️ *Админ-панель*\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def remind_debtors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = load_data(DATA_FILE)
    payments = load_data(PAYMENTS_FILE)
    current_month = get_current_month_key()
    
    debtors = []
    for user_id, resident in data.items():
        if user_id not in payments or current_month not in payments[user_id]:
            debtors.append((user_id, resident))
    
    if not debtors:
        await query.edit_message_text("✅ Все жильцы оплатили уборку в этом месяце!")
        return
    
    sent_count = 0
    for user_id, resident in debtors:
        try:
            keyboard = [[InlineKeyboardButton("💳 Оплатить сейчас", callback_data="pay")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                user_id,
                f"⚠️ *Напоминание об оплате уборки!*\n\n"
                f"Уважаемый(ая) {resident['name']}!\n"
                f"Вы еще не оплатили уборку за {current_month.replace('-', '.')}.\n"
                f"Сумма: 1000 ₽\n\n"
                f"Пожалуйста, произведите оплату как можно скорее.",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            sent_count += 1
        except Exception as e:
            print(f"Не удалось отправить сообщение {resident['name']}: {e}")
    
    await query.edit_message_text(
        f"📢 Отправлено напоминаний: {sent_count} из {len(debtors)}\n\n"
        f"Некоторым пользователям не удалось отправить сообщение (возможно, бот заблокирован)."
    )

async def full_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = load_data(DATA_FILE)
    payments = load_data(PAYMENTS_FILE)
    
    # Собираем все месяцы, за которые были платежи
    all_months = set()
    for user_payments in payments.values():
        all_months.update(user_payments.keys())
    all_months = sorted(list(all_months))
    
    if not all_months:
        await query.edit_message_text("Пока нет ни одного платежа.")
        return
    
    text = "📊 *Полная статистика по месяцам*\n\n"
    for month in all_months:
        paid_count = 0
        total_amount = 0
        for user_id, resident in data.items():
            if user_id in payments and month in payments[user_id]:
                paid_count += 1
                total_amount += 1000
        
        text += f"📅 *{month.replace('-', '.')}*: {paid_count}/{len(data)} чел. — {total_amount} ₽\n"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "👑 *Добавление администратора*\n\n"
        "Чтобы добавить нового администратора, отправьте команду:\n"
        "`/add_admin ID_пользователя`\n\n"
        "Узнать свой ID можно через команду /id",
        parse_mode="Markdown"
    )

# ====== Вспомогательные команды ======
async def show_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(f"🆔 Ваш Telegram ID: `{user_id}`", parse_mode="Markdown")

async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /add_admin <telegram_id>")
        return
    
    try:
        new_admin_id = context.args[0]
        if new_admin_id not in ADMIN_IDS:
            ADMIN_IDS.append(new_admin_id)
            await update.message.reply_text(f"✅ Пользователь {new_admin_id} добавлен в админы.")
        else:
            await update.message.reply_text("Этот пользователь уже администратор.")
    except:
        await update.message.reply_text("Ошибка при добавлении администратора.")

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_main_menu(update, context)

# ====== Ежедневная проверка и напоминания ======
async def daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Функция для автоматических напоминаний (запускается каждый день в 20:00)"""
    data = load_data(DATA_FILE)
    payments = load_data(PAYMENTS_FILE)
    current_month = get_current_month_key()
    
    # Напоминаем только после 5-го числа месяца
    if datetime.now().day < 5:
        return
    
    for user_id, resident in data.items():
        if user_id not in payments or current_month not in payments[user_id]:
            try:
                keyboard = [[InlineKeyboardButton("💳 Оплатить сейчас", callback_data="pay")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.bot.send_message(
                    user_id,
                    f"⚠️ *Ежедневное напоминание об оплате уборки!*\n\n"
                    f"Уважаемый(ая) {resident['name']}!\n"
                    f"Вы еще не оплатили уборку за {current_month.replace('-', '.')}.\n"
                    f"Сумма: 1000 ₽\n\n"
                    f"Пожалуйста, произведите оплату.",
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
            except:
                pass

# ====== Главная функция ======
def main():
    TOKEN = "8297655807:AAH5THLmX-dQGtO41gDYU6xG8V59fTWE1AY"
    
    # Добавьте сюда Telegram ID администратора (узнайте через /id)
    ADMIN_IDS.append(8476900598)  # Замените на реальный ID
    
    app = Application.builder().token(TOKEN).build()
    
    # Регистрация
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            ROOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_room)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("id", show_id))
    app.add_handler(CommandHandler("add_admin", add_admin_command))
    
    # Обработчики кнопок
    app.add_handler(CallbackQueryHandler(process_payment, pattern="^pay$"))
    app.add_handler(CallbackQueryHandler(confirm_payment, pattern="^confirm_payment_"))
    app.add_handler(CallbackQueryHandler(my_payments, pattern="^my_payments$"))
    app.add_handler(CallbackQueryHandler(list_residents, pattern="^list_residents$"))
    app.add_handler(CallbackQueryHandler(payment_stats, pattern="^stats$"))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(remind_debtors, pattern="^remind_debtors$"))
    app.add_handler(CallbackQueryHandler(full_stats, pattern="^full_stats$"))
    app.add_handler(CallbackQueryHandler(add_admin, pattern="^add_admin$"))
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern="^back_to_menu$"))
    
    # Ежедневные напоминания (в 20:00)
    job_queue = app.job_queue
    job_queue.run_daily(daily_reminder, time=datetime.strptime("20:00", "%H:%M").time())
    
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
