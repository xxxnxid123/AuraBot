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
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

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

# --- ФУНКЦИИ ДЛЯ РАБОТЫ С ФАЙЛОМ СТАТИСТИКИ ---
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
        print(f"Ошибка сохранения статистики: {e}")

# --- ПАМЯТЬ БОТА ---
LAST_ANSWERS = {}
AURA_COOLDOWN = {}
USER_JOINS_TODAY = {} 
USER_MESSAGES = load_stats()

# --- СПИСКИ ФРАЗ ---
AURA_QUOTES = ["Конечно", "А как иначе", "Черт возьми", "А когда не делали", "Делаем", "На колени", "Возможно", "Это победа", "Легенда", "Внатуре", "Это реально круто", "Естественно", "Че они там курят", "Потихоньку", "Дай Бог", "Я это запомню", "Я это не запомню", "Я не мафия", "Я мафия", "Я тебе доверяю", "Вам че денег дать", "Че она несет", "Мед по телу"]
YES_NO_ANSWERS = ["Я думаю, что ДА", "Скорее всего, ДА", "Конечно, ДА", "Однозначно ДА", "Я думаю, что НЕТ", "Скорее всего, НЕТ", "Точно НЕТ", "Вообще без вариантов, НЕТ", "Спроси позже, я в раздумьях", "Мои сенсоры говорят - ДА", "Звезды нашептали - НЕТ"]
REPEAT_PHRASES = ["Я повторяюсь... Ответ: ", "Склероз? Я уже говорила: ", "Я же только что отвечала: ", "Мое мнение не изменилось: ", "У тебя дежавю? Ответ тот же: ", "Слушай внимательно, ответ: "]
AURA_VALUES = [67, 34, 69, 89, 322, 42, 52, 82, 1488, 228, "пульсирует синим", "позорище, у тебя нет ауры", "пронырливая", "скудная", "невероятная", "бесконечная", "получил(а) много ауры незаконным путем", "грязная", "чистая", "выронил ауру", "украл чужую ауру", "пожертвовал свою ауру нуждающимся", "взял микрозайм на ауру", "отбывает срок за кражу ауры"]
SELF_AURA_VALUES = ["Абсолютная", "Ослепительная. Не смотри на меня", "Бесконечная конечно", "Выиграла вашу ауру в казино", "Живу на проценты с вашей ауры", "Отмыла всю грязную ауру", "Пожертвовала ауру нуждающимся"]
BAD_WORDS = ["хуй", "пизд", "ебла", "сук", "бля", "гандон", "даун", "шлюх", "уеб", "чмо"]
SHAME_VARIATIONS = ["С такими выражениями твоя аура начнет сыпаться уже в 35 лет", "Из-за этих слов твоя аура только что потемнела. Аккуратнее", "Слышу грязненькое слово. Успокойся, Легенда", "Маты загрязняют твою ауру", "Твои слова пахнут плохо", "Эти слова плохо влияют на ваше общее состоянее ауры"]

HELP_TEXT = (
    "✨ <b>Я Аура - ваш легендарный бот!</b> ✨\n\n"
    "<b>🛒 ЭКОНОМИКА:</b>\n"
    "⛏ <code>Аура фарм</code> — добыть 💎\n"
    "💰 <code>Аура баланс</code> — твой счет\n"
    "🏪 <code>Аура магазин</code> — меню покупок\n\n"
    "<b>🔮 КОМАНДЫ:</b>\n"
    "🔮 <code>Аура вероятность [текст]</code>\n"
    "🎱 <code>Аура да нет [вопрос]</code>\n"
    "⚖️ <code>Аура выбор [вар 1] или [вар 2]</code>\n"
    "📊 <code>Аура стата [час/сутки]</code>\n"
    "💬 <code>Аура фраза</code> | 🍀 <code>Аура удача</code>\n"
    "🎲 <code>Аура кости</code> | ⏳ <code>Аура таймер [сек]</code>\n"
    "💎 <code>Аура аура [текст]</code>\n"
    "📢 <code>Аура сбор</code> | 📜 <code>Аура команды</code>\n"
    "✉️ <code>/msg [текст]</code> - анонимка в чат"
)

