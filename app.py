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

# --- НАСТРОЙКИ ---
TOKEN = os.environ.get('BOT_TOKEN')
STATS_FILE = "stats.json"

def get_ids(env_name):
    data = os.environ.get(env_name, "")
    return [int(i.strip()) for i in data.split(",") if i.strip().replace("-", "").isdigit()]

ALLOWED_GROUPS = get_ids('ALLOWED_GROUPS')
ALLOWED_USERS = get_ids('ALLOWED_USERS')

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- РАБОТА С ДАННЫМИ ---
def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception: return {}
    return {}

def save_stats(stats_data):
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats_data, f, ensure_ascii=False, indent=4)
    except Exception as e: print(f"Ошибка сохранения: {e}")

USER_MESSAGES = load_stats()
LAST_ANSWERS = {}

# --- СПИСКИ ---
AURA_QUOTES = ["Конечно", "А как иначе", "Черт возьми", "А когда не делали", "Делаем", "На колени", "Возможно", "Это победа", "Легенда", "Внатуре", "Это реально круто", "Естественно", "Че они там курят", "Потихоньку", "Дай Бог", "Я это запомню", "Я это не запомню", "Я не мафия", "Я мафия", "Я тебе доверяю", "Вам че денег дать", "Че она несет", "Мед по телу"]
YES_NO_ANSWERS = ["Я думаю, что ДА", "Скорее всего, ДА", "Конечно, ДА", "Однозначно ДА", "Я думаю, что НЕТ", "Скорее всего, НЕТ", "Точно НЕТ", "Вообще без вариантов, НЕТ", "Спроси позже", "Мои сенсоры говорят - ДА", "Звезды нашептали - НЕТ"]
REPEAT_PHRASES = ["Я повторяюсь... Ответ: ", "Склероз? Я уже говорила: ", "Я же только что отвечала: ", "Мое мнение не изменилось: "]
AURA_VALUES = [67, 34, 69, 89, 322, 42, 52, 82, 1488, 228, "пульсирует синим", "позорище", "пронырливая", "скудная", "невероятная", "бесконечная", "грязная", "чистая"]
BAD_WORDS = ["хуй", "пизд", "ебла", "сук", "бля", "гандон", "даун", "шлюх", "уеб", "чмо"]

HELP_TEXT = (
    "✨ <b>Я Аура - ваш легендарный бот!</b> ✨\n\n"
    "<b>💎 ЭКОНОМИКА:</b>\n"
    "⛏ <code>Аура фарм</code> — добыть очки\n"
    "💰 <code>Аура баланс</code> — твой кошелек\n"
    "🛒 <code>Аура магазин</code> — меню покупок\n\n"
    "<b>🔮 КОМАНДЫ:</b>\n"
    "🔮 <code>Аура вероятность [текст]</code>\n"
    "🎱 <code>Аура да нет [вопрос]</code>\n"
    "⚖️ <code>Аура выбор [1] или [2]</code>\n"
    "📊 <code>Аура стата [час/сутки]</code>\n"
    "💬 <code>Аура фраза</code> | 🍀 <code>Аура удача</code>\n"
    "🎲 <code>Аура кости</code> | ⏳ <code>Аура таймер [сек]</code>\n"
    "📢 <code>Аура сбор</code> | 📜 <code>Аура команды</code>"
)

# --- КНОПКИ ---
def get_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⛏ Фарм Ауры", callback_data="farm_aura")],
        [InlineKeyboardButton(text="🛒 Магазин", callback_data="open_shop")],
        [InlineKeyboardButton(text="💎 Баланс", callback_data="check_balance")]
    ])

def get_shop_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎖 Купить админку (5000💎)", callback_data="buy_admin")],
        [InlineKeyboardButton(text="🏷 Сменить тег (500💎)", callback_data="buy_tag")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")]
    ])

