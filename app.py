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

# --- ФУНКЦИИ ДЛЯ РАБОТЫ СО СТАТИСТИКОЙ ---
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

# Кнопки
def get_aura_kb():
    buttons = [
        [InlineKeyboardButton(text="⛏ Фарм Ауры", callback_data="farm_aura")],
        [InlineKeyboardButton(text="💎 Мой Баланс", callback_data="check_balance")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

AURA_QUOTES = ["Конечно", "А как иначе", "Черт возьми", "А когда не делали", "Делаем", "На колени", "Возможно", "Это победа", "Легенда", "Внатуре", "Это реально круто", "Естественно", "Че они там курят", "Потихоньку", "Дай Бог", "Я это запомню", "Я это не запомню", "Я не мафия", "Я мафия", "Я тебе доверяю", "Вам че денег дать", "Че она несет", "Мед по телу"]
YES_NO_ANSWERS = ["Я думаю, что ДА", "Скорее всего, ДА", "Конечно, ДА", "Однозначно ДА", "Я думаю, что НЕТ", "Скорее всего, НЕТ", "Точно НЕТ", "Вообще без вариантов, НЕТ", "Спроси позже, я в раздумьях", "Мои сенсоры говорят - ДА", "Звезды нашептали - НЕТ"]
REPEAT_PHRASES = ["Я повторяюсь... Ответ: ", "Склероз? Я уже говорила: ", "Я же только что отвечала: ", "Мое мнение не изменилось: ", "У тебя дежавю? Ответ тот же: ", "Слушай внимательно, ответ: "]
AURA_VALUES = [67, 34, 69, 89, 322, 42, 52, 82, 1488, 228, "пульсирует синим", "позорище, у тебя нет ауры", "пронырливая", "скудная", "невероятная", "бесконечная", "грязная", "чистая"]
SELF_AURA_VALUES = ["Абсолютная", "Ослепительная. Не смотри на меня", "Бесконечная конечно"]

BAD_WORDS = ["хуй", "пизд", "ебла", "сук", "бля", "гандон", "даун", "шлюх", "уеб", "чмо"]
SHAME_VARIATIONS = ["С такими выражениями твоя аура начнет сыпаться уже в 35 лет", "Из-за этих слов твоя аура только что потемнела. Аккуратнее"]

HELP_TEXT = (
    "✨ <b>Я Аура - ваш легендарный бот!</b> ✨\n\n"
    "<b>💎 ЭКОНОМИКА:</b>\n"
    "⛏ <code>Аура фарм</code> — добыть очки (раз в 3ч)\n"
    "💰 <code>Аура баланс</code> — твой кошелек\n"
    "🛒 <code>Аура купить админку [тег]</code> — статус + тег (5000💎)\n"
    "🏷 <code>Аура изменить тег [тег]</code> — сменить надпись (500💎)\n\n"
    "<b>🔮 КОМАНДЫ:</b>\n"
    "🔮 <code>Аура вероятность [текст]</code>\n"
    "🎱 <code>Аура да нет [вопрос]</code>\n"
    "⚖️ <code>Аура выбор [1] или [2]</code>\n"
    "📊 <code>Аура стата [час/сутки]</code>\n"
    "💬 <code>Аура фраза</code> | 🍀 <code>Аура удача</code>\n"
    "🎲 <code>Аура кости</code> | ⏳ <code>Аура таймер [сек]</code>\n"
    "💎 <code>Аура аура [текст]</code>\n"
    "📢 <code>Аура сбор</code> | 📜 <code>Аура команды</code>\n"
    "✉️ <code>/msg [текст]</code> - анонимка в чат"
)

# --- CALLBACK ОБРАБОТЧИКИ ---
@dp.callback_query(F.data == "farm_aura")
async def process_farm(callback: CallbackQuery):
    uid = str(callback.from_user.id)
    if int(uid) not in ALLOWED_USERS:
        await callback.answer("Тебя нет в белом списке!", show_alert=True)
        return
    
    now = time.time()
    user_data = USER_MESSAGES.get(uid, {"balance": 0, "last_farm": 0})
    last_farm = user_data.get("last_farm", 0)
    
    if now - last_farm < 10800: # 3 часа
        wait_min = int((10800 - (now - last_farm)) // 60)
        await callback.answer(f"⏳ Рано! Твоя аура восстановится через {wait_min} мин.", show_alert=True)
        return
    
    reward = random.randint(10, 300)
    USER_MESSAGES[uid]["balance"] = USER_MESSAGES[uid].get("balance", 0) + reward
    USER_MESSAGES[uid]["last_farm"] = now
    save_stats(USER_MESSAGES)
    
    await callback.message.answer(f"⛏ <b>{callback.from_user.first_name}</b>, ты нафармил <b>{reward}</b> 💎\nБаланс: <b>{USER_MESSAGES[uid]['balance']}</b>")
    await callback.answer()

@dp.callback_query(F.data == "check_balance")
async def process_balance(callback: CallbackQuery):
    uid = str(callback.from_user.id)
    if int(uid) in ALLOWED_USERS and int(uid) in [int(x) for x in os.environ.get('ALLOWED_USERS', '').split(',')][:1]: # Твой ID обычно первый
        await callback.answer("💎 Твой баланс: ∞ (Админ-режим)", show_alert=True)
    else:
        balance = USER_MESSAGES.get(uid, {}).get("balance", 0)
        await callback.answer(f"💎 Твой баланс: {balance} ауры", show_alert=True)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def check_repeat(chat_id, question):
    now = time.time()
    if chat_id in LAST_ANSWERS:
        chat_history = LAST_ANSWERS[chat_id]
        if question in chat_history:
            entry = chat_history[question]
            if (now - entry['time']) < 60:
                return entry['answer']
    return None

def save_answer(chat_id, question, answer):
    now = time.time()
    if chat_id not in LAST_ANSWERS:
        LAST_ANSWERS[chat_id] = {}
    LAST_ANSWERS[chat_id][question] = {"answer": answer, "time": now}

async def handle(request):
    return web.Response(text="Aura is alive!")

async def start_uptime_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- ОБРАБОТЧИКИ ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.reply(HELP_TEXT, reply_markup=get_aura_kb())

@dp.message(F.chat.id.in_(ALLOWED_GROUPS), F.text)
async def main_group_handler(message: types.Message):
    msg_text = message.text.lower()
    uid = str(message.from_user.id)
    uname = message.from_user.first_name
    now = time.time()

    if uid not in USER_MESSAGES:
        USER_MESSAGES[uid] = {"name": uname, "times": [], "balance": 0, "last_farm": 0}
    USER_MESSAGES[uid]["times"].append(now)
    USER_MESSAGES[uid]["name"] = uname
    save_stats(USER_MESSAGES)

    if msg_text.startswith("аура"):
        if int(uid) not in ALLOWED_USERS:
            return

        # --- ЭКОНОМИКА КОМАНДЫ ---
        if msg_text == "аура фарм":
            last_farm = USER_MESSAGES[uid].get("last_farm", 0)
            if now - last_farm < 10800:
                wait_min = int((10800 - (now - last_farm)) // 60)
                await message.reply(f"⏳ Подожди еще {wait_min} мин.")
                return
            reward = random.randint(10, 300)
            USER_MESSAGES[uid]["balance"] += reward
            USER_MESSAGES[uid]["last_farm"] = now
            save_stats(USER_MESSAGES)
            await message.reply(f"⛏ +<b>{reward}</b> 💎! Баланс: <b>{USER_MESSAGES[uid]['balance']}</b>")

        elif msg_text == "аура баланс":
            bal = "∞" if int(uid) == ALLOWED_USERS[0] else USER_MESSAGES[uid].get("balance", 0)
            await message.reply(f"💎 Твой баланс: <b>{bal}</b>")

        elif msg_text.startswith("аура купить админку"):
            price = 5000
            # Проверка для тебя (бесконечный баланс)
            is_admin = int(uid) == ALLOWED_USERS[0]
            if not is_admin and USER_MESSAGES[uid].get("balance", 0) < price:
                await message.reply(f"❌ Нужно {price}💎. У тебя {USER_MESSAGES[uid]['balance']}")
                return
            
            title = message.text[19:].strip()
            if not title or len(title) > 16:
                await message.reply("Укажи тег (до 16 симв).")
                return
            try:
                await bot.promote_chat_member(chat_id=message.chat.id, user_id=int(uid), can_manage_chat=True)
                await bot.set_chat_administrator_custom_title(chat_id=message.chat.id, user_id=int(uid), custom_title=title)
                if not is_admin: USER_MESSAGES[uid]["balance"] -= price
                save_stats(USER_MESSAGES)
                await message.reply(f"🔥 Успех! Теперь ты <b>{title}</b>")
            except: await message.reply("❌ Дай боту права на управление админами.")

        elif msg_text.startswith("аура изменить тег"):
            price = 500
            is_admin = int(uid) == ALLOWED_USERS[0]
            if not is_admin and USER_MESSAGES[uid].get("balance", 0) < price:
                await message.reply(f"❌ Нужно {price}💎")
                return
            title = message.text[17:].strip()
            if not title or len(title) > 16: return
            try:
                await bot.set_chat_administrator_custom_title(chat_id=message.chat.id, user_id=int(uid), custom_title=title)
                if not is_admin: USER_MESSAGES[uid]["balance"] -= price
                save_stats(USER_MESSAGES)
                await message.reply(f"🏷 Тег изменен на <b>{title}</b>")
            except: await message.reply("❌ Ошибка. Ты админ?")

        # --- ТВОИ ОРИГИНАЛЬНЫЕ КОМАНДЫ ---
        elif "стата" in msg_text or "статистика" in msg_text:
            periods = {"час": 3600, "сутки": 86400, "неделя": 604800, "месяц": 2592000}
            target_period = next((v for k, v in periods.items() if k in msg_text), None)
            stats = []
            for u_id_key, data in USER_MESSAGES.items():
                count = sum(1 for t in data["times"] if not target_period or (now - t) <= target_period)
                if count > 0: stats.append((data["name"], count, u_id_key))
            stats.sort(key=lambda x: x[1], reverse=True)
            report = f"📊 <b>Топ:</b>\n"
            for i, (name, cnt, u_id) in enumerate(stats[:10], 1):
                report += f"{i}. <a href='tg://user?id={u_id}'>{name}</a> — <b>{cnt}</b>\n"
            await message.answer(report)

        elif "команды" in msg_text:
            await message.reply(HELP_TEXT, reply_markup=get_aura_kb())
        
        elif "вероятность" in msg_text:
            res = f"{random.randint(0, 100)}%"
            await message.reply(f"🔮 Вероятность: <b>{res}</b>")
        
        elif "да нет" in msg_text:
            await message.reply(f"🎱 Ответ: <b>{random.choice(YES_NO_ANSWERS)}</b>")

        elif "выбор" in msg_text:
            options = msg_text.replace("аура выбор", "").split(" или ")
            if len(options) > 1:
                await message.reply(f"⚖️ Мой выбор: <b>{random.choice(options).strip()}</b>")
        
        elif "удач" in msg_text:
            await message.reply(f"🍀 Удача: <b>{random.randint(0, 100)}%</b>")
        
        elif msg_text.startswith("аура аура"):
            await message.reply(f"💎 Аура: <b>{random.choice(AURA_VALUES)}</b>")
        
        elif "фраз" in msg_text:
            await message.reply(f"💬 <b>{random.choice(AURA_QUOTES)}</b>")
        
        elif "таймер" in msg_text:
            try:
                sec = int(msg_text.split()[2])
                await message.reply(f"⏳ Таймер {sec}с.")
                await asyncio.sleep(sec)
                await message.answer(f"🔔 {uname}, время вышло!")
            except: pass

        elif "сбор" in msg_text:
            mentions = "".join([f'<a href="tg://user?id={tid}">\u2063</a>' for tid in ALLOWED_USERS])
            await message.answer(f"📢 <b>Общий сбор!</b>{mentions}")

    if any(word in msg_text for word in BAD_WORDS):
        if random.random() < 0.25:
            await message.reply(random.choice(SHAME_VARIATIONS))

@dp.message(F.chat.type == "private", F.from_user.id.in_(ALLOWED_USERS), F.text.startswith("/msg "))
async def aura_anon_message(message: types.Message):
    text = message.text.replace("/msg ", "", 1).strip()
    if text:
        for g_id in ALLOWED_GROUPS:
            try: await bot.send_message(chat_id=g_id, text=f"💌 <b>Анонимно:</b>\n\n{text}")
            except: continue
        await message.reply("✅ Отправлено!")

async def main():
    if not TOKEN: return
    asyncio.create_task(start_uptime_server())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
