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
from aiogram.utils.link import create_tg_link
import google.generativeai as genai

# --- НАСТРОЙКИ ---
TOKEN = os.environ.get('BOT_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')
STATS_FILE = "stats.json"

# --- ДИАГНОСТИКА И НАСТРОЙКА НЕЙРОСЕТИ ---
if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
        
        # Выводим инфу в логи Render (вкладка Logs)
        print(f"DEBUG: Версия библиотеки: {genai.__version__}")
        
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        print(f"DEBUG: Доступные модели: {available_models}")

        # Выбираем первую доступную или flash по умолчанию
        model_name = 'models/gemini-1.5-flash' 
        if available_models:
            # Если в списке есть что-то другое, можно подставить оттуда
            model_name = available_models[0]
            
        model = genai.GenerativeModel(model_name)
        print(f"DEBUG: Использую модель: {model_name}")

    except Exception as e:
        print(f"ОШИБКА ДИАГНОСТИКИ: {e}")

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

AURA_QUOTES = ["Конечно", "А как иначе", "Черт возьми", "А когда не делали", "Делаем", "На колени", "Возможно", "Это победа", "Легенда", "Внатуре", "Это реально круто", "Естественно", "Че они там курят", "Потихоньку", "Дай Бог", "Я это запомню", "Я это не запомню", "Я не мафия", "Я мафия", "Я тебе доверяю", "Вам че денег дать", "Че она несет", "Мед по телу"]
YES_NO_ANSWERS = ["Я думаю, что ДА", "Скорее всего, ДА", "Конечно, ДА", "Однозначно ДА", "Я думаю, что НЕТ", "Скорее всего, НЕТ", "Точно НЕТ", "Вообще без вариантов, НЕТ", "Спроси позже, я в раздумьях", "Мои сенсоры говорят - ДА", "Звезды нашептали - НЕТ"]
REPEAT_PHRASES = ["Я повторяюсь... Ответ: ", "Склероз? Я уже говорила: ", "Я же только что отвечала: ", "Мое мнение не изменилось: ", "У тебя дежавю? Ответ тот же: ", "Слушай внимательно, ответ: "]
AURA_VALUES = [
    67, 34, 69, 89, 322, 42, 52, 82, 1488, 228, 
    "пульсирует синим", "позорище, у тебя нет ауры", "пронырливая", "скудная", "невероятная", "бесконечная",
    "получил(а) много ауры незаконным путем", "грязная", "чистая", "выронил ауру", "украл чужую ауру", 
    "пожертвовал свою ауру нуждающимся", "взял микрозайм на ауру", "отбывает срок за кражу ауры"
]

SELF_AURA_VALUES = [
    "Абсолютная", 
    "Ослепительная. Не смотри на меня", 
    "Бесконечная конечно", 
    "Выиграла вашу ауру в казино", 
    "Живу на проценты с вашей ауры", 
    "Отмыла всю грязную ауру", 
    "Пожертвовала ауру нуждающимся"
]

WELCOME_VARIATIONS = [
    "Привет, {name}! Я Аура. Добро пожаловать в чат. Если вы тут впервые, учтите, что команды будут доступны после включения вас в белый список. Меню: <b>Аура команды</b>.",
    "Рада знакомству, {name}! Я Аура. Добро пожаловать. Если вы тут впервые, команды станут доступны, как только вас внесут в список доступа. Список команд: <b>Аура команды</b>.",
    "Приветствуем, {name}! Я - бот Аура. Если ты здесь впервые, располагайся! Команды заработают после получения доступа. Меню: <b>Аура команды</b>."
]
REJOIN_VARIATIONS = ["Привет, {name}! Рады тебя снова видеть.", "О, {name}, ты вернулся! С возвращением.", "{name}, снова привет! Без тебя было скучно.", "С возвращением, {name}! Мы уже и не надеялись."]
LEAVE_VARIATIONS = ["Удачи, {name}!", "{name} покинул(а) чат. Увидимся.", "До встречи, {name}.", "Минус один. Счастливо, {name}!"]
LEAVE_REPEAT_VARIATIONS = ["Опять ушел? Ну, до связи, {name}.", "Снова покидаешь нас, {name}? Ладно, пока.", "Ну вот, опять ушел. Бывай, {name}."]

BAD_WORDS = ["хуй", "пизд", "ебла", "сук", "бля", "гандон", "даун", "шлюх", "уеб", "чмо"]
SHAME_VARIATIONS = [
    "С такими выражениями твоя аура начнет сыпаться уже в 35 лет",
    "Из-за этих слов твоя аура только что потемнела. Аккуратнее",
    "Слышу грязненькое слово. Успокойся, Легенда и используй их с умом. Нам еще нужна твоя чистая аура",
    "Маты загрязняют твою ауру, используй их правильно",
    "Твои слова пахнут плохо. Давай без этого в моем присутствии",
    "Эти слова плохо влияют на ваше общее состоянее ауры. Осторожнее"
]

