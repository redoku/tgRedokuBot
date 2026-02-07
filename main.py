import asyncio
import logging
import sqlite3
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# --- КОНФИГУРАЦИЯ ---
# ВНИМАНИЕ: После тестов обязательно смени токен и вебхук, так как они были в публичном чате!
BOT_TOKEN = "8424697240:AAGa3oGF2GdRp4rUqVE4Hqbw78q4Cd2UgDE"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1469657464650727609/nhQ_2yrjv7IO3aNzm_ZiOCXWCMU9dSxwEdvKaYXGuAnaDUfT8MqByMa8jc4TMgaWG631"

# Включаем логирование, чтобы видеть ошибки в консоли
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ (SQLite) ---
DB_NAME = "whitelist.db"

def init_db():
    """Создает таблицу, если её нет"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)
    conn.commit()
    conn.close()

def check_user_exists(user_id):
    """Проверяет, подавал ли пользователь заявку"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM requests WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def add_user_request(user_id, username):
    """Добавляет пользователя в базу (блокирует повторную подачу)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO requests (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()

# --- МАШИНА СОСТОЯНИЙ (FSM) ---
class WhitelistForm(StatesGroup):
    age = State()
    name = State()
    plans = State()
    source = State()
    nickname = State()

# --- КЛАВИАТУРЫ ---
def get_start_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Подать заявку")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# --- ХЕНДЛЕРЫ (ОБРАБОТЧИКИ) ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.full_name}!\n"
        "Это бот для подачи заявки на Minecraft сервер 1.21.\n"
        "Правило: 1 Telegram аккаунт = 1 Заявка.",
        reply_markup=get_start_kb()
    )

@dp.message(F.text == "Подать заявку")
async def start_process(message: types.Message, state: FSMContext):
    # 1. Проверяем базу данных
    if check_user_exists(message.from_user.id):
        await message.answer("⛔ Вы уже подавали заявку. Повторная подача невозможна.")
        return

    # 2. Если не подавал — начинаем опрос
    await state.set_state(WhitelistForm.age)
    await message.answer(
        "Начинаем анкету.\n\n"
        "1. Сколько вам лет?",
        reply_markup=ReplyKeyboardRemove() # Убираем кнопки
    )

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
    await message.answer("5. Ваш ник в Minecraft (Вводите внимательно!):")

@dp.message(WhitelistForm.nickname)
async def process_nickname(message: types.Message, state: FSMContext):
    # Сохраняем последний ответ
    await state.update_data(nickname=message.text)
    
    # Получаем все данные
    data = await state.get_data()
    
    # Формируем сообщение для Discord
    discord_message = (
        "🔔 **НОВАЯ ЗАЯВКА НА WHITELIST**\n"
        "----------------------------------\n"
        f"👤 **Telegram:** @{message.from_user.username} (ID: {message.from_user.id})\n"
        f"🎂 **Возраст:** {data['age']}\n"
        f"👋 **Имя:** {data['name']}\n"
        f"🔨 **Планы:** {data['plans']}\n"
        f"eyes **Откуда узнал:** {data['source']}\n"
        "----------------------------------\n"
        f"🎮 **НИКНЕЙМ:** `{data['nickname']}`"
    )

    # Отправляем в Discord через Webhook
    async with aiohttp.ClientSession() as session:
        webhook_data = {"content": discord_message}
        try:
            async with session.post(DISCORD_WEBHOOK_URL, json=webhook_data) as response:
                if response.status == 204 or response.status == 200:
                    # Если успешно ушло в ДС — записываем игрока в БД
                    add_user_request(message.from_user.id, message.from_user.username)
                    await message.answer("✅ Ваша заявка успешно отправлена! Ожидайте добавления в Whitelist.")
                else:
                    await message.answer(f"Ошибка при отправке заявки (Код {response.status}). Сообщите администратору.")
        except Exception as e:
            await message.answer(f"Произошла ошибка соединения: {e}")

    # Сбрасываем состояние
    await state.clear()

# --- ЗАПУСК ---
async def main():
    print("Бот запускается...")
    init_db() # Создаем базу данных при старте
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")