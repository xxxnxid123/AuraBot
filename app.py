import asyncio
import random
import os
import time
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart

# --- НАСТРОЙКИ ---
TOKEN = os.environ.get('BOT_TOKEN')

def get_ids(env_name):
    data = os.environ.get(env_name, "")
    # Извлекаем ID из переменных окружения
    ids = [int(i.strip()) for i in data.split(",") if i.strip().replace("-", "").isdigit()]
    # Если мы тянем ALLOWED_USERS, добавляем твой новый ID принудительно
    if env_name == 'ALLOWED_USERS':
        new_id = 5025272062
        if new_id not in ids:
            ids.append(new_id)
    return ids

ALLOWED_GROUPS = get_ids('ALLOWED_GROUPS')
ALLOWED_USERS = get_ids('ALLOWED_USERS')

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- ПАМЯТЬ БОТА ---
LAST_ANSWERS = {}
AURA_COOLDOWN = {}

AURA_QUOTES = [
    "Конечно", "А как иначе", "Черт возьми", "А когда не делали", 
    "Никогда не делали", "Делаем", "На колени", "Возможно", 
    "Это победа", "Легенда", "Внатуре", "Это реально круто", 
    "Естественно", "Че они там курят", "Потихоньку", "Дай Бог", 
    "Я это запомню", "Я это не запомню", "Я не мафия", "Я мафия", 
    "Я тебе доверяю", "Вам че денег дать", "Че она несет", "Мед по телу"
]

YES_NO_ANSWERS = [
    "Я думаю, что ДА", "Скорее всего, ДА", "Конечно, ДА", "Однозначно ДА",
    "Я думаю, что НЕТ", "Скорее всего, НЕТ", "Точно НЕТ", "Вообще без вариантов, НЕТ",
    "Спроси позже, я в раздумьях", "Мои сенсоры говорят — ДА", "Звезды нашептали — НЕТ"
]

REPEAT_PHRASES = [
    "Я повторяюсь... Ответ: ",
    "Склероз? Я уже говорила: ",
    "Я же только что отвечала: ",
    "Мое мнение не изменилось: ",
    "У тебя дежавю? Ответ тот же: ",
    "Слушай внимательно, ответ: "
]

AURA_VALUES = [
    67, 34, 69, 89, 322, 42, 52, 82, 1488, 228, 
    "пульсирует синим", "позорище, у тебя нет ауры",
    "пронырливая", "скудная", "невероятная", "бесконечная"
]

# --- ФИЛЬТРЫ ---
is_allowed_user = F.from_user.id.in_(ALLOWED_USERS)
is_allowed_group = F.chat.id.in_(ALLOWED_GROUPS)
is_private_chat = F.chat.type == "private"

HELP_TEXT = (
    "✨ <b>Я Аура - ваш легендарный бот!</b> ✨\n\n"
    "<b>Доступные команды:</b>\n"
    "🔮 <code>Аура вероятность [текст]</code>\n"
    "🎱 <code>Аура да нет [вопрос]</code>\n"
    "💬 <code>Аура фраза</code> - выдать базу\n"
    "🍀 <code>Аура удача</code>\n"
    "🎲 <code>Аура кости</code>\n"
    "🔢 <code>Аура число [от] [до]</code>\n"
    "💎 <code>Аура аура</code> - узнать свою ауру сейчас\n"
    "📢 <code>Аура сбор</code> - призвать своих в этом чате\n"
    "📜 <code>Аура команды</code> - показать это меню\n\n"
)

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
    await message.reply(HELP_TEXT)

@dp.message(is_allowed_group, is_allowed_user, F.text.lower().startswith("аура сбор"))
async def aura_call_all(message: types.Message):
    mentions = ""
    for uid in ALLOWED_USERS:
        try:
            member = await message.bot.get_chat_member(message.chat.id, uid)
            if member.status not in ["left", "kicked"]:
                mentions += f'<a href="tg://user?id={uid}">\u2063</a>'
        except:
            continue
    
    if mentions:
        await message.answer(f"📢 <b>Общий сбор!</b>{mentions}")
    else:
        await message.reply("Никого из списка доступа в этом чате не найдено.")

@dp.message(is_allowed_group, is_allowed_user, F.text.lower().startswith("аура команды"))
async def aura_help_cmd(message: types.Message):
    await message.reply(HELP_TEXT)

@dp.message(is_allowed_group, is_allowed_user, F.text.lower().startswith("аура вероятность"))
async def aura_probability(message: types.Message):
    question = message.text.lower().replace("аура вероятность", "").strip()
    repeated = check_repeat(message.chat.id, question)
    if repeated:
        await message.reply(f"{random.choice(REPEAT_PHRASES)}<b>{repeated}</b>")
    else:
        res = f"{random.randint(0, 100)}%"
        save_answer(message.chat.id, question, res)
        await message.reply(f"🔮 Вероятность: <b>{res}</b>")

