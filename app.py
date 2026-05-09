import asyncio
import random
import os
import time
import json
import re
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.utils.link import create_tg_link
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton

# БИБЛИОТЕКИ ДЛЯ ТАБЛИЦ
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# БИБЛИОТЕКА ДЛЯ СКАЧИВАНИЯ (нужно установить: pip install yt-dlp)
import yt_dlp

# --- НОВЫЕ БИБЛИОТЕКИ ДЛЯ ГС ---
import speech_recognition as sr
from pydub import AudioSegment

# --- НАСТРОЙКИ ---
TOKEN = os.environ.get('BOT_TOKEN')

def get_ids(env_name):
    data = os.environ.get(env_name, "")
    return [int(i.strip()) for i in data.split(",") if i.strip().replace("-", "").isdigit()]

ALLOWED_GROUPS = get_ids('ALLOWED_GROUPS')
ALLOWED_USERS = get_ids('ALLOWED_USERS')

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Инициализация распознавателя
recognizer = sr.Recognizer()

# --- ЛОГИКА GOOGLE ТАБЛИЦ ---
def get_gsheet():
    creds_raw = os.environ.get('GOOGLE_SETTINGS')
    if not creds_raw:
        print("ОШИБКА: Переменная GOOGLE_SETTINGS не найдена!")
        return None
    
    creds_json = json.loads(creds_raw)
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    client = gspread.authorize(creds)
    return client.open("AuraStats").sheet1

def load_stats():
    try:
        sheet = get_gsheet()
        if not sheet: return {}
        
        records = sheet.get_all_records()
        if not records:
            return {}
            
        stats = {}
        for row in records:
            if not row.get('user_id'): continue
            
            uid = str(row['user_id'])
            stats[uid] = {
                "name": str(row.get('name', 'User')),
                "balance": int(row.get('balance', 0)),
                "last_farm": float(row.get('last_farm', 0)),
                "times": json.loads(row['times']) if row.get('times') else []
            }
        return stats
    except Exception as e:
        print(f"!!! ОШИБКА ЗАГРУЗКИ: {e}")
        return {}

def save_stats(stats_data):
    try:
        sheet = get_gsheet()
        if not sheet: return
        
        rows = [["user_id", "name", "balance", "last_farm", "times"]]
        
        for uid, data in stats_data.items():
            rows.append([
                str(uid), 
                str(data['name']), 
                int(data['balance']), 
                float(data['last_farm']), 
                json.dumps(data['times'])
            ])
        
        sheet.clear()
        sheet.update('A1', rows)
        print("--- Данные успешно синхронизированы с таблицей ---")
    except Exception as e:
        print(f"!!! ОШИБКА СОХРАНЕНИЯ: {e}")

# --- ЛОГИКА СТАТУСОВ ---
def get_status(balance):
    if balance < 500: return "Нищий (1)"
    if balance < 1500: return "Обычный (2)"
    if balance < 4000: return "Суетливый (3)"
    if balance < 10000: return "Жирный (4)"
    if balance < 25000: return "У тебя огромный аура (5)"
    if balance < 50000: return "Легенда (6)"
    return "Мёд по телу (7)"

# --- ПАМЯТЬ БОТА ---
LAST_ANSWERS = {}
AURA_COOLDOWN = {}
RISK_COOLDOWN = {} 
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

SELF_AURA_VALUES = ["Абсолютная", "Ослепительная. Не смотри на меня", "Бесконечная конечно", "Выиграла вашу ауру в казино", "Живу на проценты с вашей ауры", "Отмыла всю грязную ауру", "Пожертвовала ауру нуждающимся"]

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
    "Пизды дам будешь материться",
    "Как некультурно. Твоя аура только что потемнела.",
    "Что за слова такие черные. Нам еще нужна твоя чистая аура",
    "Охуел материться?",
    "Твои слова пахнут плохо. Давай без этого в моем присутствии."
]

