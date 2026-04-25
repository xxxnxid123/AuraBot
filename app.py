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
    return [int(i.strip()) for i in data.split(",") if i.strip().replace("-", "").isdigit()]

ALLOWED_GROUPS = get_ids('ALLOWED_GROUPS')
ALLOWED_USERS = get_ids('ALLOWED_USERS')

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- ПАМЯТЬ БОТА ---
LAST_ANSWERS = {}
AURA_COOLDOWN = {}
USER_JOINS_TODAY = {} 

AURA_QUOTES = ["Конечно", "А как иначе", "Черт возьми", "А когда не делали", "Делаем", "На колени", "Возможно", "Это победа", "Легенда", "Внатуре", "Это реально круто", "Естественно", "Че они там курят", "Потихоньку", "Дай Бог", "Я это запомню", "Я это не запомню", "Я не мафия", "Я мафия", "Я тебе доверяю", "Вам че денег дать", "Че она несет", "Мед по телу"]
YES_NO_ANSWERS = ["Я думаю, что ДА", "Скорее всего, ДА", "Конечно, ДА", "Однозначно ДА", "Я думаю, что НЕТ", "Скорее всего, НЕТ", "Точно НЕТ", "Вообще без вариантов, НЕТ", "Спроси позже, я в раздумьях", "Мои сенсоры говорят - ДА", "Звезды нашептали - НЕТ"]
REPEAT_PHRASES = ["Я повторяюсь... Ответ: ", "Склероз? Я уже говорила: ", "Я же только что отвечала: ", "Мое мнение не изменилось: ", "У тебя дежавю? Ответ тот же: ", "Слушай внимательно, ответ: "]
AURA_VALUES = [67, 34, 69, 89, 322, 42, 52, 82, 1488, 228, "пульсирует синим", "позорище, у тебя нет ауры", "пронырливая", "скудная", "невероятная", "бесконечная"]

# Варианты приветствий
WELCOME_VARIATIONS = [
    "Привет, {name}! Я Аура. Добро пожаловать в чат. Если вы тут впервые, учтите, что команды будут доступны после включения вас в белый список. Меню: <b>Аура команды</b>.",
    "Рада знакомству, {name}! Я Аура. Добро пожаловать. Если вы тут впервые, команды станут доступны, как только вас внесут в список доступа. Список команд: <b>Аура команды</b>.",
    "Приветствуем, {name}! Я - бот Аура. Если ты здесь впервые, располагайся! Команды заработают после получения доступа. Меню: <b>Аура команды</b>."
]
REJOIN_VARIATIONS = ["Привет, {name}! Рады тебя снова видеть.", "О, {name}, ты вернулся! С возвращением.", "{name}, снова привет! Без тебя было скучно.", "С возвращением, {name}! Мы уже и не надеялись."]
LEAVE_VARIATIONS = ["Удачи, {name}!", "{name} покинул(а) чат. Увидимся.", "До встречи, {name}.", "Минус один. Счастливо, {name}!"]
LEAVE_REPEAT_VARIATIONS = ["Опять ушел? Ну, до связи, {name}.", "Снова покидаешь нас, {name}? Ладно, пока.", "Ну вот, опять ушел. Бывай, {name}."]

# Реакции на мат
BAD_WORDS = ["хуй", "пизд", "ебла", "сук", "бля", "гандон", "даун", "шлюх", "уеб", "чмо"]
SHAME_VARIATIONS = [
    "Ай-ай-ай, какой плохой человек... Как так можно, материться? 😏",
    "Фу, как некультурно. Твоя аура только что потемнела. ✨",
    "Слышу мат - вижу неуверенность. Успокойся, легенда. Нам еще нужна твоя чистая аура",
    "Ой, кто это у нас тут такой смелый матерится? Кринжа навалил, конечно. 👋",
    "Твои слова пахнут плохо. Давай без этого в моем присутствии."
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
    "⚖️ <code>Аура выбор [вар 1] или [вар 2]</code>\n"
    "💬 <code>Аура фраза</code> - выдать базу\n"
    "🍀 <code>Аура удача</code>\n"
    "🎲 <code>Аура кости</code>\n"
    "🔢 <code>Аура число [от] [до]</code>\n"
    "💎 <code>Аура аура</code> - узнать свою ауру сейчас\n"
    "📢 <code>Аура сбор</code> - общий сбор, тегнуть пользователей чата\n"
    "📜 <code>Аура команды</code> - показать это меню\n\n"
)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def check_repeat(chat_id, question):
    now = time.time()
    if chat_id in LAST_ANSWERS:
        chat_history = LAST_ANSWERS[chat_id]
        if question in chat_history:
            entry = chat_history[question]
            if (now - entry['time']) < 60: return entry['answer']
    return None

def save_answer(chat_id, question, answer):
    now = time.time()
    if chat_id not in LAST_ANSWERS: LAST_ANSWERS[chat_id] = {}
    LAST_ANSWERS[chat_id][question] = {"answer": answer, "time": now}

async def handle(request): return web.Response(text="Aura is alive!")

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
async def cmd_start(message: types.Message): await message.reply(HELP_TEXT)

