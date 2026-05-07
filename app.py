import asyncio
import random
import os
import time
import json
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ForceReply

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.environ.get('BOT_TOKEN')
STATS_FILE = "stats.json"

def get_ids(env_name):
    data = os.environ.get(env_name, "")
    return [int(i.strip()) for i in data.split(",") if i.strip().replace("-", "").isdigit()]

ALLOWED_GROUPS = get_ids('ALLOWED_GROUPS')
ALLOWED_USERS = get_ids('ALLOWED_USERS')

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- РАБОТА С БАЗОЙ ДАННЫХ ---
def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_stats(stats_data):
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ошибка сохранения: {e}")

USER_MESSAGES = load_stats()

# --- ТЕКСТОВЫЕ ДАННЫЕ ---
AURA_QUOTES = [
    "Конечно", "А как иначе", "Черт возьми", "Делаем", "На колени", 
    "Возможно", "Это победа", "Легенда", "Внатуре", "Это реально круто", 
    "Естественно", "Потихоньку", "Дай Бог", "Я это запомню", "Мед по телу"
]

YES_NO_ANSWERS = [
    "Я думаю, что ДА", "Скорее всего, ДА", "Конечно, ДА", "Однозначно ДА", 
    "Я думаю, что НЕТ", "Скорее всего, НЕТ", "Точно НЕТ", "Спроси позже", 
    "Мои сенсоры говорят - ДА", "Звезды нашептали - НЕТ"
]

BAD_WORDS = ["хуй", "пизд", "ебла", "сук", "бля", "гандон", "даун", "шлюх", "уеб", "чмо"]

SHAME_VARIATIONS = [
    "С такими выражениями твоя аура начнет сыпаться уже в 35 лет", 
    "Из-за этих слов твоя аура только что потемнела", 
    "Маты загрязняют твою ауру"
]

HELP_TEXT = (
    "✨ <b>Я Аура!</b> ✨\n\n"
    "<b>💎 ЭКОНОМИКА:</b>\n"
    "⛏ <code>Аура фарм</code> — раз в 3 часа\n"
    "💰 <code>Аура баланс</code> — твой кошелек\n"
    "🛒 <code>Аура магазин</code> — меню и переводы\n\n"
    "<b>🔮 КОМАНДЫ:</b>\n"
    "🔮 Вероятность | 🎱 Да/Нет | ⚖️ Выбор\n"
    "📊 Стата | 💬 Фраза | 🍀 Удача\n"
    "🎲 Кости | ⏳ Таймер | 📢 Сбор"
)

