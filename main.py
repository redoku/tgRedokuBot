import asyncio
import logging
import sqlite3
import aiohttp

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove, CallbackQuery
)

from config import *

# --- ЛОГИ ---
logging.basicConfig(level=logging.INFO)

# --- БД ---
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
        "INSERT OR REPLACE INTO requests VALUES (?, ?, ?, ?, 'pending')",
        (user_id, username, nickname, age)
    )
    conn.commit()
    conn.close()

def update_status_db(user_id, status):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE requests SET status=? WHERE user_id=?", (status, user_id))
    conn.commit()
    conn.close()

# --- БОТ ---
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# --- DISCORD ---
async def send_to_discord(url, content):
    timeout = aiohttp.ClientTimeout(total=10)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json={"content": content}) as r:
                if r.status not in (200, 204):
                    logging.error(f"Discord error {r.status}")
    except Exception as e:
        logging.error(f"Discord timeout/error: {e}")

# --- FSM ---
class WhitelistForm(StatesGroup):
    age = State()
    name = State()
    plans = State()
    source = State()
    nickname = State()

# --- КЛАВИАТУРЫ ---
def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Подать заявку"),
             KeyboardButton(text="👤 Личный кабинет")],
            [KeyboardButton(text="ℹ️ Инфо"),
             KeyboardButton(text="⚖️ Правила")]
        ],
        resize_keyboard=True
    )

def admin_kb(uid):
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ Принять", callback_data=f"a_{uid}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"r_{uid}")
        ]]
    )

# --- ХЕНДЛЕРЫ ---
@dp.message(Command("start"))
async def start(m: types.Message):
    await m.answer("Добро пожаловать!", reply_markup=main_kb())

@dp.message(F.text == "👤 Личный кабинет")
async def profile(m: types.Message):
    u = get_user_db(m.from_user.id)
    if not u:
        return await m.answer("Заявки нет.")

    await m.answer(
        f"Ник: {u['nickname']}\n"
        f"Возраст: {u['age']}\n"
        f"Статус: {u['status']}"
    )

@dp.message(F.text == "📝 Подать заявку")
async def reg_start(m: types.Message, s: FSMContext):
    if get_user_db(m.from_user.id):
        return await m.answer("Вы уже подавали заявку.")

    await s.set_state(WhitelistForm.age)
    await m.answer("Возраст?", reply_markup=ReplyKeyboardRemove())

@dp.message(WhitelistForm.age)
async def age(m: types.Message, s: FSMContext):
    await s.update_data(age=m.text)
    await s.set_state(WhitelistForm.name)
    await m.answer("Имя?")

@dp.message(WhitelistForm.name)
async def name(m: types.Message, s: FSMContext):
    await s.update_data(name=m.text)
    await s.set_state(WhitelistForm.plans)
    await m.answer("Планы?")

@dp.message(WhitelistForm.plans)
async def plans(m: types.Message, s: FSMContext):
    await s.update_data(plans=m.text)
    await s.set_state(WhitelistForm.source)
    await m.answer("Откуда узнал?")

@dp.message(WhitelistForm.source)
async def source(m: types.Message, s: FSMContext):
    await s.update_data(source=m.text)
    await s.set_state(WhitelistForm.nickname)
    await m.answer("Ник Minecraft?")

@dp.message(WhitelistForm.nickname)
async def finish(m: types.Message, s: FSMContext):
    d = await s.get_data()
    nick = m.text

    add_request_db(m.from_user.id, m.from_user.username, nick, d["age"])

    text = (
        f"Новая заявка\n"
        f"@{m.from_user.username}\n"
        f"Ник: {nick}\n"
        f"Возраст: {d['age']}"
    )

    await send_to_discord(DISCORD_WEBHOOK_URL, text)

    for admin in ADMIN_IDS:
        await bot.send_message(admin, text, reply_markup=admin_kb(m.from_user.id))

    await m.answer("Заявка отправлена!", reply_markup=main_kb())
    await s.clear()

@dp.callback_query(F.data.startswith("a_"))
async def approve(c: CallbackQuery):
    uid = int(c.data.split("_")[1])
    update_status_db(uid, "approved")
    await bot.send_message(uid, "Заявка одобрена!")
    await c.answer("Принято")

@dp.callback_query(F.data.startswith("r_"))
async def reject(c: CallbackQuery):
    uid = int(c.data.split("_")[1])
    update_status_db(uid, "rejected")
    await bot.send_message(uid, "Заявка отклонена.")
    await c.answer("Отклонено")

# --- СТАРТ ---
async def main():
    init_db()

    # УДАЛЯЕМ WEBHOOK (фикс конфликтов)
    await bot.delete_webhook(drop_pending_updates=True)

    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
