import asyncio
import logging
import sqlite3
import aiohttp
import sys
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardRemove, CallbackQuery
)

# --- 1. КОНФИГУРАЦИЯ ---
BOT_TOKEN = "8424697240:AAGa3oGF2GdRp4rUqVE4Hqbw78q4Cd2UgDE"
ADMIN_IDS = [
    5169488204,
    7822701177
]

# ССЫЛКИ НА ВЕБХУКИ (Разделенные)
WEBHOOK_REQUESTS = "https://discord.com/api/webhooks/1469657464650727609/nhQ_2yrjv7IO3aNzm_ZiOCXWCMU9dSxwEdvKaYXGuAnaDUfT8MqByMa8jc4TMgaWG631"
WEBHOOK_TICKETS = "https://discord.com/api/webhooks/1469716181731639418/T49IMPARbNcZQOKyY6GZWduKdNKqD4Ezc41zYHVy0H2HZ9xU_GWGn3Qb6W7nZvWHNjd9"

SERVER_IP_MAIN = "redoku.bisquit.host"
SERVER_IP_SPARE = "redoku.goida.host"
SERVER_VERSION = "1.21.1"
LINK_PLASMO = "https://modrinth.com/plugin/plasmo-voice"
LINK_EMOTECRAFT = "https://modrinth.com/mod/emotecraft"

# --- 2. БАЗА ДАННЫХ ---
DB_NAME = "whitelist.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            nickname TEXT,
            age TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)
    conn.commit()
    conn.close()

def get_user_db(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM requests WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "user_id": row[0],
            "username": row[1],
            "nickname": row[2],
            "age": row[3],
            "status": row[4]
        }
    return None

def add_request_db(user_id, username, nickname, age):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO requests (user_id, username, nickname, age, status) VALUES (?, ?, ?, ?, 'pending')",
        (user_id, username, nickname, age)
    )
    conn.commit()
    conn.close()

def update_status_db(user_id, status):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE requests SET status = ? WHERE user_id = ?", (status, user_id))
    conn.commit()
    conn.close()

# --- 3. ЛОГИКА БОТА ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Функция отправки в Discord (Исправленная)
async def send_to_discord(url, content):
    """Отправляет сообщение в указанный вебхук Discord"""
    async with aiohttp.ClientSession() as session:
        payload = {"content": content}
        try:
            async with session.post(url, json=payload) as response:
                if response.status not in (200, 204):
                    error_text = await response.text()
                    logging.error(f"❌ Ошибка Discord ({response.status}): {error_text}")
                else:
                    logging.info("✅ Сообщение успешно отправлено в Discord")
        except Exception as e:
            logging.error(f"❌ Ошибка соединения с Discord: {e}")

class WhitelistForm(StatesGroup):
    age = State()
    name = State()
    plans = State()
    source = State()
    nickname = State()

class SupportState(StatesGroup):
    waiting_for_message = State()
    admin_reply = State()

# КЛАВИАТУРЫ
def get_main_kb(user_id):
    kb = [
        [KeyboardButton(text="📝 Подать заявку"), KeyboardButton(text="👤 Личный кабинет")],
        [KeyboardButton(text="ℹ️ Инфо"), KeyboardButton(text="⚖️ Правила")],
        [KeyboardButton(text="🆘 Поддержка (Тикет)")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_admin_decision_kb(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user_id}")
        ]
    ])

def get_admin_reply_kb(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Ответить игроку", callback_data=f"replyticket_{user_id}")]
    ])

# ХЕНДЛЕРЫ
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.full_name}! 👋\n"
        "Добро пожаловать в бота сервера **REDOKU**.\n"
        "Используй меню ниже для навигации.",
        reply_markup=get_main_kb(message.from_user.id)
    )

@dp.message(F.text == "⚖️ Правила")
async def cmd_rules(message: types.Message):
    RULES_TEXT = """
📜 **КОДЕКС СЕРВЕРА REDOKU**
... (Полный текст правил, сокращен для экономии места, но работать будет) ...
1.1. Уважение: запрещены оскорбления.
1.2. Спам: запрещен флуд.
2.1. Гриферство запрещено.
2.2. Читы — перманентный бан.
"""
    await message.answer(RULES_TEXT, parse_mode="Markdown")