# --- КЛАВИАТУРЫ ---
def get_main_kb():
    keyboard = [
        [InlineKeyboardButton(text="⛏ Фарм (Раз в 3ч)", callback_data="farm_aura")],
        [InlineKeyboardButton(text="🛒 Магазин", callback_data="open_shop")],
        [InlineKeyboardButton(text="💎 Баланс", callback_data="check_balance")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_shop_kb():
    keyboard = [
        [InlineKeyboardButton(text="🎖 Админка (5000💎)", callback_data="buy_admin")],
        [InlineKeyboardButton(text="🏷 Сменить тег (500💎)", callback_data="buy_tag")],
        [InlineKeyboardButton(text="💸 Перевести 💎", callback_data="transfer_start")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- ОБРАБОТКА КНОПОК (CALLBACKS) ---
@dp.callback_query(F.data == "farm_aura")
async def cb_farm(callback: CallbackQuery):
    uid = str(callback.from_user.id)
    if int(uid) not in ALLOWED_USERS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    now = time.time()
    user_data = USER_MESSAGES.get(uid, {"balance": 0, "last_farm": 0})
    wait_seconds = 10800 # 3 часа

    if now - user_data.get("last_farm", 0) < wait_seconds:
        remaining = int((wait_seconds - (now - user_data["last_farm"])) // 60)
        await callback.answer(f"⏳ Жди {remaining // 60}ч {remaining % 60}мин", show_alert=True)
        return

    reward = random.randint(50, 400)
    USER_MESSAGES[uid]["balance"] = user_data.get("balance", 0) + reward
    USER_MESSAGES[uid]["last_farm"] = now
    save_stats(USER_MESSAGES)

    await callback.message.answer(f"⛏ +{reward} 💎! Баланс: {USER_MESSAGES[uid]['balance']}")
    await callback.answer()

@dp.callback_query(F.data == "check_balance")
async def cb_bal(callback: CallbackQuery):
    uid = str(callback.from_user.id)
    is_owner = int(uid) == ALLOWED_USERS[0]
    balance = "∞" if is_owner else USER_MESSAGES.get(uid, {}).get("balance", 0)
    await callback.answer(f"Твой баланс: {balance} 💎", show_alert=True)

@dp.callback_query(F.data == "open_shop")
async def cb_shop(callback: CallbackQuery):
    await callback.message.edit_text("🛒 <b>Магазин Ауры</b>", reply_markup=get_shop_kb())

@dp.callback_query(F.data == "back_to_main")
async def cb_back(callback: CallbackQuery):
    await callback.message.edit_text(HELP_TEXT, reply_markup=get_main_kb())

@dp.callback_query(F.data == "buy_admin")
async def cb_buy_admin(callback: CallbackQuery):
    await callback.message.answer("📝 Введи текст для админки (ответь на это сообщение):", reply_markup=ForceReply(selective=True))
    await callback.answer()

@dp.callback_query(F.data == "buy_tag")
async def cb_buy_tag(callback: CallbackQuery):
    await callback.message.answer("🏷 Введи новый тег (ответь на это сообщение):", reply_markup=ForceReply(selective=True))
    await callback.answer()

@dp.callback_query(F.data == "transfer_start")
async def cb_transfer(callback: CallbackQuery):
    await callback.message.answer("💸 <b>Перевод Ауры:</b>\nОтветь на сообщение того, кому хочешь перевести, и напиши сумму цифрами.", reply_markup=ForceReply(selective=True))
    await callback.answer()

# --- ОСНОВНОЙ ОБРАБОТЧИК СООБЩЕНИЙ ---
@dp.message(F.chat.id.in_(ALLOWED_GROUPS), F.text)
async def main_handler(message: types.Message):
    text_lower = message.text.lower()
    uid = str(message.from_user.id)
    now = time.time()
    is_owner = int(uid) == ALLOWED_USERS[0]

    # Инициализация пользователя
    if uid not in USER_MESSAGES:
        USER_MESSAGES[uid] = {"name": message.from_user.first_name, "times": [], "balance": 0, "last_farm": 0}
    
    USER_MESSAGES[uid]["times"].append(now)
    USER_MESSAGES[uid]["name"] = message.from_user.first_name
    save_stats(USER_MESSAGES)

    # 1. ОБРАБОТКА ОТВЕТОВ (ПОКУПКИ И ПЕРЕВОДЫ)
    if message.reply_to_message:
        reply_user = message.reply_to_message.from_user
        reply_text = message.reply_to_message.text
        input_val = message.text.strip()

        # Если отвечаем боту (Покупка в магазине)
        if reply_user.id == (await bot.get_me()).id:
            if "текст для админки" in reply_text or "новый тег" in reply_text:
                price = 5000 if "админки" in reply_text else 500
                
                if not is_owner and USER_MESSAGES[uid]["balance"] < price:
                    await message.reply("❌ Недостаточно 💎"); return

                try:
                    if "админки" in reply_text:
                        await bot.promote_chat_member(message.chat.id, int(uid), can_manage_chat=True)
                    
                    await bot.set_chat_administrator_custom_title(message.chat.id, int(uid), input_val)
                    
                    if not is_owner:
                        USER_MESSAGES[uid]["balance"] -= price
                    
                    save_stats(USER_MESSAGES)
                    await message.reply(f"✅ Готово! Твой тег: <b>{input_val}</b>")
                except:
                    await message.reply("❌ Ошибка прав. Бот должен быть админом.")
                return

        # Если отвечаем пользователю (Перевод денег)
        elif input_val.isdigit() and not reply_user.is_bot:
            amount = int(input_val)
            target_id = str(reply_user.id)

            if amount <= 0: return
            if target_id == uid:
                await message.reply("Нельзя переводить самому себе!"); return
            
            if not is_owner and USER_MESSAGES[uid]["balance"] < amount:
                await message.reply("❌ У тебя нет столько 💎"); return

            # Авто-регистрация получателя
            if target_id not in USER_MESSAGES:
                USER_MESSAGES[target_id] = {"name": reply_user.first_name, "times": [], "balance": 0, "last_farm": 0}

            if not is_owner:
                USER_MESSAGES[uid]["balance"] -= amount
            
            USER_MESSAGES[target_id]["balance"] += amount
            save_stats(USER_MESSAGES)
            await message.reply(f"💸 Перевод выполнен!\n<b>{amount}</b> 💎 отправлено {USER_MESSAGES[target_id]['name']}.")
            return

    # 2. КОМАНДЫ НАЧИНАЮЩИЕСЯ С "АУРА"
    if text_lower.startswith("аура"):
        if int(uid) not in ALLOWED_USERS: return

        if text_lower == "аура фарм":
            u_data = USER_MESSAGES[uid]
            if now - u_data["last_farm"] < 10800:
                rem = int((10800 - (now - u_data["last_farm"])) // 60)
                await message.reply(f"⏳ Жди {rem // 60}ч {rem % 60}м")
            else:
                rew = random.randint(50, 400)
                u_data["balance"] += rew
                u_data["last_farm"] = now
                save_stats(USER_MESSAGES)
                await message.reply(f"⛏ +{rew} 💎! Баланс: {u_data['balance']}")

        elif text_lower == "аура баланс":
            bal = "∞" if is_owner else USER_MESSAGES[uid].get("balance", 0)
            await message.reply(f"💎 Баланс: <b>{bal}</b>")

        elif text_lower == "аура магазин":
            await message.reply("🛒 <b>Магазин Ауры</b>", reply_markup=get_shop_kb())

        elif "стата" in text_lower:
            stats_list = sorted(
                [(d["name"], sum(1 for t in d["times"] if (now-t) <= 86400)) for d in USER_MESSAGES.values()],
                key=lambda x: x[1], reverse=True
            )
            top_text = "📊 <b>Топ за сутки:</b>\n" + "\n".join([f"{i}. {n} — {c}" for i, (n, c) in enumerate(stats_list[:10], 1)])
            await message.answer(top_text)

        elif "команды" in text_lower:
            await message.reply(HELP_TEXT, reply_markup=get_main_kb())

        elif "вероятность" in text_lower:
            await message.reply(f"🔮 Вероятность: <b>{random.randint(0, 100)}%</b>")

        elif "да нет" in text_lower:
            await message.reply(f"🎱 Ответ: <b>{random.choice(YES_NO_ANSWERS)}</b>")

        elif "выбор" in text_lower:
            options = text_lower.replace("аура выбор", "").split(" или ")
            if len(options) > 1:
                await message.reply(f"⚖️ Выбор: <b>{random.choice(options).strip()}</b>")

        elif "удач" in text_lower:
            await message.reply(f"🍀 Удача: <b>{random.randint(0, 100)}%</b>")

        elif "фраз" in text_lower:
            await message.reply(f"💬 <b>{random.choice(AURA_QUOTES)}</b>")

        elif "кости" in text_lower:
            await message.reply(f"🎲 Кости: <b>{random.randint(1, 6)}</b>")

        elif "сбор" in text_lower:
            mentions = "".join([f'<a href="tg://user?id={tid}">\u2063</a>' for tid in ALLOWED_USERS])
            await message.answer(f"📢 <b>Общий сбор!</b>{mentions}")

        elif "таймер" in text_lower:
            try:
                seconds = int(text_lower.split()[2])
                await message.reply(f"⏳ Таймер на {seconds}с.")
                await asyncio.sleep(seconds)
                await message.answer(f"🔔 {message.from_user.first_name}, время вышло!")
            except: pass

    # 3. ФИЛЬТР МАТОВ
    if any(word in text_lower for word in BAD_WORDS):
        if random.random() < 0.2:
            await message.reply(random.choice(SHAME_VARIATIONS))

# --- ЗАПУСК WEB-СЕРВЕРА И БОТА ---
async def handle(request):
    return web.Response(text="Aura is running!")

async def main():
    # Настройка Web-сервера для Render (чтобы не падал деплой)
    app = web.Application()
    app.router.add_get('/', handle)
    
    # Запуск сервера в отдельной задаче
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080)))
    await site.start()
    
    # Запуск Telegram бота
    print("Бот запущен...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен.")