# --- ОБРАБОТЧИКИ CALLBACK ---
@dp.callback_query(F.data == "farm_aura")
async def cb_farm(callback: CallbackQuery):
    uid = str(callback.from_user.id)
    if int(uid) not in ALLOWED_USERS:
        await callback.answer("Тебя нет в списке!", show_alert=True); return
    now = time.time()
    user_data = USER_MESSAGES.get(uid, {"balance": 0, "last_farm": 0})
    if now - user_data.get("last_farm", 0) < 10800:
        await callback.answer(f"⏳ Жди {int((10800-(now-user_data['last_farm']))//60)} мин.", show_alert=True); return
    reward = random.randint(10, 300)
    USER_MESSAGES[uid]["balance"] = user_data.get("balance", 0) + reward
    USER_MESSAGES[uid]["last_farm"] = now
    save_stats(USER_MESSAGES)
    await callback.message.answer(f"⛏ <b>{callback.from_user.first_name}</b>, +<b>{reward}</b> 💎\nБаланс: <b>{USER_MESSAGES[uid]['balance']}</b>")
    await callback.answer()

@dp.callback_query(F.data == "check_balance")
async def cb_bal(callback: CallbackQuery):
    uid = str(callback.from_user.id)
    is_owner = int(uid) == ALLOWED_USERS[0]
    bal = "∞" if is_owner else USER_MESSAGES.get(uid, {}).get("balance", 0)
    await callback.answer(f"Твой баланс: {bal} 💎", show_alert=True)

@dp.callback_query(F.data == "open_shop")
async def cb_shop(callback: CallbackQuery):
    await callback.message.edit_text("🛒 <b>Магазин Ауры</b>\nВыбери товар:", reply_markup=get_shop_kb())

@dp.callback_query(F.data == "back_to_main")
async def cb_back(callback: CallbackQuery):
    await callback.message.edit_text(HELP_TEXT, reply_markup=get_main_kb())

@dp.callback_query(F.data == "buy_admin")
async def cb_buy_admin(callback: CallbackQuery):
    await callback.message.answer("📝 Введи желаемый тег для админки (до 16 символов):", reply_markup=ForceReply(selective=True))
    await callback.answer()

@dp.callback_query(F.data == "buy_tag")
async def cb_buy_tag(callback: CallbackQuery):
    await callback.message.answer("🏷 Введи новый тег для изменения:", reply_markup=ForceReply(selective=True))
    await callback.answer()