# --- КНОПКИ ---
def get_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⛏ Фарм Ауры", callback_data="farm_aura")],
        [InlineKeyboardButton(text="🛒 Магазин", callback_data="open_shop")],
        [InlineKeyboardButton(text="💎 Мой Баланс", callback_data="check_balance")]
    ])

def get_shop_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎖 Админка (5000💎)", callback_data="buy_info_admin")],
        [InlineKeyboardButton(text="🏷 Смена тега (500💎)", callback_data="buy_info_tag")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")]
    ])

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def check_repeat(chat_id, question):
    now = time.time()
    if chat_id in LAST_ANSWERS and question in LAST_ANSWERS[chat_id]:
        entry = LAST_ANSWERS[chat_id][question]
        if (now - entry['time']) < 60:
            return entry['answer']
    return None

def save_answer(chat_id, question, answer):
    if chat_id not in LAST_ANSWERS: LAST_ANSWERS[chat_id] = {}
    LAST_ANSWERS[chat_id][question] = {"answer": answer, "time": time.time()}

# --- ОБРАБОТЧИКИ CALLBACK ---
@dp.callback_query(F.data == "farm_aura")
async def cb_farm(callback: CallbackQuery):
    uid = str(callback.from_user.id)
    if int(uid) not in ALLOWED_USERS:
        await callback.answer("Тебя нет в списке доступа!", show_alert=True); return
    now = time.time()
    user_data = USER_MESSAGES.get(uid, {"balance": 0, "last_farm": 0})
    if now - user_data.get("last_farm", 0) < 10800:
        await callback.answer(f"⏳ Жди {int((10800-(now-user_data['last_farm']))//60)} мин.", show_alert=True); return
    reward = random.randint(10, 300)
    USER_MESSAGES[uid]["balance"] = user_data.get("balance", 0) + reward
    USER_MESSAGES[uid]["last_farm"] = now
    save_stats(USER_MESSAGES)
    await callback.message.answer(f"⛏ +{reward} 💎! Баланс: {USER_MESSAGES[uid]['balance']}")
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

@dp.callback_query(F.data.startswith("buy_info_"))
async def cb_buy_info(callback: CallbackQuery):
    item = callback.data.split("_")[-1]
    if item == "admin": text = "Чтобы купить админку, напиши:\n<code>Аура купить админку [тег]</code>"
    else: text = "Чтобы сменить тег, напиши:\n<code>Аура изменить тег [тег]</code>"
    await callback.answer(text, show_alert=True)

# --- ОСНОВНОЙ ОБРАБОТЧИК ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.reply(HELP_TEXT, reply_markup=get_main_kb())