LOSE_TROLL_PHRASES = [
    "не играйте в казино пацаны",
    "ахахахахах",
    "хахаххахха",
    "мдааа, минус аура",
    "лох",
    "казино всегда побеждает, когда вы поймете",
    "кто-то сегодня остался без обеда",
    "ебаный рот этого казино",
    "хахха это че за ставка"
]

TT_OFFER_TEXTS = [
    "Вижу тут скинули ТикТок! Желаете скачать?",
    "О, видос из тт скинули! Могу скачать.",
    "АЙ, че за ТикТок такой сладенький. Скачать?",
    "Аура подсказывает, что этот видос надо сохранить. Качаем?"
]

# Варианты предложений расшифровать ГС
VOICE_OFFER_TEXTS = [
    "🎙️ Вижу ГС! Если лень слушать, просто нажми на кнопку ниже или напиши: <code>Аура гс</code>",
    "🎤 О, голосовое! Могу перевести в текст, если не хочешь слушать.",
    "🛰️ Твои уши в безопасности. Расшифровать это голосовое?",
    "🎧 Входящее ГС обнаружено. Желаете прочитать, а не слушать?",
    "📝 Вижу голос. Если лень слушать, Аура может вслушаться за тебя."
]

# --- ФИЛЬТРЫ ---
is_allowed_user = F.from_user.id.in_(ALLOWED_USERS)
is_allowed_group = F.chat.id.in_(ALLOWED_GROUPS)
is_private_chat = F.chat.type == "private"