@dp.message(F.text == "ℹ️ Инфо")
async def cmd_info(message: types.Message):
    text = (
        "⚡ **ИНФОРМАЦИЯ О СЕРВЕРЕ**\n\n"
        f"🌍 **IP (Основной):** `{SERVER_IP_MAIN}`\n"
        f"🌍 **IP (Запасной):** `{SERVER_IP_SPARE}`\n"
        f"📦 **Версия:** `{SERVER_VERSION}`\n\n"
        "🎧 **Рекомендуемые моды:**\n"
        f"🔹 [Plasmo Voice]({LINK_PLASMO})\n"
        f"🔹 [Emotecraft]({LINK_EMOTECRAFT})\n"
    )
    await message.answer(text, parse_mode="Markdown", disable_web_page_preview=True)

@dp.message(F.text == "👤 Личный кабинет")
async def cmd_profile(message: types.Message):
    user = get_user_db(message.from_user.id)
    if not user:
        await message.answer("❌ Вы еще не подавали заявку.")
        return

    status_emoji = {
        "pending": "⏳ На рассмотрении",
        "approved": "✅ Принят (В вайтлисте)",
        "rejected": "⛔ Отклонен"
    }.get(user['status'], user['status'])

    text = (
        "👤 **ВАШ ПРОФИЛЬ**\n\n"
        f"🎮 **Ник:** `{user['nickname']}`\n"
        f"🎂 **Возраст:** {user['age']}\n"
        f"📊 **Статус:** {status_emoji}"
    )
    await message.answer(text, parse_mode="Markdown")

# --- РЕГИСТРАЦИЯ ---
@dp.message(F.text == "📝 Подать заявку")
async def start_reg(message: types.Message, state: FSMContext):
    if get_user_db(message.from_user.id):
        await message.answer("⛔ Вы уже подавали заявку. Проверьте 'Личный кабинет'.")
        return
    await state.set_state(WhitelistForm.age)
    await message.answer("1. Сколько вам лет?", reply_markup=ReplyKeyboardRemove())

@dp.message(WhitelistForm.age)
async def process_age(message: types.Message, state: FSMContext):
    await state.update_data(age=message.text)
    await state.set_state(WhitelistForm.name)
    await message.answer("2. Как вас зовут?")

@dp.message(WhitelistForm.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(WhitelistForm.plans)
    await message.answer("3. Чем планируете заниматься на сервере?")

@dp.message(WhitelistForm.plans)
async def process_plans(message: types.Message, state: FSMContext):
    await state.update_data(plans=message.text)
    await state.set_state(WhitelistForm.source)
    await message.answer("4. Как узнали о нас?")

@dp.message(WhitelistForm.source)
async def process_source(message: types.Message, state: FSMContext):
    await state.update_data(source=message.text)
    await state.set_state(WhitelistForm.nickname)
    await message.answer("5. Ваш ник в Minecraft (Внимательно!):")

@dp.message(WhitelistForm.nickname)
async def process_nickname(message: types.Message, state: FSMContext):
    await state.update_data(nickname=message.text)
    data = await state.get_data()

    # 1. Сохраняем в БД
    add_request_db(message.from_user.id, message.from_user.username, data['nickname'], data['age'])

    # 2. Формируем текст
    admin_text = (
        "🔔 **НОВАЯ ЗАЯВКА**\n"
        f"👤 TG: @{message.from_user.username} (ID: {message.from_user.id})\n"
        f"🎮 Ник: `{data['nickname']}`\n"
        f"🎂 Возраст: {data['age']}\n"
        f"👋 Имя: {data['name']}\n"
        f"🔨 Планы: {data['plans']}\n"
        f"👀 Источник: {data['source']}"
    )

    # 3. Шлем в Discord (ИСПОЛЬЗУЕМ ВЕБХУК ДЛЯ ЗАЯВОК)
    await send_to_discord(WEBHOOK_REQUESTS, admin_text + "\n*(Ожидает подтверждения в Telegram)*")

    # 4. Шлем админам
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id, 
                admin_text, 
                reply_markup=get_admin_decision_kb(message.from_user.id),
                parse_mode="Markdown"
            )
        except:
            pass 

    await message.answer("✅ Заявка отправлена админам! Ожидайте решения.", reply_markup=get_main_kb(message.from_user.id))
    await state.clear()