# --- ОСНОВНОЙ ОБРАБОТЧИК ---
@dp.message(F.chat.id.in_(ALLOWED_GROUPS), F.text)
async def main_group_handler(message: types.Message):
    msg_text = message.text.lower()
    uid = str(message.from_user.id)
    uname = message.from_user.first_name
    now = time.time()
    is_owner = int(uid) == ALLOWED_USERS[0]

    # Инициализация юзера
    if uid not in USER_MESSAGES:
        USER_MESSAGES[uid] = {"name": uname, "times": [], "balance": 0, "last_farm": 0}
    USER_MESSAGES[uid]["times"].append(now)
    USER_MESSAGES[uid]["name"] = uname
    save_stats(USER_MESSAGES)

    # Обработка ответов (ForceReply) на покупку
    if message.reply_to_message and message.reply_to_message.from_user.id == (await bot.get_me()).id:
        reply_text = message.reply_to_message.text
        title = message.text.strip()
        
        if "желаемый тег для админки" in reply_text:
            price = 5000
            if not is_owner and USER_MESSAGES[uid]["balance"] < price:
                await message.reply("❌ Недостаточно 💎"); return
            try:
                await bot.promote_chat_member(chat_id=message.chat.id, user_id=int(uid), can_manage_chat=True)
                await bot.set_chat_administrator_custom_title(chat_id=message.chat.id, user_id=int(uid), custom_title=title)
                if not is_owner: USER_MESSAGES[uid]["balance"] -= price
                save_stats(USER_MESSAGES); await message.reply(f"🔥 Успешно! Теперь ты: <b>{title}</b>")
            except: await message.reply("❌ Ошибка прав бота.")
            return

        elif "новый тег для изменения" in reply_text:
            price = 500
            if not is_owner and USER_MESSAGES[uid]["balance"] < price:
                await message.reply("❌ Недостаточно 💎"); return
            try:
                await bot.set_chat_administrator_custom_title(chat_id=message.chat.id, user_id=int(uid), custom_title=title)
                if not is_owner: USER_MESSAGES[uid]["balance"] -= price
                save_stats(USER_MESSAGES); await message.reply(f"🏷 Тег изменен на: <b>{title}</b>")
            except: await message.reply("❌ Ошибка изменения.")
            return

    # Команды "Аура"
    if msg_text.startswith("аура"):
        if int(uid) not in ALLOWED_USERS: return

        if msg_text == "аура фарм":
            last_f = USER_MESSAGES[uid].get("last_farm", 0)
            if now - last_f < 10800:
                await message.reply(f"⏳ Жди {int((10800-(now-last_f))//60)} мин.")
            else:
                reward = random.randint(10, 300)
                USER_MESSAGES[uid]["balance"] += reward
                USER_MESSAGES[uid]["last_farm"] = now
                save_stats(USER_MESSAGES); await message.reply(f"⛏ +{reward} 💎! Баланс: {USER_MESSAGES[uid]['balance']}")

        elif msg_text == "аура баланс":
            bal = "∞" if is_owner else USER_MESSAGES[uid].get("balance", 0)
            await message.reply(f"💎 Твой баланс: <b>{bal}</b>")

        elif msg_text == "аура магазин":
            await message.reply("🛒 <b>Магазин Ауры</b>", reply_markup=get_shop_kb())

        elif "стата" in msg_text:
            periods = {"час": 3600, "сутки": 86400, "неделя": 604800, "месяц": 2592000}
            target_period = next((v for k, v in periods.items() if k in msg_text), None)
            stats = sorted([(d["name"], sum(1 for t in d["times"] if not target_period or (now-t)<=target_period), k) 
                           for k, d in USER_MESSAGES.items()], key=lambda x: x[1], reverse=True)
            report = "📊 <b>Топ:</b>\n" + "\n".join([f"{i}. {n} — <b>{c}</b>" for i, (n, c, k) in enumerate(stats[:10], 1)])
            await message.answer(report)

        elif "команды" in msg_text: await message.reply(HELP_TEXT, reply_markup=get_main_kb())
        elif "вероятность" in msg_text: await message.reply(f"🔮 Вероятность: <b>{random.randint(0, 100)}%</b>")
        elif "да нет" in msg_text: await message.reply(f"🎱 Ответ: <b>{random.choice(YES_NO_ANSWERS)}</b>")
        elif "выбор" in msg_text:
            opts = msg_text.replace("аура выбор", "").split(" или ")
            if len(opts) > 1: await message.reply(f"⚖️ Выбор: <b>{random.choice(opts).strip()}</b>")
        elif "удач" in msg_text: await message.reply(f"🍀 Удача: <b>{random.randint(0, 100)}%</b>")
        elif "фраз" in msg_text: await message.reply(f"💬 <b>{random.choice(AURA_QUOTES)}</b>")
        elif "кости" in msg_text: await message.reply(f"🎲 Выпало: <b>{random.randint(1, 6)}</b>")
        elif "таймер" in msg_text:
            try:
                sec = int(msg_text.split()[2])
                await message.reply(f"⏳ Таймер {sec}с."); await asyncio.sleep(sec)
                await message.answer(f"🔔 {uname}, время вышло!")
            except: pass
        elif "сбор" in msg_text:
            mentions = "".join([f'<a href="tg://user?id={tid}">\u2063</a>' for tid in ALLOWED_USERS])
            await message.answer(f"📢 <b>Общий сбор!</b>{mentions}")

@dp.message(CommandStart())
async def cmd_start_private(message: types.Message):
    await message.reply(HELP_TEXT, reply_markup=get_main_kb())

async def handle(r): return web.Response(text="Aura alive")
async def start_uptime():
    app = web.Application(); app.router.add_get('/', handle)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080))).start()

async def main():
    asyncio.create_task(start_uptime())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())
