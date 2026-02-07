# main.py
import asyncio
import logging
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

# Импортируем наши настройки и базу данных
import config
import database

# Настройка логов
logging.basicConfig(level=logging.INFO)
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# --- ТЕКСТ ПРАВИЛ ---
RULES_TEXT = """
📜 **КОДЕКС СЕРВЕРА REDOKU**

💬 **1. Общение и чат**
1.1. Уважение: запрещены оскорбления, токсичность, буллинг.
1.2. Спам: запрещен флуд, КАПС (>50%), реклама.

💣 **2. Гриферство и Читы**
2.1. Гриферство: запрещено ломать чужое, воровать, убивать в приватах.
2.2. Читы (X-Ray, KillAura, Fly и др.) — ⛔ **Перманентный бан**.
2.3. Лаг-машины запрещены.
2.4. Отказ от проверки = Бан.

🧩 **3. Модификации**
✅ Разрешено: Litematica (без принтера), MiniHUD, Sodium, Iris, ReplayMod, Inventory HUD+, AppleSkin.
❌ Запрещено: X-Ray, Baritone, KillAura, FreeCam (для поиска), AutoClicker.

⚖️ **Наказания:** от мута до вечного бана.
"""

# --- МАШИНА СОСТОЯНИЙ (FSM) ---
class WhitelistForm(StatesGroup):
    age = State()
    name = State()
    plans = State()
    source = State()
    nickname = State()

class SupportState(StatesGroup):
    waiting_for_message = State()
    admin_reply = State() # Состояние для админа, когда он отвечает

# --- КЛАВИАТУРЫ ---
def get_main_kb(user_id):
    """Главное меню"""
    kb = [
        [KeyboardButton(text="📝 Подать заявку"), KeyboardButton(text="👤 Личный кабинет")],
        [KeyboardButton(text="ℹ️ Инфо"), KeyboardButton(text="⚖️ Правила")],
        [KeyboardButton(text="🆘 Поддержка (Тикет)")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_admin_decision_kb(user_id):
    """Кнопки под заявкой для админа"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user_id}")
        ]
    ])

def get_admin_reply_kb(user_id):
    """Кнопка ответа на тикет для админа"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Ответить игроку", callback_data=f"replyticket_{user_id}")]
    ])

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
async def send_discord_log(content):
    """Отправка логов в Discord"""
    async with aiohttp.ClientSession() as session:
        try:
            await session.post(config.DISCORD_WEBHOOK_URL, json={"content": content})
        except Exception as e:
            logging.error(f"Discord Error: {e}")

# --- ХЕНДЛЕРЫ: СТАРТ И МЕНЮ ---

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
    await message.answer(RULES_TEXT, parse_mode="Markdown")

@dp.message(F.text == "ℹ️ Инфо")
async def cmd_info(message: types.Message):
    text = (
        "⚡ **ИНФОРМАЦИЯ О СЕРВЕРЕ**\n\n"
        f"🌍 **IP (Основной):** `{config.SERVER_IP_MAIN}`\n"
        f"🌍 **IP (Запасной):** `{config.SERVER_IP_SPARE}`\n"
        f"📦 **Версия:** `{config.SERVER_VERSION}`\n\n"
        "🎧 **Рекомендуемые моды:**\n"
        f"🔹 [Plasmo Voice]({config.LINK_PLASMO})\n"
        f"🔹 [Emotecraft]({config.LINK_EMOTECRAFT})\n"
    )
    await message.answer(text, parse_mode="Markdown", disable_web_page_preview=True)

@dp.message(F.text == "👤 Личный кабинет")
async def cmd_profile(message: types.Message):
    user = database.get_user(message.from_user.id)
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

# --- ХЕНДЛЕРЫ: РЕГИСТРАЦИЯ ---