HELP_TEXT = (
    "✨ <b>Я Аура - ваш легендарный бот!</b> ✨\n\n"
    "<b>Доступные команды:</b>\n"
    "🔮 <code>Аура вероятность [текст]</code>\n"
    "🎱 <code>Аура да нет [вопрос]</code>\n"
    "⚖️ <code>Аура выбор [вар 1] или [вар 2]</code>\n"
    "📊 <code>Аура стата [час/сутки/неделя/месяц]</code>\n"
    "🤖 <code>Аура аск [вопрос]</code> - спросить мой разум\n"
    "💬 <code>Аура фраза</code> - выдать базу\n"
    "🍀 <code>Аура удача</code>\n"
    "🎲 <code>Аура кости</code>\n"
    "⏳ <code>Аура таймер [сек]</code>\n"
    "💎 <code>Аура аура [текст]</code> - узнать ауру\n"
    "📢 <code>Аура сбор</code> - общий сбор\n"
    "📜 <code>Аура команды</code> - меню"
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

@dp.message(F.chat.id.in_(ALLOWED_GROUPS), F.text)
async def main_group_handler(message: types.Message):
    msg_text = message.text.lower()
    uid = str(message.from_user.id)
    uname = message.from_user.first_name
    now = time.time()

    if uid not in USER_MESSAGES:
        USER_MESSAGES[uid] = {"name": uname, "times": []}
    USER_MESSAGES[uid]["times"].append(now)
    USER_MESSAGES[uid]["name"] = uname
    save_stats(USER_MESSAGES)

    if msg_text.startswith("аура"):
        if int(uid) not in ALLOWED_USERS:
            return

        # --- НОВАЯ КОМАНДА: АУРА АСК ---
        if msg_text.startswith("аура аск"):
            prompt = message.text[8:].strip()
            if not prompt:
                await message.reply("Легенда, ты забыл сам вопрос. Пиши: <code>Аура аск [твой вопрос]</code>")
                return
            
            if not GEMINI_KEY:
                await message.reply("Мои мозги сейчас отключены (нет ключа API).")
                return

            sent_msg = await message.reply("🌀 Так, секунду, сверяюсь с космосом...")
            try:
                # Настройка личности
                persona = (
                    "Ты — бот по имени Аура, легенда этого чата. Ты женщина с характером. "
                    "Твой стиль: дерзкий, уверенный, любишь немного подтроллить, но без злобы. "
                    "Используй сленг типа 'Легенда', 'база', 'мед по телу'. "
                    "Отвечай кратко, емко и по факту. Если вопрос глупый — подколи."
                )
                response = model.generate_content(f"{persona}\n\nВопрос от пользователя: {prompt}")
                await sent_msg.edit_text(response.text)
            except Exception as e:
                await sent_msg.edit_text(f"Ошибка: {str(e)}")
            return

        elif "стата" in msg_text or "статистика" in msg_text:
            periods = {"час": 3600, "сутки": 86400, "неделя": 604800, "месяц": 2592000}
            target_period = None
            period_name = "все время"
            for p_key, p_val in periods.items():
                if p_key in msg_text:
                    target_period = p_val
                    period_name = p_key
                    break
            
            stats = []
            for user_id_key, data in USER_MESSAGES.items():
                count = sum(1 for t in data["times"] if not target_period or (now - t) <= target_period)
                if count > 0: stats.append((data["name"], count, user_id_key))
            
            if not stats:
                await message.reply("Тут пока тишина, статы нет.")
                return

            stats.sort(key=lambda x: x[1], reverse=True)
            report = f"📊 <b>Статистика ({period_name}):</b>\n"
            for i, (name, cnt, u_id) in enumerate(stats[:10], 1):
                link = f'<a href="tg://user?id={u_id}">{name}</a>'
                report += f"{i}. {link} — <b>{cnt}</b>\n"
            await message.answer(report)

        elif "сбор" in msg_text:
            mentions = "".join([f'<a href="tg://user?id={tid}">\u2063</a>' for tid in ALLOWED_USERS])
            if mentions: await message.answer(f"📢 <b>Общий сбор!</b>{mentions}")
            else: await message.reply("Никого не нашла.")
        
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
        
        elif msg_text.startswith("аура аура"):
            target = message.text[9:].strip()
            if not target:
                if int(uid) in AURA_COOLDOWN and (now - AURA_COOLDOWN[int(uid)]) < 10:
                    await message.reply(f"⏳ Не части, Легенда. Подожди {int(10-(now-AURA_COOLDOWN[int(uid)]))} сек."); return
                res = random.choice(AURA_VALUES); AURA_COOLDOWN[int(uid)] = now
                await message.reply(f"💎 Твоя аура: <b>{res}</b>")
            elif target.lower() in ["@aurabotn_bot", "ауры", "аура", "aura"]:
                await message.reply(f"💎 Моя аура: <b>{random.choice(SELF_AURA_VALUES)}</b>")
            else:
                await message.reply(f"💎 Аура <b>{target}</b>: <b>{random.choice(AURA_VALUES)}</b>")
        
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
                await message.reply(f"⏳ Таймер на <b>{sec}</b> сек. запущен."); await asyncio.sleep(sec)
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

@dp.message(F.chat.type == "private", F.from_user.id.in_(ALLOWED_USERS), F.text.startswith("/msg "))
async def aura_anon_message(message: types.Message):
    text = message.text.replace("/msg ", "", 1).strip()
    if not text: return
    for g_id in ALLOWED_GROUPS:
        try: await bot.send_message(chat_id=g_id, text=f"💌 <b>Анонимно:</b>\n\n{text}")
        except: continue
    await message.reply("✅ Послание доставлено!")

async def main():
    if not TOKEN: return
    asyncio.create_task(start_uptime_server())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
