import logging
import json
import requests
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ✅ Конфигурация
BOT_TOKEN = "8101750587:AAEoO1Aote7wHIRDADD4kpwFyYOYIkibe_c"
AIRTABLE_API_KEY = "patZ7hX8W8F8apmJm.9adf2ed71f8925dd372af08a5b5af2af4b12ead4abc0036be4ea68c43c47a8c4"
AIRTABLE_BASE_ID = "appTpq4tdeQ27uxQ9"
AIRTABLE_TABLE_NAME = "Tasks"
AIRTABLE_URL = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

contact_messages = {}

# ✅ /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🚀 Открыть STUDENTUS", web_app=WebAppInfo(url="https://grud1807.github.io/tg-webapp/"))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Добро пожаловать в STUDENTUS!\n\nНажмите кнопку ниже, чтобы открыть платформу 👇",
        reply_markup=reply_markup
    )

# ✅ Обработка WebApp данных
async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = json.loads(update.effective_message.web_app_data.data)
        user = update.effective_user

        deadline = f"2025-{data['deadline'][3:5]}-{data['deadline'][0:2]}"

        fields = {
            "Предмет": data['subject'],
            "Описание": data['description'],
            "Цена": float(data['price']),
            "Дедлайн": deadline,
            "Статус": "Новое",
            "ID пользователя": user.id,
            "Пользователь Telegram": user.username or "без username",
            "Подтверждение заказчика": "Нет",
            "Подтверждение исполнителя": "Нет"
        }

        headers = {
            "Authorization": f"Bearer {AIRTABLE_API_KEY}",
            "Content-Type": "application/json"
        }

        response = requests.post(AIRTABLE_URL, headers=headers, json={"fields": fields})

        if response.status_code in [200, 201]:
            await update.message.reply_text("✅ Задание успешно добавлено!\nОжидайте, пока исполнитель возьмёт его в работу.")
        else:
            logger.error(f"Airtable error: {response.text}")
            await update.message.reply_text("❌ Ошибка при добавлении. Попробуйте позже.")
    except Exception as e:
        logger.exception("Ошибка обработки WebApp данных")
        await update.message.reply_text("⚠️ Ошибка. Попробуйте снова.")

# ✅ Подтверждение выполнения
async def confirm_completion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split(":")
    record_id = data[1]
    user_type = data[2]
    user_id = query.from_user.id

    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }

    task_url = f"{AIRTABLE_URL}/{record_id}"
    resp = requests.get(task_url, headers=headers)
    if resp.status_code != 200:
        await query.edit_message_text("❌ Ошибка при получении задания.")
        return

    fields = resp.json().get("fields", {})
    update_fields = {}

    if user_type == "customer":
        update_fields["Подтверждение заказчика"] = "Да"
    elif user_type == "executor":
        update_fields["Подтверждение исполнителя"] = "Да"

    # Обновляем подтверждение
    requests.patch(task_url, headers=headers, json={"fields": update_fields})

    # Если оба подтвердили
    if fields.get("Подтверждение заказчика") == "Да" and fields.get("Подтверждение исполнителя") == "Да":
        requests.patch(task_url, headers=headers, json={"fields": {"Статус": "Завершено"}})

        for uid in ["ID заказчика", "ID исполнителя"]:
            uid_value = fields.get(uid)
            if uid_value and uid_value in contact_messages:
                try:
                    await context.bot.delete_message(chat_id=uid_value, message_id=contact_messages[uid_value])
                except Exception as e:
                    logger.warning(f"❗️Ошибка удаления сообщения: {e}")

        await query.edit_message_text("✅ Оба подтвердили выполнение. Задание завершено.")
    else:
        await query.edit_message_text("✅ Подтверждение получено. Ожидаем вторую сторону.")

# ✅ Обмен контактами
async def send_contacts(executor_id, executor_username, customer_id, customer_username, record_id, context):
    msg1 = await context.bot.send_message(
        chat_id=executor_id,
        text=f"📞 Свяжитесь с заказчиком: @{customer_username}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Подтвердить выполнение", callback_data=f"confirm:{record_id}:executor")
        ]])
    )
    contact_messages[executor_id] = msg1.message_id

    msg2 = await context.bot.send_message(
        chat_id=customer_id,
        text=f"📞 Ваше задание выполняет: @{executor_username}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Подтвердить выполнение", callback_data=f"confirm:{record_id}:customer")
        ]])
    )
    contact_messages[customer_id] = msg2.message_id

# ✅ Запуск
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    app.add_handler(CallbackQueryHandler(confirm_completion))

    logging.info("🚀 Бот запущен")
    app.run_polling()