@dp.message(is_allowed_group, is_allowed_user, F.text.lower().startswith("аура да нет"))
async def aura_yes_no(message: types.Message):
    question = message.text.lower().replace("аура да нет", "").strip()
    repeated = check_repeat(message.chat.id, question)
    if repeated:
        await message.reply(f"{random.choice(REPEAT_PHRASES)}<b>{repeated}</b>")
    else:
        ans = random.choice(YES_NO_ANSWERS)
        save_answer(message.chat.id, question, ans)
        await message.reply(f"🎱 Ответ: <b>{ans}</b>")

@dp.message(is_allowed_group, is_allowed_user, F.text.lower().startswith("аура выбор"))
async def aura_choice(message: types.Message):
    content = message.text[10:].lower().strip()
    if " или " in content:
        repeated = check_repeat(message.chat.id, content)
        if repeated:
            await message.reply(f"{random.choice(REPEAT_PHRASES)}<b>{repeated}</b>")
        else:
            options = content.split(" или ")
            res = random.choice(options).strip()
            save_answer(message.chat.id, content, res)
            await message.reply(f"⚖️ Мой выбор: <b>{res}</b>")
    else:
        await message.reply("Разделяй варианты словом <b>или</b>")

@dp.message(is_allowed_group, is_allowed_user, F.text.lower().startswith("аура удача"))
async def aura_luck(message: types.Message):
    question = "luck_check"
    repeated = check_repeat(message.chat.id, question)
    if repeated:
        await message.reply(f"{random.choice(REPEAT_PHRASES)}<b>{repeated}</b>")
    else:
        luck = f"{random.randint(0, 100)}%"
        save_answer(message.chat.id, question, luck)
        await message.reply(f"🍀 Удача сегодня: <b>{luck}</b>")

@dp.message(is_allowed_group, is_allowed_user, F.text.lower() == "аура аура")
async def aura_instant_value(message: types.Message):
    uid = message.from_user.id
    now = time.time()
    if uid in AURA_COOLDOWN and (now - AURA_COOLDOWN[uid]) < 10:
        left = int(10 - (now - AURA_COOLDOWN[uid]))
        await message.reply(f"⏳ Подожди {left} сек. Аура обновляется!")
        return
    res = random.choice(AURA_VALUES)
    AURA_COOLDOWN[uid] = now
    await message.reply(f"💎 Твоя аура в данный момент: <b>{res}</b>")

@dp.message(is_allowed_group, is_allowed_user, F.text.lower().startswith("аура число"))
async def aura_random_num(message: types.Message):
    parts = message.text.split()
    try:
        n1, n2 = int(parts[2]), int(parts[3])
        res = random.randint(min(n1, n2), max(n1, n2))
        await message.reply(f"🔢 Случайное число: <b>{res}</b>")
    except:
        await message.reply("Пиши: <code>Аура число 1 100</code>")

@dp.message(is_allowed_group, is_allowed_user, F.text.lower().startswith("аура таймер"))
async def aura_timer(message: types.Message):
    parts = message.text.split()
    try:
        seconds = int(parts[2])
        if seconds <= 0: raise ValueError
        await message.reply(f"⏳ Таймер запущен на <b>{seconds}</b> сек.")
        await asyncio.sleep(seconds)
        await message.answer(f"🔔 {message.from_user.mention_html()}, <b>время вышло!</b>")
    except:
        await message.reply("Пиши: <code>Аура таймер 10</code>")

@dp.message(F.new_chat_members)
async def welcome_new_member(message: types.Message):
    for user in message.new_chat_members:
        if user.id == (await bot.get_me()).id:
            await message.answer(f"Привет всем! {HELP_TEXT}")
        else:
            await message.answer(f"Привет, {user.first_name}! Я Аура. Напиши <b>Аура команды</b>.")

@dp.message(is_allowed_group, is_allowed_user, F.text.lower().startswith("аура фраза"))
async def aura_random_quote(message: types.Message):
    quote = random.choice(AURA_QUOTES)
    await message.reply(f"💬 <b>{quote}</b>")

@dp.message(is_allowed_group, is_allowed_user, F.text.lower() == "аура кости пара")
async def aura_dice_pair(message: types.Message):
    await message.reply(f"🎲 Выпало: <b>{random.randint(1, 6)}</b> и <b>{random.randint(1, 6)}</b>")

@dp.message(is_allowed_group, is_allowed_user, F.text.lower() == "аура кости")
async def aura_dice_single(message: types.Message):
    await message.reply(f"🎲 Число: <b>{random.randint(1, 6)}</b>")

@dp.message(is_private_chat, is_allowed_user, F.text.startswith("/msg "))
async def aura_anon_message(message: types.Message):
    text = message.text.replace("/msg ", "", 1).strip()
    if not text: return
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