@dp.message(F.new_chat_members)
async def welcome_new_member(message: types.Message):
    today = time.strftime("%Y-%m-%d")
    for user in message.new_chat_members:
        if user.id == (await bot.get_me()).id:
            await message.answer(f"Привет всем! {HELP_TEXT}")
            continue
        uid, name = user.id, user.first_name
        if uid in USER_JOINS_TODAY and USER_JOINS_TODAY[uid]['last_date'] == today:
            USER_JOINS_TODAY[uid]['count'] += 1
            text = random.choice(REJOIN_VARIATIONS).format(name=name)
        else:
            USER_JOINS_TODAY[uid] = {'count': 1, 'last_date': today}
            text = random.choice(WELCOME_VARIATIONS).format(name=name)
        await message.answer(text)

@dp.message(F.left_chat_member)
async def goodbye_member(message: types.Message):
    user = message.left_chat_member
    if user.id == (await bot.get_me()).id: return
    today = time.strftime("%Y-%m-%d")
    uid, name = user.id, user.first_name
    if uid in USER_JOINS_TODAY and USER_JOINS_TODAY[uid]['last_date'] == today and USER_JOINS_TODAY[uid]['count'] > 1:
        text = random.choice(LEAVE_REPEAT_VARIATIONS).format(name=name)
    else:
        text = random.choice(LEAVE_VARIATIONS).format(name=name)
    await message.answer(text)

@dp.message(is_allowed_group, F.text)
async def main_group_handler(message: types.Message):
    msg_text = message.text.lower()
    uid = message.from_user.id

    if msg_text.startswith("аура"):
        if uid not in ALLOWED_USERS:
            return

        if "сбор" in msg_text:
            mentions = ""
            for target_id in ALLOWED_USERS:
                try:
                    member = await message.bot.get_chat_member(message.chat.id, target_id)
                    if member.status not in ["left", "kicked"]:
                        mentions += f'<a href="tg://user?id={target_id}">\u2063</a>'
                except: continue
            if mentions: await message.answer(f"📢 <b>Общий сбор!</b>{mentions}")
            else: await message.reply("Никого из списка доступа в этом чате не найдено.")
        
        elif "команды" in msg_text:
            await message.reply(HELP_TEXT)
        
        elif "вероятность" in msg_text:
            question = msg_text.replace("аура вероятность", "").strip()
            repeated = check_repeat(message.chat.id, question)
            if repeated: await message.reply(f"{random.choice(REPEAT_PHRASES)}<b>{repeated}</b>")
            else:
                res = f"{random.randint(0, 100)}%"
                save_answer(message.chat.id, question, res)
                await message.reply(f"🔮 Вероятность: <b>{res}</b>")
        
        elif "да нет" in msg_text:
            question = msg_text.replace("аура да нет", "").strip()
            repeated = check_repeat(message.chat.id, question)
            if repeated: await message.reply(f"{random.choice(REPEAT_PHRASES)}<b>{repeated}</b>")
            else:
                ans = random.choice(YES_NO_ANSWERS); save_answer(message.chat.id, question, ans)
                await message.reply(f"🎱 Ответ: <b>{ans}</b>")

        elif "выбор" in msg_text:
            content = msg_text.replace("аура выбор", "").strip()
            if " или " in content:
                repeated = check_repeat(message.chat.id, content)
                if repeated: await message.reply(f"{random.choice(REPEAT_PHRASES)}<b>{repeated}</b>")
                else:
                    options = content.split(" или "); res = random.choice(options).strip()
                    save_answer(message.chat.id, content, res); await message.reply(f"⚖️ Мой выбор: <b>{res}</b>")
            else: await message.reply("Разделяй варианты словом <b>или</b>")
        
        elif "удач" in msg_text:
            luck = f"{random.randint(0, 100)}%"; await message.reply(f"🍀 Удача сегодня: <b>{luck}</b>")
        
        elif msg_text == "аура аура":
            now = time.time()
            if uid in AURA_COOLDOWN and (now - AURA_COOLDOWN[uid]) < 10:
                await message.reply(f"⏳ Подожди {int(10-(now-AURA_COOLDOWN[uid]))} сек."); return
            res = random.choice(AURA_VALUES); AURA_COOLDOWN[uid] = now
            await message.reply(f"💎 Твоя аура: <b>{res}</b>")
        
        elif "фраз" in msg_text:
            await message.reply(f"💬 <b>{random.choice(AURA_QUOTES)}</b>")
        
        elif "число" in msg_text:
            try:
                parts = msg_text.split(); n1, n2 = int(parts[2]), int(parts[3])
                await message.reply(f"🔢 Число: <b>{random.randint(min(n1, n2), max(n1, n2))}</b>")
            except: await message.reply("Пиши: <code>Аура число 1 100</code>")
        
        elif "таймер" in msg_text:
            try:
                sec = int(msg_text.split()[2])
                await message.reply(f"⏳ Таймер на <b>{sec}</b> сек."); await asyncio.sleep(sec)
                await message.answer(f"🔔 {message.from_user.mention_html()}, время вышло!")
            except: await message.reply("Пиши: <code>Аура таймер 10</code>")

        elif "кости пара" in msg_text:
            await message.reply(f"🎲 Выпало: <b>{random.randint(1, 6)}</b> и <b>{random.randint(1, 6)}</b>")
        
        elif "кости" in msg_text:
            await message.reply(f"🎲 Число: <b>{random.randint(1, 6)}</b>")

        return

    if any(word in msg_text for word in BAD_WORDS):
        if random.random() < 0.25:
            await message.reply(random.choice(SHAME_VARIATIONS))

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