@dp.message(F.text == "📝 Подать заявку")
async def start_reg(message: types.Message, state: FSMContext):
    user = database.get_user(message.from_user.id)
    if user:
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

    # 1. Сохраняем в БД со статусом pending
    database.add_request(message.from_user.id, message.from_user.username, data['nickname'], data['age'])

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

    # 3. Шлем в Discord
    await send_discord_log(admin_text + "\n*(Ожидает подтверждения в Telegram)*")

    # 4. Шлем админам в TG с кнопками
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id, 
                admin_text, 
                reply_markup=get_admin_decision_kb(message.from_user.id),
                parse_mode="Markdown"
            )
        except:
            pass # Если админ заблочил бота

    await message.answer("✅ Заявка отправлена админам! Ожидайте решения.", reply_markup=get_main_kb(message.from_user.id))
    await state.clear()

# --- ХЕНДЛЕРЫ: АДМИНСКИЕ КНОПКИ (ПРИНЯТЬ/ОТКЛОНИТЬ) ---

@dp.callback_query(F.data.startswith("approve_"))
async def admin_approve(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    database.update_status(user_id, "approved")
    
    # Редактируем сообщение у админа
    await callback.message.edit_text(
        f"{callback.message.text}\n\n✅ **ПРИНЯТ** (Админ: {callback.from_user.full_name})", 
        reply_markup=None, parse_mode="Markdown"
    )
    
    # Уведомляем игрока
    try:
        await bot.send_message(user_id, "🥳 **Поздравляем! Ваша заявка одобрена!**\nВы добавлены в Whitelist.\nПриятной игры!", parse_mode="Markdown")
        # Тут можно добавить логику RCON для автоматического добавления на сервере
    except:
        pass
    
    await send_discord_log(f"✅ Заявка игрока (ID: {user_id}) была **ОДОБРЕНА** админом {callback.from_user.full_name}.")
    await callback.answer()

@dp.callback_query(F.data.startswith("reject_"))
async def admin_reject(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    database.update_status(user_id, "rejected")
    
    await callback.message.edit_text(
        f"{callback.message.text}\n\n⛔ **ОТКЛОНЕН** (Админ: {callback.from_user.full_name})", 
        reply_markup=None, parse_mode="Markdown"
    )
    
    try:
        await bot.send_message(user_id, "😔 **Ваша заявка отклонена.**\nВозможно, анкета заполнена некорректно.", parse_mode="Markdown")
    except:
        pass
    
    await callback.answer()

# --- ХЕНДЛЕРЫ: ПОДДЕРЖКА (ТИКЕТЫ) ---

@dp.message(F.text == "🆘 Поддержка (Тикет)")
async def support_start(message: types.Message, state: FSMContext):
    await state.set_state(SupportState.waiting_for_message)
    await message.answer(
        "✏️ **Напишите ваше сообщение администрации:**\n"
        "(Опишите проблему, жалобу или вопрос одним сообщением)",
        reply_markup=ReplyKeyboardRemove()
    )

@dp.message(SupportState.waiting_for_message)
async def support_send(message: types.Message, state: FSMContext):
    ticket_text = (
        "🆘 **НОВЫЙ ТИКЕТ**\n"
        f"👤 От: @{message.from_user.username} (ID: {message.from_user.id})\n"
        f"📝 Сообщение:\n{message.text}"
    )

    # В Discord
    await send_discord_log(ticket_text)

    # Админам
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id, 
                ticket_text, 
                reply_markup=get_admin_reply_kb(message.from_user.id)
            )
        except:
            pass

    await message.answer("✅ Сообщение отправлено администрации!", reply_markup=get_main_kb(message.from_user.id))
    await state.clear()

# Ответ админа на тикет
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
            await bot.send_message(
                target_user_id,
                f"📨 **Ответ от администратора:**\n\n{message.text}",
                parse_mode="Markdown"
            )
            await message.answer("✅ Ответ отправлен!")
            # Лог в ДС
            await send_discord_log(f"👮‍♂️ **Ответ админа:** {message.text}\n➡️ Для пользователя: {target_user_id}")
        except Exception as e:
            await message.answer(f"❌ Ошибка отправки (пользователь заблокировал бота?): {e}")
    
    await state.clear()

# --- ЗАПУСК ---
async def main():
    database.init_db()
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())