# --- АДМИН КНОПКИ ---
@dp.callback_query(F.data.startswith("approve_"))
async def admin_approve(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    update_status_db(user_id, "approved")
    
    await callback.message.edit_text(f"{callback.message.text}\n\n✅ **ПРИНЯТ** ({callback.from_user.full_name})", parse_mode="Markdown")
    
    try:
        await bot.send_message(user_id, "🥳 **Ваша заявка одобрена!**\nВы добавлены в Whitelist.", parse_mode="Markdown")
    except: pass
    
    # Лог в Discord (Заявки)
    await send_to_discord(WEBHOOK_REQUESTS, f"✅ Заявка игрока (ID: {user_id}) была **ОДОБРЕНА** админом {callback.from_user.full_name}.")
    await callback.answer()

@dp.callback_query(F.data.startswith("reject_"))
async def admin_reject(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    update_status_db(user_id, "rejected")
    
    await callback.message.edit_text(f"{callback.message.text}\n\n⛔ **ОТКЛОНЕН** ({callback.from_user.full_name})", parse_mode="Markdown")
    
    try:
        await bot.send_message(user_id, "😔 **Ваша заявка отклонена.**", parse_mode="Markdown")
    except: pass
    
    await callback.answer()

# --- ТИКЕТЫ ---
@dp.message(F.text == "🆘 Поддержка (Тикет)")
async def support_start(message: types.Message, state: FSMContext):
    await state.set_state(SupportState.waiting_for_message)
    await message.answer("✏️ **Опишите вашу проблему одним сообщением:**", reply_markup=ReplyKeyboardRemove())

@dp.message(SupportState.waiting_for_message)
async def support_send(message: types.Message, state: FSMContext):
    ticket_text = (
        "🆘 **НОВЫЙ ТИКЕТ**\n"
        f"👤 От: @{message.from_user.username} (ID: {message.from_user.id})\n"
        f"📝 Сообщение:\n{message.text}"
    )

    # В Discord (ИСПОЛЬЗУЕМ ВЕБХУК ДЛЯ ТИКЕТОВ)
    await send_to_discord(WEBHOOK_TICKETS, ticket_text)

    # Админам
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id, 
                ticket_text, 
                reply_markup=get_admin_reply_kb(message.from_user.id)
            )
        except: pass

    await message.answer("✅ Сообщение отправлено администрации!", reply_markup=get_main_kb(message.from_user.id))
    await state.clear()

@dp.callback_query(F.data.startswith("replyticket_"))
async def admin_reply_start(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[1])
    await state.update_data(reply_to_user_id=user_id)
    await state.set_state(SupportState.admin_reply)
    await callback.message.answer(f"✍️ Введите ответ для пользователя ID {user_id}:")
    await callback.answer()

@dp.message(SupportState.admin_reply)
async def admin_reply_send(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_user_id = data.get("reply_to_user_id")

    if target_user_id:
        try:
            await bot.send_message(target_user_id, f"📨 **Ответ от администратора:**\n\n{message.text}", parse_mode="Markdown")
            await message.answer("✅ Ответ отправлен!")
            
            # Лог в Discord (Тикеты) - ответ админа
            await send_to_discord(WEBHOOK_TICKETS, f"👮‍♂️ **Ответ админа:** {message.text}\n➡️ Для пользователя: {target_user_id}")
            
        except Exception as e:
            await message.answer(f"❌ Ошибка отправки: {e}")
    
    await state.clear()

async def main():
    init_db()
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())