@dp.message(F.chat.id.in_(ALLOWED_GROUPS), F.text)
async def main_group_handler(message: types.Message):
    msg_text = message.text.lower()
    uid = str(message.from_user.id)
    uname = message.from_user.first_name
    now = time.time()
    is_owner = int(uid) == ALLOWED_USERS[0]

    if uid not in USER_MESSAGES:
        USER_MESSAGES[uid] = {"name": uname, "times": [], "balance": 0, "last_farm": 0}
    USER_MESSAGES[uid]["times"].append(now)
    USER_MESSAGES[uid]["name"] = uname
    save_stats(USER_MESSAGES)

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

        elif msg_text.startswith("аура купить админку"):
            price = 5000
            if not is_owner and USER_MESSAGES[uid].get("balance", 0) < price:
                await message.reply(f"❌ Нужно {price}💎"); return
            title = message.text[19:].strip()
            if not title: await message.reply("Укажи тег!"); return
            try:
                await bot.promote_chat_member(chat_id=message.chat.id, user_id=int(uid), can_manage_chat=True)
                await bot.set_chat_administrator_custom_title(chat_id=message.chat.id, user_id=int(uid), custom_title=title)
                if not is_owner: USER_MESSAGES[uid]["balance"] -= price
                save_stats(USER_MESSAGES); await message.reply(f"🔥 Теперь ты <b>{title}</b>!")
            except: await message.reply("❌ Проверь мои права админа!")

        elif msg_text.startswith("аура изменить тег"):
            price = 500
            if not is_owner and USER_MESSAGES[uid].get("balance", 0) < price:
                await message.reply(f"❌ Нужно {price}💎"); return
            title = message.text[17:].strip()
            if not title: return
            try:
                await bot.set_chat_administrator_custom_title(chat_id=message.chat.id, user_id=int(uid), custom_title=title)
                if not is_owner: USER_MESSAGES[uid]["balance"] -= price
                save_stats(USER_MESSAGES); await message.reply(f"🏷 Новый тег: <b>{title}</b>")
            except: await message.reply("❌ Не удалось сменить тег.")

        elif "стата" in msg_text:
            periods = {"час": 3600, "сутки": 86400, "неделя": 604800, "месяц": 2592000}
            target_period = next((v for k, v in periods.items() if k in msg_text), None)
            stats = sorted([(d["name"], sum(1 for t in d["times"] if not target_period or (now-t)<=target_period), k) 
                           for k, d in USER_MESSAGES.items()], key=lambda x: x[1], reverse=True)
            report = "📊 <b>Топ чата:</b>\n" + "\n".join([f"{i}. {n} — <b>{c}</b>" for i, (n, c, k) in enumerate(stats[:10], 1)])
            await message.answer(report)

        elif "команды" in msg_text: await message.reply(HELP_TEXT, reply_markup=get_main_kb())
        elif "вероятность" in msg_text:
            q = msg_text.replace("аура вероятность", "").strip()
            rep = check_repeat(message.chat.id, q)
            if rep: await message.reply(f"{random.choice(REPEAT_PHRASES)}<b>{rep}</b>")
            else: res = f"{random.randint(0, 100)}%"; save_answer(message.chat.id, q, res); await message.reply(f"🔮 Вероятность: <b>{res}</b>")
        elif "да нет" in msg_text:
            q = msg_text.replace("аура да нет", "").strip()
            rep = check_repeat(message.chat.id, q)
            if rep: await message.reply(f"{random.choice(REPEAT_PHRASES)}<b>{rep}</b>")
            else: ans = random.choice(YES_NO_ANSWERS); save_answer(message.chat.id, q, ans); await message.reply(f"🎱 Ответ: <b>{ans}</b>")
        elif "выбор" in msg_text:
            opts = msg_text.replace("аура выбор", "").split(" или ")
            if len(opts) > 1: await message.reply(f"⚖️ Мой выбор: <b>{random.choice(opts).strip()}</b>")
        elif "удач" in msg_text: await message.reply(f"🍀 Удача: <b>{random.randint(0, 100)}%</b>")
        elif "фраз" in msg_text: await message.reply(f"💬 <b>{random.choice(AURA_QUOTES)}</b>")
        elif "кости" in msg_text: await message.reply(f"🎲 Выпало: <b>{random.randint(1, 6)}</b>")
        elif "таймер" in msg_text:
            try:
                sec = int(msg_text.split()[2])
                await message.reply(f"⏳ Таймер на {sec}с."); await asyncio.sleep(sec)
                await message.answer(f"🔔 {uname}, время вышло!")
            except: pass
        elif "сбор" in msg_text:
            mentions = "".join([f'<a href="tg://user?id={tid}">\u2063</a>' for tid in ALLOWED_USERS])
            await message.answer(f"📢 <b>Общий сбор!</b>{mentions}")
        elif msg_text.startswith("аура аура"):
            await message.reply(f"💎 Аура: <b>{random.choice(AURA_VALUES)}</b>")

    if any(word in msg_text for word in BAD_WORDS):
        if random.random() < 0.25: await message.reply(random.choice(SHAME_VARIATIONS))

@dp.message(F.chat.type == "private", F.from_user.id.in_(ALLOWED_USERS), F.text.startswith("/msg "))
async def aura_anon_message(message: types.Message):
    text = message.text.replace("/msg ", "", 1).strip()
    if text:
        for g_id in ALLOWED_GROUPS:
            try: await bot.send_message(chat_id=g_id, text=f"💌 <b>Анонимно:</b>\n\n{text}")
            except: continue
        await message.reply("✅ Отправлено!")

async def handle(r): return web.Response(text="Aura alive")
async def start_uptime():
    app = web.Application(); app.router.add_get('/', handle)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080))).start()

async def main():
    if not TOKEN: return
    asyncio.create_task(start_uptime())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())