HELP_TEXT = (
    "✨ <b>Я Аура - ваш легендарный бот!</b> ✨\n\n"
    "<b>Экономика:</b>\n"
    "⛏ <code>Аура фарм</code> - заработать 💎\n"
    "💰 <code>Аура баланс</code> - твой счет\n"
    "🏆 <code>Аура топ</code> - богачи чата\n"
    "🔥 <code>Аура ставка [сумма]</code> - казино\n"
    "💸 <code>Аура перевод [сумма]</code> - (ответом на сообщение)\n\n"
    "<b>Доступные команды:</b>\n"
    "🎬 <code>Аура тт</code> - скачать видео (в ответ на ссылку)\n"
    "🎤 <code>Аура гс</code> - расшифровать ГС (в ответ на ГС)\n"
    "🔮 <code>Аура вероятность [текст]</code>\n"
    "🎱 <code>Аура да нет [вопрос]</code>\n"
    "⚖️ <code>Аура выбор [вар 1] или [вар 2]</code>\n"
    "📊 <code>Аура стата [час/сутки/неделя/месяц]</code>\n"
    "💬 <code>Аура фраза</code> - выдать базу\n"
    "🍀 <code>Аура удача</code>\n"
    "🎲 <code>Аура кости / кости пара</code>\n"
    "🔢 <code>Аура число [от] [до]</code>\n"
    "⏳ <code>Аура таймер [сек]</code>\n"
    "💎 <code>Аура аура [текст]</code> - узнать ауру\n"
    "📢 <code>Аура сбор</code> - общий сбор\n"
    "📜 <code>Аура команды</code> - меню\n\n"
    "📩 <b>Личные сообщения:</b>\n"
    "🔐 <code>/msg [текст]</code> - анонимка в чат"
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

def download_tiktok(url):
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': 'tiktok_video_%(id)s.mp4',
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        print(f"Ошибка скачивания ТТ: {e}")
        return None

# --- ФУНКЦИИ НЕЗАВИСИМЫХ ТАЙМЕРОВ (ОПТИМИЗИРОВАННЫЕ) ---
async def run_independent_timer(msg, initial_sec, user_mention):
    for s in range(initial_sec - 1, -1, -1):
        await asyncio.sleep(1)
        try:
            if s == 0:
                await msg.edit_text("🔔 Время вышло!")
                await msg.answer(f"🔔 {user_mention}, время вышло!")
                return
            elif s <= 10 or s % 5 == 0:
                await msg.edit_text(f"⏳ Осталось: <b>{s} сек.</b>")
        except: break

async def run_bet_cooldown_static(msg, remaining):
    await asyncio.sleep(remaining)
    try:
        await msg.edit_text("✅ Кулдаун прошел! Можно ставить снова.")
    except: pass

async def run_aura_analysis_static(msg, result):
    await asyncio.sleep(10)
    try:
        await msg.edit_text(f"💎 Твоя аура: <b>{result}</b>")
    except: pass

# --- ОБРАБОТЧИКИ ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message): await message.reply(HELP_TEXT)

@dp.callback_query(F.data.startswith("dl_tt_"))
async def cb_download_tt(callback: types.CallbackQuery):
    url = callback.data.replace("dl_tt_", "")
    wait_msg = await callback.message.answer("⏳ Пытаюсь достать видео из ТикТока... Подожди.")
    await callback.answer("Начинаю загрузку...")
    
    video_path = await asyncio.to_thread(download_tiktok, url)
    if video_path and os.path.exists(video_path):
        await callback.message.answer_video(FSInputFile(video_path), caption="🎬 Ваше видео из TikTok")
        os.remove(video_path)
        await wait_msg.delete()
    else:
        await wait_msg.edit_text("❌ Не удалось скачать видео. Возможно, оно приватное или ссылка битая.")

# Колбэк для кнопки расшифровки ГС
@dp.callback_query(F.data == "transcribe_voice")
async def cb_transcribe_voice(callback: types.CallbackQuery):
    if not callback.message.reply_to_message or not callback.message.reply_to_message.voice:
        await callback.answer("❌ ГС не найдено или оно было удалено.", show_alert=True)
        return
    
    # Имитируем команду "аура гс" для того же сообщения
    # Вызываем логику напрямую или через создание искусственного сообщения
    await callback.answer("Аура начинает слушать...")
    
    # Важное примечание: логика обработки ниже в основном обработчике дублируется, 
    # чтобы не менять структуру, вызываем расшифровку вручную здесь
    voice = callback.message.reply_to_message.voice
    v_uid = str(callback.message.reply_to_message.from_user.id)
    wait_msg = await callback.message.edit_text("📡 Аура прислушивается...")
    ogg_p, wav_p = f"{voice.file_id}.ogg", f"{voice.file_id}.wav"
    bad_pattern = r"(?i)\b(?:а|о|вы|по|на|при|у|ни)?(?:хуй|пизд|ебла|сук|бля|гандон|даун|шлюх|уеб|чмо|хуе|хуя)[а-яё]*"

    try:
        file = await bot.get_file(voice.file_id)
        await bot.download_file(file.file_path, ogg_p)
        audio = AudioSegment.from_ogg(ogg_p)
        audio.export(wav_p, format="wav")
        with sr.AudioFile(wav_p) as source:
            audio_data = recognizer.record(source)
            text = await asyncio.to_thread(recognizer.recognize_google, audio_data, language="ru-RU")

        if text:
            res = f"📝 <b>Текст голосового:</b>\n{text}"
            matches_gs = re.findall(bad_pattern, text.lower())
            if matches_gs:
                if v_uid not in USER_MESSAGES:
                    USER_MESSAGES[v_uid] = {"name": callback.message.reply_to_message.from_user.first_name, "times": [], "balance": 0, "last_farm": 0}
                fine_gs = len(matches_gs) * 10
                USER_MESSAGES[v_uid]["balance"] = max(0, USER_MESSAGES[v_uid].get("balance", 0) - fine_gs)
                res += f"\n\n🤫 <b>Аура всё слышит!</b> Автор оштрафован на <b>{fine_gs}</b> 💎"
                asyncio.create_task(asyncio.to_thread(save_stats, USER_MESSAGES))
            await wait_msg.edit_text(res)
        else:
            await wait_msg.edit_text("🛰 Не смогла разобрать ни слова.")
    except Exception as e:
        print(f"ГС ошибка: {e}")
        await wait_msg.edit_text("❌ Ошибка расшифровки. Проверь наличие ffmpeg.")
    finally:
        if os.path.exists(ogg_p): os.remove(ogg_p)
        if os.path.exists(wav_p): os.remove(wav_p)

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

# --- ОБРАБОТКА ГОЛОСОВЫХ (С ВАРИАНТАМИ И КНОПКОЙ) ---
@dp.message(is_allowed_group, F.voice)
async def voice_hint_handler(message: types.Message):
    if random.random() < 0.10: # Шанс 10%
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎤 Расшифровать", callback_data="transcribe_voice")]])
        await message.reply(random.choice(VOICE_OFFER_TEXTS), reply_markup=kb)

@dp.message(is_allowed_group, F.text)
async def main_group_handler(message: types.Message):
    msg_text = message.text.lower()
    uid = str(message.from_user.id)
    uname = message.from_user.first_name
    now = time.time()

    if uid not in USER_MESSAGES:
        USER_MESSAGES[uid] = {"name": uname, "times": [], "balance": 0, "last_farm": 0}
    USER_MESSAGES[uid]["times"].append(now)
    USER_MESSAGES[uid]["name"] = uname

    bad_pattern = r"(?i)\b(?:а|о|вы|по|на|при|у|ни)?(?:хуй|пизд|ебла|сук|бля|гандон|даун|шлюх|уеб|чмо|хуе|хуя)[а-яё]*"
    matches = re.findall(bad_pattern, msg_text)
    
    if matches:
        count = len(matches)
        total_fine = count * 5
        USER_MESSAGES[uid]["balance"] = max(0, USER_MESSAGES[uid].get("balance", 0) - total_fine)
        shame_phrase = random.choice(SHAME_VARIATIONS)
        if count > 1:
            response_text = f"{shame_phrase}\nПосчитала матов: <b>{count}</b> шт.\nИтого списано: <b>{total_fine}</b> 💎"
        else:
            response_text = f"{shame_phrase}\nУ тебя списано <b>{total_fine}</b> 💎"
        await message.reply(response_text)
        asyncio.create_task(asyncio.to_thread(save_stats, USER_MESSAGES))

    tt_match = re.search(r'http(?:s)?://(?:www\.)?v(?:t|m)\.tiktok\.com/\S+|http(?:s)?://(?:www\.)?tiktok\.com/\S+', message.text)
    if tt_match and not msg_text.startswith("аура"):
        url = tt_match.group(0)
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎬 Скачать видео", callback_data=f"dl_tt_{url}")]])
        await message.reply(random.choice(TT_OFFER_TEXTS), reply_markup=kb)

    if msg_text.startswith("аура"):
        if int(uid) not in ALLOWED_USERS:
            return

        if msg_text == "аура фарм":
            u_data = USER_MESSAGES[uid]
            wait_time = 10800
            if now - u_data.get("last_farm", 0) < wait_time:
                rem = int((wait_time - (now - u_data["last_farm"])) // 60)
                await message.reply(f"⏳ Рано! Приходи через <b>{rem // 60}ч {rem % 60}м</b>")
            else:
                reward = random.randint(50, 450)
                u_data["balance"] = u_data.get("balance", 0) + reward
                u_data["last_farm"] = now
                status = get_status(u_data["balance"])
                await message.reply(f"⛏ Ты нафармил <b>{reward}</b> 💎\nТвой баланс: <b>{u_data['balance']}</b>\nТвой статус: <b>{status}</b>")
                asyncio.create_task(asyncio.to_thread(save_stats, USER_MESSAGES)) 

        elif msg_text == "аура баланс":
            balance = USER_MESSAGES[uid].get("balance", 0)
            status = get_status(balance)
            await message.reply(f"💰 Твой баланс: <b>{balance}</b> 💎\nТвой статус: <b>{status}</b>")

        elif msg_text == "аура топ":
            top_list = []
            for u_id, data in USER_MESSAGES.items():
                if data.get("balance", 0) > 0:
                    top_list.append((data["name"], data["balance"], u_id))
            if not top_list:
                await message.reply("Список богачей пока пуст.")
                return
            top_list.sort(key=lambda x: x[1], reverse=True)
            report = "🏆 <b>Топ богачей Ауры:</b>\n\n"
            for i, (name, bal, u_id) in enumerate(top_list[:10], 1):
                link = f'<a href="tg://user?id={u_id}">{name}</a>'
                report += f"{i}. {link} — <b>{bal}</b> 💎\n"
            await message.answer(report)

        elif msg_text.startswith("аура перевод"):
            if not message.reply_to_message:
                await message.reply("Эту команду нужно писать ответом на сообщение того, кому хочешь перевести 💎")
                return
            try:
                parts = msg_text.split()
                amount = int(parts[2])
            except:
                await message.reply("Пиши: <code>Аура перевод [сумма]</code> (ответом на сообщение)")
                return
            
            recipient_id = str(message.reply_to_message.from_user.id)
            recipient_name = message.reply_to_message.from_user.first_name
            bot_id = str((await bot.get_me()).id)

            if amount <= 0:
                await message.reply("Сумма должна быть больше 0!")
                return
            if USER_MESSAGES[uid].get("balance", 0) < amount:
                await message.reply("У тебя не хватает 💎 для перевода!")
                return
            if uid == recipient_id:
                await message.reply("Переводить самому себе? Гениально.")
                return

            fee = int(amount * 0.01)
            fee_label = "(1%)"
            if amount < 100:
                fee = 1
                fee_label = "(1)"
            
            final_amount = amount - fee

            if bot_id not in USER_MESSAGES:
                USER_MESSAGES[bot_id] = {"name": "Казна Ауры", "times": [], "balance": 0, "last_farm": 0}
            if recipient_id not in USER_MESSAGES:
                USER_MESSAGES[recipient_id] = {"name": recipient_name, "times": [], "balance": 0, "last_farm": 0}

            USER_MESSAGES[uid]["balance"] -= amount
            USER_MESSAGES[recipient_id]["balance"] += final_amount
            USER_MESSAGES[bot_id]["balance"] += fee

            report_msg = (
                f"✅ <b>Перевод успешно выполнен!</b>\n\n"
                f"👤 Получатель: <a href='tg://user?id={recipient_id}'>{recipient_name}</a>\n"
                f"💸 Сумма перевода: <b>{amount}</b> 💎\n"
                f"🧾 Комиссия {fee_label}: <b>{fee}</b> 💎\n"
                f"💰 <b>Дошло до получателя: {final_amount}</b> 💎"
            )
            await message.reply(report_msg)
            asyncio.create_task(asyncio.to_thread(save_stats, USER_MESSAGES))

        elif msg_text.startswith("аура ставка"):
            uid_int = int(uid)
            if uid_int in RISK_COOLDOWN:
                passed = now - RISK_COOLDOWN[uid_int]
                if passed < 60:
                    remaining = int(60 - passed)
                    wait_bet_msg = await message.reply(f"⏳ Не так часто! Бурмалдить можно раз в минуту.\nПосиди еще: <b>{remaining} сек.</b>")
                    asyncio.create_task(run_bet_cooldown_static(wait_bet_msg, remaining))
                    return

            u_data = USER_MESSAGES[uid]
            try:
                bet = int(msg_text.split()[2])
            except:
                await message.reply("Пиши: <code>Аура ставка [сумма]</code>")
                return

            if bet <= 0:
                await message.reply("Ставка должна быть больше 0!")
                return
            if bet > u_data.get("balance", 0):
                await message.reply("У тебя нет столько 💎!")
                return

            dice = random.random()
            is_lose = False
            
            if dice < 0.05:
                mult, res_text = -2, "КРИТИЧЕСКИЙ ПРОВАЛ! Ты потерял ставку в двойном размере! 💀"
                is_lose = True
            elif dice < 0.20:
                mult, res_text = -1.5, "Неудачный риск! Потерял 1.5x от ставки. 📉"
                is_lose = True
            elif dice < 0.50:
                mult, res_text = 0, "Ничего не изменилось. Аура стабильна. ⚖️"
            elif dice < 0.75:
                mult, res_text = 0.5, "Хорошо! Твоя прибыль +0.5x ставки! 📈"
            elif dice < 0.95:
                mult, res_text = 1, "Удача! Ты удвоил ставку (+2x)! 💰"
            else:
                mult, res_text = 2, "ДЖЕКПОТ!!! Тройная прибыль (+3x)! 🔥"

            change = int(bet * mult)
            u_data["balance"] += change
            if u_data["balance"] < 0: u_data["balance"] = 0
            RISK_COOLDOWN[uid_int] = now
            
            await message.reply(f"{res_text}\nИзменение: <b>{'+' if change >= 0 else ''}{change}</b> 💎\nБаланс: <b>{u_data['balance']}</b>")
            asyncio.create_task(asyncio.to_thread(save_stats, USER_MESSAGES))

            if is_lose:
                await asyncio.sleep(1)
                await message.answer(random.choice(LOSE_TROLL_PHRASES))

        elif msg_text == "аура тт":
            if not message.reply_to_message or not message.reply_to_message.text:
                await message.reply("Ответь этой командой на сообщение с ссылкой на TikTok!")
                return
            urls = re.findall(r'http(?:s)?://(?:www\.)?v(?:t|m)\.tiktok\.com/\S+|http(?:s)?://(?:www\.)?tiktok\.com/\S+', message.reply_to_message.text)
            if not urls:
                await message.reply("В сообщении не найдено ссылки на TikTok.")
                return
            wait_msg = await message.reply("⏳ Пытаюсь достать видео из ТикТока... Подожди.")
            video_path = await asyncio.to_thread(download_tiktok, urls[0])
            if video_path and os.path.exists(video_path):
                await message.answer_video(FSInputFile(video_path), caption="🎬 Ваше видео из TikTok")
                os.remove(video_path)
                await wait_msg.delete()
            else:
                await wait_msg.edit_text("❌ Не удалось скачать видео.")

        # --- НОВАЯ КОМАНДА: РАСШИФРОВКА ГС ---
        elif msg_text in ["аура гс", "аура поясни", "аура чё там"]:
            if not message.reply_to_message or not message.reply_to_message.voice:
                await message.reply("Чтобы я расшифровала, ответь этой командой на голосовое сообщение! 🎧")
                return

            voice = message.reply_to_message.voice
            v_uid = str(message.reply_to_message.from_user.id)
            wait_msg = await message.reply("📡 Аура прислушивается...")
            ogg_p, wav_p = f"{voice.file_id}.ogg", f"{voice.file_id}.wav"

            try:
                file = await bot.get_file(voice.file_id)
                await bot.download_file(file.file_path, ogg_p)

                audio = AudioSegment.from_ogg(ogg_p)
                audio.export(wav_p, format="wav")

                with sr.AudioFile(wav_p) as source:
                    audio_data = recognizer.record(source)
                    # Фикс лагов: выносим распознавание в поток
                    text = await asyncio.to_thread(recognizer.recognize_google, audio_data, language="ru-RU")

                if text:
                    res = f"📝 <b>Текст голосового:</b>\n\n«{text}»"
                    matches_gs = re.findall(bad_pattern, text.lower())
                    if matches_gs:
                        # Фикс вылета: проверяем юзера в базе перед штрафом
                        if v_uid not in USER_MESSAGES:
                            USER_MESSAGES[v_uid] = {"name": message.reply_to_message.from_user.first_name, "times": [], "balance": 0, "last_farm": 0}
                        
                        fine_gs = len(matches_gs) * 10
                        USER_MESSAGES[v_uid]["balance"] = max(0, USER_MESSAGES[v_uid].get("balance", 0) - fine_gs)
                        res += f"\n\n🤫 <b>Аура всё слышит!</b> Автор оштрафован на <b>{fine_gs}</b> 💎"
                        asyncio.create_task(asyncio.to_thread(save_stats, USER_MESSAGES))
                    await wait_msg.edit_text(res)
                else:
                    await wait_msg.edit_text("🛰 Не смогла разобрать ни слова.")
            except Exception as e:
                print(f"ГС ошибка: {e}")
                await wait_msg.edit_text("❌ Ошибка расшифровки. Проверь наличие ffmpeg.")
            finally:
                # Гарантированное удаление мусора
                if os.path.exists(ogg_p): os.remove(ogg_p)
                if os.path.exists(wav_p): os.remove(wav_p)

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
                if target_period: count = sum(1 for t in data["times"] if (now - t) <= target_period)
                else: count = len(data["times"])
                if count > 0: stats.append((data["name"], count, user_id_key, data.get("balance", 0)))
            if not stats:
                await message.reply("Статистика пуста.")
                return
            stats.sort(key=lambda x: x[1], reverse=True)
            report = f"📊 <b>Статистика ({period_name}):</b>\n"
            for i, (name, cnt, u_id, bal) in enumerate(stats[:10], 1):
                link = f'<a href="tg://user?id={u_id}">{name}</a>'
                status_short = get_status(bal).split(' (')[0]
                report += f"{i}. {link} — <b>{cnt}</b> [{status_short}]\n"
            await message.answer(report)

        elif "сбор" in msg_text:
            mentions = ""
            for target_id in ALLOWED_USERS:
                try:
                    member = await message.bot.get_chat_member(message.chat.id, target_id)
                    if member.status not in ["left", "kicked"]:
                        mentions += f'<a href="tg://user?id={target_id}">\u2063</a>'
                except: continue
            if mentions: await message.answer(f"📢 <b>Общий сбор!</b>{mentions}")
            else: await message.reply("Никого из списка доступа в этом чате не найдено.")
        
        elif "команды" in msg_text: await message.reply(HELP_TEXT)
        
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
            words = content.lower()
            if ("вилк" in words or "глаз" in words) and ("жоп" in words or "раз" in words):
                await message.reply(random.choice(["Иди нахуй", "Иди нахуй с такими вопросами", "Пошел нахуй", "Еблан сука", "Может нахуй сходишь", "Тебя явно не спрашивали блять"]))
                return
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
            uid_int = int(uid)

            if not target:
                if uid_int in AURA_COOLDOWN:
                    passed = now - AURA_COOLDOWN[uid_int]
                    if passed < 10:
                        remaining = int(10 - passed)
                        try: await message.reply(f"⏳ Ты уже запрашивал ауру! Подожди еще <b>{remaining} сек.</b>")
                        except: pass
                        return

                AURA_COOLDOWN[uid_int] = now
                res = random.choice(AURA_VALUES)
                wait_msg = await message.reply(f"🔮 Анализирую твою ауру... Подожди 10 сек.")
                asyncio.create_task(run_aura_analysis_static(wait_msg, res))
            
            elif target.lower() in ["@aurabotn_bot", "ауры", "аура", "aura"]:
                res = random.choice(SELF_AURA_VALUES)
                await message.reply(f"💎 Моя аура: <b>{res}</b>")
            else:
                res = random.choice(AURA_VALUES)
                await message.reply(f"💎 Аура <b>{target}</b>: <b>{res}</b>")
        
        elif "фраз" in msg_text: await message.reply(f"💬 <b>{random.choice(AURA_QUOTES)}</b>")
        
        elif "число" in msg_text:
            try:
                parts = msg_text.split(); n1, n2 = int(parts[2]), int(parts[3])
                await message.reply(f"🔢 Число: <b>{random.randint(min(n1, n2), max(n1, n2))}</b>")
            except: await message.reply("Пиши: <code>Аура число 1 100</code>")
        
        elif "таймер" in msg_text:
            try:
                sec = int(msg_text.split()[2])
                if sec > 300: 
                    await message.reply("Максимум 300 секунд!")
                    return
                
                msg = await message.reply(f"⏳ Таймер запущен: <b>{sec} сек.</b>")
                asyncio.create_task(run_independent_timer(msg, sec, message.from_user.mention_html()))
            except: 
                await message.reply("Пиши: <code>Аура таймер [время в сек]</code>")

        elif "кости пара" in msg_text: await message.reply(f"🎲 Выпало: <b>{random.randint(1, 6)}</b> и <b>{random.randint(1, 6)}</b>")
        elif "кости" in msg_text: await message.reply(f"🎲 Число: <b>{random.randint(1, 6)}</b>")
        return

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
