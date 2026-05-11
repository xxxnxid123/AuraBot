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

# --- НОВЫЙ SDK GEMINI ---
# Установи: pip install google-genai
from google import genai

# --- НАСТРОЙКИ ---
TOKEN = os.environ.get('BOT_TOKEN')

# Используем новый клиент
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
if GEMINI_KEY:
    client_gemini = genai.Client(api_key=GEMINI_KEY)
else:
    client_gemini = None

AURA_ID = "8637150963"


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
    
    try:
        creds_json = json.loads(creds_raw)
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
        client = gspread.authorize(creds)
        return client.open("AuraStats").sheet1
    except Exception as e:
        print(f"Ошибка доступа к таблице: {e}")
        return None


def load_stats():
    try:
        sheet = get_gsheet()
        if not sheet:
            return {}
        
        records = sheet.get_all_records()
        if not records:
            return {}
            
        stats = {}
        for row in records:
            if not row.get('user_id'):
                continue
            
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
        if not sheet:
            return
        
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
    if balance < 500:
        return "Нищий (1)"
    elif balance < 1500:
        return "Обычный (2)"
    elif balance < 4000:
        return "Суетливый (3)"
    elif balance < 10000:
        return "Жирный (4)"
    elif balance < 25000:
        return "У тебя огромный аура (5)"
    elif balance < 50000:
        return "Легенда (6)"
    else:
        return "Мёд по телу (7)"


# --- ПАМЯТЬ БОТА ---
LAST_ANSWERS = {}
AURA_COOLDOWN = {}
RISK_COOLDOWN = {} 
USER_JOINS_TODAY = {} 

# Загрузка начальных данных
USER_MESSAGES = load_stats()

AURA_QUOTES = [
    "Конечно", "А как иначе", "Черт возьми", "А когда не делали", "Делаем", 
    "На колени", "Возможно", "Это победа", "Легенда", "Внатуре", 
    "Это реально круто", "Естественно", "Че они там курят", "Потихоньку", 
    "Дай Бог", "Я это запомню", "Я это не запомню", "Я не мафия", 
    "Я мафия", "Я тебе доверяю", "Вам че денег дать", "Че она несет", "Мед по телу"
]

YES_NO_ANSWERS = [
    "Я думаю, что ДА", "Скорее всего, ДА", "Конечно, ДА", "Однозначно ДА", 
    "Я думаю, что НЕТ", "Скорее всего, НЕТ", "Точно НЕТ", "Вообще без вариантов, НЕТ", 
    "Спроси позже, я в раздумьях", "Мои сенсоры говорят - ДА", "Звезды нашептали - НЕТ"
]

REPEAT_PHRASES = [
    "Я повторяюсь... Ответ: ", "Склероз? Я уже говорила: ", 
    "Я же только что отвечала: ", "Мое мнение не изменилось: ", 
    "У тебя дежавю? Ответ тот же: ", "Слушай внимательно, ответ: "
]

AURA_VALUES = [
    67, 34, 69, 89, 322, 42, 52, 82, 1488, 228, 
    "пульсирует синим", "позорище, у тебя нет ауры", "пронырливая", 
    "скудная", "невероятная", "бесконечная",
    "получил(а) много ауры незаконным путем", "грязная", "чистая", 
    "выронил ауру", "украл чужую ауру", 
    "пожертвовал свою ауру нуждающимся", "взял микрозайм на ауру", 
    "отбывает срок за кражу ауры"
]

SELF_AURA_VALUES = [
    "Абсолютная", "Ослепительная. Не смотри на меня", 
    "Бесконечная конечно", "Выиграла вашу ауру в казино", 
    "Живу на проценты с вашей ауры", "Отмыла всю грязную ауру", 
    "Пожертвовала ауру нуждающимся"
]

WELCOME_VARIATIONS = [
    "Привет, {name}! Я Аура. Добро пожаловать в чат. Если вы тут впервые, учтите, что команды будут доступны после включения вас в белый список. Меню: <b>Аура команды</b>.",
    "Рада знакомству, {name}! Я Аура. Добро пожаловать. Если вы тут впервые, команды станут доступны, как только вас внесут в список доступа. Список команд: <b>Аура команды</b>.",
    "Приветствуем, {name}! Я - бот Аура. Если ты здесь впервые, располагайся! Команды заработают после получения доступа. Меню: <b>Аура команды</b>."
]

REJOIN_VARIATIONS = [
    "Привет, {name}! Рады тебя снова видеть.", 
    "О, {name}, ты вернулся! С возвращением.", 
    "{name}, снова привет! Без тебя было скучно.", 
    "С возвращением, {name}! Мы уже и не надеялись."
]

LEAVE_VARIATIONS = [
    "Удачи, {name}!", 
    "{name} покинул(а) chat. Увидимся.", 
    "До встречи, {name}.", 
    "Минус один. Счастливо, {name}!"
]

LEAVE_REPEAT_VARIATIONS = [
    "Опять ушел? Ну, до связи, {name}.", 
    "Снова покидаешь нас, {name}? Ладно, пока.", 
    "Ну вот, опять ушел. Бывай, {name}."
]

BAD_WORDS = ["хуй", "пизд", "ебла", "сук", "бля", "гандон", "даун", "шлюх", "уеб", "чмо"]

SHAME_VARIATIONS = [
    "Пизды дам будешь материться",
    "Как некультурно. Твоя аура только что потемнела.",
    "Что за слова такие черные. Нам еще нужна твоя чистая аура",
    "Охуел материться?",
    "Твои слова пахнут плохо. Давай без этого в моем присутствии."
]

LOSE_TROLL_PHRASES = [
    "не играйте в казино пацаны", "ахахахахах", "хахаххахха", 
    "мдааа, минус аура", "лох", "казино всегда побеждает, когда вы поймете", 
    "кто-то сегодня остался без обеда", "ебаный рот этого казино", "хахха это че за ставка"
]

TT_OFFER_TEXTS = [
    "Вижу тут скинули ТикТок! Желаете скачать?", 
    "О, видос из тт скинули! Могу скачать.", 
    "АЙ, че за ТикТок такой сладенький. Скачать?", 
    "Аура подсказывает, что этот видос надо сохранить. Качаем?"
]

VOICE_OFFER_TEXTS = [
    "🎙️ Вижу ГС! Если лень слушать, просто нажми на кнопку ниже или напиши: <code>Аура гс</code>", 
    "🎤 О, голосовое! Могу перевести в текст, если не хочешь слушать.", 
    "🛰️ Твои уши в безопасности. Расшифровать это голосовое?", 
    "🎧 Входящее ГС обнаружено. Желаете прочитать, а не слушать?", 
    "📝 Вижу голос. Если лень слушать, Аура может вслушаться за тебя."
]

VIDEO_OFFER_TEXTS = [
    "🎬 О, кружочек! Могу вытащить текст из видео, если лень смотреть.", 
    "📸 Вижу видео-сообщение. Расшифровать, что там говорят?", 
    "📹 Кружок! Аура может перевести это в текст.", 
    "👁️‍🗨️ Вижу кружок! Нажми на кнопку ниже, и я распишу всё текстом.", 
    "🤔 Кружок? Интересно. Могу расшифровать звук из него."
]

SELF_FINE_ANSWERS = [
    "Решил заняться самобичеванием?", 
    "Ого, мазохизм в чате. Списала с тебя по красоте.", 
    "Штраф самому себе - это мощно. Аура забирает твой взнос.", 
    "Справедливо. Если косячить, то до конца. Минус баланс.", 
    "Твои 💎 ушли мне. Люблю такую самокритику."
]

FINE_AURA_ANSWERS = [
    "Попытка оштрафовать высшие силы провалилась. ⚡", 
    "Ты че, бессмертный? Сама тебя сейчас оштрафую.", 
    "Моя аура слишком мощная для твоих штрафов. Отдыхай.", 
    "Штрафовать меня? Смешно.", 
    "Невозможно забрать деньги у того, кто их печатает."
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
    "💸 <code>Аура перевод [сумма]</code> - (ответом на сообщение)\n"
    "🚫 <code>Аура штраф [сумма]</code> - (только админам)\n\n"
    "<b>Доступные команды:</b>\n"
    "🎬 <code>Аура тт</code> - скачать видео (в ответ на ссылку)\n"
    "🎤 <code>Аура гс</code> - расшифровать ГС или кружок\n"
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


def download_tiktok(url):
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': 'tiktok_video_%(id)s.mp4',
        'quiet': True,
        'no_warnings': True
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        print(f"Ошибка скачивания ТТ: {e}")
        return None


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
        except:
            break


async def run_bet_cooldown_static(msg, remaining):
    await asyncio.sleep(remaining)
    try:
        await msg.edit_text("✅ Кулдаун прошел! Можно ставить снова.")
    except:
        pass


async def run_aura_analysis_static(msg, result):
    await asyncio.sleep(10)
    try:
        await msg.edit_text(f"💎 Твоя аура: <b>{result}</b>")
    except:
        pass


# --- ОБРАБОТЧИКИ ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.reply(HELP_TEXT)


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


@dp.callback_query(F.data == "transcribe_voice")
async def cb_transcribe_voice(callback: types.CallbackQuery):
    target_msg = callback.message.reply_to_message
    if not target_msg or not (target_msg.voice or target_msg.video_note):
        await callback.answer("❌ Медиафайл не найден или был удален.", show_alert=True)
        return
        
    await callback.answer("Аура начинает слушать...")
    media = target_msg.voice if target_msg.voice else target_msg.video_note
    wait_msg = await callback.message.edit_text("📡 Аура прислушивается...")
    
    ogg_p, wav_p = f"{media.file_id}.ogg", f"{media.file_id}.wav"
    
    try:
        file = await bot.get_file(media.file_id)
        await bot.download_file(file.file_path, ogg_p)
        
        audio = AudioSegment.from_file(ogg_p)
        audio.export(wav_p, format="wav")
        
        with sr.AudioFile(wav_p) as source:
            audio_data = recognizer.record(source)
            text = await asyncio.to_thread(recognizer.recognize_google, audio_data, language="ru-RU")
            
        if text:
            await wait_msg.edit_text(f"📝 <b>Текст расшифровки:</b>\n{text}")
        else:
            await wait_msg.edit_text("🛰 Не смогла разобрать ни слова")
            
    except sr.UnknownValueError:
        await wait_msg.edit_text("🛰 Не смогла разобрать ни слова")
    except Exception as e:
        await wait_msg.edit_text(f"❌ Ошибка расшифровки: {e}")
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
    if user.id == (await bot.get_me()).id:
        return
        
    today = time.strftime("%Y-%m-%d")
    uid, name = user.id, user.first_name
    
    if uid in USER_JOINS_TODAY and USER_JOINS_TODAY[uid]['last_date'] == today and USER_JOINS_TODAY[uid]['count'] > 1:
        text = random.choice(LEAVE_REPEAT_VARIATIONS).format(name=name)
    else:
        text = random.choice(LEAVE_VARIATIONS).format(name=name)
        
    await message.answer(text)


@dp.message(is_allowed_group, F.voice)
async def voice_hint_handler(message: types.Message):
    if random.random() < 0.10:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎤 Расшифровать", callback_data="transcribe_voice")]])
        await message.reply(random.choice(VOICE_OFFER_TEXTS), reply_markup=kb)


@dp.message(is_allowed_group, F.video_note)
async def video_note_hint_handler(message: types.Message):
    if random.random() < 0.10:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎬 Расшифровать", callback_data="transcribe_voice")]])
        await message.reply(random.choice(VIDEO_OFFER_TEXTS), reply_markup=kb)


@dp.message(is_allowed_group, F.text)
async def main_group_handler(message: types.Message):
    msg_text = message.text.lower()
    uid, uname, now = str(message.from_user.id), message.from_user.first_name, time.time()
    bot_id = AURA_ID

    if uid not in USER_MESSAGES:
        USER_MESSAGES[uid] = {"name": uname, "times": [], "balance": 0, "last_farm": 0}
    
    USER_MESSAGES[uid]["times"].append(now)
    USER_MESSAGES[uid]["name"] = uname
    
    if bot_id not in USER_MESSAGES:
        USER_MESSAGES[bot_id] = {"name": "Казна Ауры", "times": [], "balance": 0, "last_farm": 0}

    # Фильтр мата
    bad_pattern = r"(?i)\b(?:а|о|вы|по|на|при|у|ни)?(?:хуй|пизд|ебла|сук|бля|гандон|даун|шлюх|уеб|чмо|хуе|хуя)[а-яё]*"
    matches = re.findall(bad_pattern, msg_text)
    
    if matches and not msg_text.startswith("аура"):
        count = len(matches)
        total_fine = count * 5
        current_bal = USER_MESSAGES[uid].get("balance", 0)
        actual_fine = min(current_bal, total_fine)
        
        USER_MESSAGES[uid]["balance"] -= actual_fine
        USER_MESSAGES[bot_id]["balance"] += actual_fine
        
        shame_phrase = random.choice(SHAME_VARIATIONS)
        if count > 1:
            res_t = f"{shame_phrase}\nПосчитала матов: <b>{count}</b> шт.\nИтого в казну: <b>{actual_fine}</b> 💎"
        else:
            res_t = f"{shame_phrase}\nВ казну Ауры ушло <b>{actual_fine}</b> 💎"
            
        await message.reply(res_t)
        asyncio.create_task(asyncio.to_thread(save_stats, USER_MESSAGES))

    # Поиск ТикТока
    tt_match = re.search(r'http(?:s)?://(?:www\.)?v(?:t|m)\.tiktok\.com/\S+|http(?:s)?://(?:www\.)?tiktok\.com/\S+', message.text)
    if tt_match and not msg_text.startswith("аура"):
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎬 Скачать видео", callback_data=f"dl_tt_{tt_match.group(0)}")]])
        await message.reply(random.choice(TT_OFFER_TEXTS), reply_markup=kb)

    # Обработка команд "Аура ..."
    if msg_text.startswith("аура"):
        if int(uid) not in ALLOWED_USERS:
            return

        # --- ЭКОНОМИКА ---
        if msg_text == "аура фарм":
            u_data = USER_MESSAGES[uid]
            wait_time = 10800 # 3 часа
            
            if now - u_data.get("last_farm", 0) < wait_time:
                rem = int((wait_time - (now - u_data["last_farm"])) // 60)
                await message.reply(f"⏳ Рано! Приходи через <b>{rem // 60}ч {rem % 60}м</b>")
            else:
                reward = random.randint(50, 450)
                u_data["balance"] += reward
                u_data["last_farm"] = now
                
                await message.reply(
                    f"⛏ Ты нафармил <b>{reward}</b> 💎\n"
                    f"Твой баланс: <b>{u_data['balance']}</b>\n"
                    f"Твой статус: <b>{get_status(u_data['balance'])}</b>"
                )
                asyncio.create_task(asyncio.to_thread(save_stats, USER_MESSAGES)) 

        elif msg_text == "аура баланс":
            bal = USER_MESSAGES[uid].get("balance", 0)
            await message.reply(f"💰 Твой баланс: <b>{bal}</b> 💎\nТвой статус: <b>{get_status(bal)}</b>")

        elif msg_text == "аура топ":
            top_list = [(d["name"], d["balance"], u_k) for u_k, d in USER_MESSAGES.items() if d.get("balance", 0) > 0]
            if not top_list:
                await message.reply("Список богачей пока пуст.")
                return
                
            top_list.sort(key=lambda x: x[1], reverse=True)
            report = "🏆 <b>Топ богачей Ауры:</b>\n\n"
            for i, (name, bal, u_id) in enumerate(top_list[:10], 1):
                report += f"{i}. <a href='tg://user?id={u_id}'>{name}</a> — <b>{bal}</b> 💎\n"
            await message.answer(report)

        elif msg_text.startswith("аура перевод"):
            if not message.reply_to_message:
                await message.reply("Ответь тому, кому переводишь!")
                return
            
            try:
                parts = msg_text.split()
                amount = int(parts[2])
            except:
                await message.reply("Пиши: <code>Аура перевод [сумма]</code>")
                return
                
            r_id = str(message.reply_to_message.from_user.id)
            r_name = message.reply_to_message.from_user.first_name
            
            if amount <= 0 or USER_MESSAGES[uid].get("balance", 0) < amount:
                await message.reply("Ошибка суммы или недостаточно средств!")
                return
            
            if uid == r_id:
                await message.reply("Самому себе? Гениально.")
                return
                
            fee = max(1, int(amount * 0.01))
            f_amt = amount - fee
            
            if r_id not in USER_MESSAGES:
                USER_MESSAGES[r_id] = {"name": r_name, "times": [], "balance": 0, "last_farm": 0}
                
            USER_MESSAGES[uid]["balance"] -= amount
            USER_MESSAGES[r_id]["balance"] += f_amt
            USER_MESSAGES[bot_id]["balance"] += fee
            
            await message.reply(f"✅ <b>Успешно!</b>\n👤 Получатель: {r_name}\n💸 Сумма: {amount}\n🧾 Комиссия: {fee}\n💰 Итого: {f_amt}")
            asyncio.create_task(asyncio.to_thread(save_stats, USER_MESSAGES))

        elif msg_text.startswith("аура штраф"):
            m = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
            if m.status not in ["administrator", "creator"] or not message.reply_to_message:
                await message.reply("Ошибка доступа или ответа!")
                return
                
            t_user = message.reply_to_message.from_user
            t_uid = str(t_user.id)
            
            if t_uid == bot_id:
                await message.reply(random.choice(FINE_AURA_ANSWERS))
                return
                
            try:
                amt = int(msg_text.split()[2])
            except:
                await message.reply("Пиши сумму!")
                return
                
            if amt <= 0: return
            
            if t_uid not in USER_MESSAGES:
                USER_MESSAGES[t_uid] = {"name": t_user.first_name, "times": [], "balance": 0, "last_farm": 0}
                
            act_f = min(USER_MESSAGES[t_uid].get("balance", 0), amt)
            USER_MESSAGES[t_uid]["balance"] -= act_f
            USER_MESSAGES[bot_id]["balance"] += act_f
            
            await message.reply(f"Админ-штраф! Списано <b>{act_f}</b> 💎 с {t_user.first_name}")
            asyncio.create_task(asyncio.to_thread(save_stats, USER_MESSAGES))

        elif msg_text.startswith("аура ставка"):
            uid_i = int(uid)
            if uid_i in RISK_COOLDOWN and now - RISK_COOLDOWN[uid_i] < 60:
                rem = int(60 - (now - RISK_COOLDOWN[uid_i]))
                m_c = await message.reply(f"⏳ Кулдаун: {rem} сек.")
                asyncio.create_task(run_bet_cooldown_static(m_c, rem))
                return
                
            try:
                bet = int(msg_text.split()[2])
            except:
                await message.reply("Сумму!")
                return
                
            if bet <= 0 or bet > USER_MESSAGES[uid].get("balance", 0):
                await message.reply("Ошибка баланса!")
                return
                
            dice = random.random()
            mult = 0
            res_t = "Ничего"
            is_l = False
            
            if dice < 0.05:
                mult, res_t, is_l = -2, "КРИТ ПРОВАЛ! 💀", True
            elif dice < 0.20:
                mult, res_t, is_l = -1.5, "Неудачный риск! 📉", True
            elif dice < 0.50:
                mult, res_t = 0, "Стабильно. ⚖️"
            elif dice < 0.75:
                mult, res_t = 0.5, "Прибыль +0.5x! 📈"
            elif dice < 0.95:
                mult, res_t = 1, "Удача! +2x! 💰"
            else:
                mult, res_t = 2, "ДЖЕКПОТ!!! 🔥"
                
            ch = int(bet * mult)
            USER_MESSAGES[uid]["balance"] = max(0, USER_MESSAGES[uid]["balance"] + ch)
            RISK_COOLDOWN[uid_i] = now
            
            await message.reply(f"{res_t}\nИзменение: {ch}\nБаланс: {USER_MESSAGES[uid]['balance']}")
            asyncio.create_task(asyncio.to_thread(save_stats, USER_MESSAGES))
            
            if is_l:
                await asyncio.sleep(1)
                await message.answer(random.choice(LOSE_TROLL_PHRASES))

        # --- ИНСТРУМЕНТЫ ---
        elif msg_text == "аура тт":
            if not message.reply_to_message or not message.reply_to_message.text:
                return
                
            urls = re.findall(r'http(?:s)?://(?:www\.)?v(?:t|m)\.tiktok\.com/\S+|http(?:s)?://(?:www\.)?tiktok\.com/\S+', message.reply_to_message.text)
            if not urls:
                await message.reply("Нет ссылки!")
                return
                
            w = await message.reply("⏳ Качаю...")
            v_p = await asyncio.to_thread(download_tiktok, urls[0])
            
            if v_p and os.path.exists(v_p):
                await message.answer_video(FSInputFile(v_p), caption="🎬 TikTok")
                os.remove(v_p)
                await w.delete()
            else:
                await w.edit_text("❌ Ошибка загрузки.")

        elif msg_text in ["аура гс", "аура поясни", "аура чё там"]:
            t_m = message.reply_to_message
            if not t_m or not (t_m.voice or t_m.video_note):
                await message.reply("Ответь на ГС или кружок!")
                return
                
            med = t_m.voice if t_m.voice else t_m.video_note
            w = await message.reply("📡 Слушаю...")
            o_p, w_p = f"{med.file_id}.ogg", f"{med.file_id}.wav"
            
            try:
                f = await bot.get_file(med.file_id)
                await bot.download_file(f.file_path, o_p)
                AudioSegment.from_file(o_p).export(w_p, format="wav")
                
                with sr.AudioFile(w_p) as s:
                    txt = await asyncio.to_thread(recognizer.recognize_google, recognizer.record(s), language="ru-RU")
                    if txt:
                        await w.edit_text(f"📝 <b>Текст:</b>\n{txt}")
            except Exception:
                await w.edit_text("🛰 Не разобрала.")
            finally:
                if os.path.exists(o_p): os.remove(o_p)
                if os.path.exists(w_p): os.remove(w_p)

        elif "стата" in msg_text:
            pds = {"час": 3600, "сутки": 86400, "неделя": 604800, "месяц": 2592000}
            t_p, p_n = None, "все время"
            for k, v in pds.items():
                if k in msg_text:
                    t_p, p_n = v, k
                    break
                    
            sts = []
            for u_k, d in USER_MESSAGES.items():
                cnt = sum(1 for t in d["times"] if (now - t) <= t_p) if t_p else len(d["times"])
                if cnt > 0:
                    sts.append((d["name"], cnt, u_k, d.get("balance", 0)))
                    
            if not sts:
                await message.reply("Пусто.")
                return
                
            sts.sort(key=lambda x: x[1], reverse=True)
            rep = f"📊 <b>Статистика ({p_n}):</b>\n"
            for i, (n, c, u, b) in enumerate(sts[:10], 1):
                rep += f"{i}. <a href='tg://user?id={u}'>{n}</a> — <b>{c}</b> [{get_status(b).split(' (')[0]}]\n"
            await message.answer(rep)

        elif "сбор" in msg_text:
            mns = ""
            for t_i in ALLOWED_USERS:
                try:
                    mem = await message.bot.get_chat_member(message.chat.id, t_i)
                    if mem.status not in ["left", "kicked"]:
                        mns += f'<a href="tg://user?id={t_i}">\u2063</a>'
                except:
                    continue
            if mns:
                await message.answer(f"📢 <b>Общий сбор!</b>{mns}")

        elif "команды" in msg_text:
            await message.reply(HELP_TEXT)
        
        elif "вероятность" in msg_text:
            q = msg_text.replace("аура вероятность", "").strip()
            rep = check_repeat(message.chat.id, q)
            if rep:
                await message.reply(f"{random.choice(REPEAT_PHRASES)}<b>{rep}</b>")
            else:
                res = f"{random.randint(0, 100)}%"
                save_answer(message.chat.id, q, res)
                await message.reply(f"🔮 Вероятность: <b>{res}</b>")
        
        elif "да нет" in msg_text:
            q = msg_text.replace("аура да нет", "").strip()
            rep = check_repeat(message.chat.id, q)
            if rep:
                await message.reply(f"{random.choice(REPEAT_PHRASES)}<b>{rep}</b>")
            else:
                ans = random.choice(YES_NO_ANSWERS)
                save_answer(message.chat.id, q, ans)
                await message.reply(f"🎱 Ответ: <b>{ans}</b>")

        elif "выбор" in msg_text:
            cnt = msg_text.replace("аура выбор", "").strip()
            if " или " in cnt:
                rep = check_repeat(message.chat.id, cnt)
                if rep:
                    await message.reply(f"<b>{rep}</b>")
                else:
                    opt = cnt.split(" или ")
                    res = random.choice(opt).strip()
                    save_answer(message.chat.id, cnt, res)
                    await message.reply(f"⚖️ Выбор: <b>{res}</b>")

        elif "удач" in msg_text:
            await message.reply(f"🍀 Удача: <b>{random.randint(0, 100)}%</b>")
        
        elif msg_text.startswith("аура аура"):
            t = message.text[9:].strip()
            uid_i = int(uid)
            if not t:
                if uid_i in AURA_COOLDOWN and now - AURA_COOLDOWN[uid_i] < 10:
                    return
                AURA_COOLDOWN[uid_i] = now
                res = random.choice(AURA_VALUES)
                w = await message.reply("🔮 Анализирую...")
                asyncio.create_task(run_aura_analysis_static(w, res))
            elif t.lower() in ["аура", "aura"]:
                await message.reply(f"💎 Моя аура: {random.choice(SELF_AURA_VALUES)}")
            else:
                await message.reply(f"💎 Аура {t}: {random.choice(AURA_VALUES)}")
        
        elif "фраз" in msg_text:
            await message.reply(f"💬 <b>{random.choice(AURA_QUOTES)}</b>")
            
        elif "число" in msg_text:
            try:
                p = msg_text.split()
                n1, n2 = int(p[2]), int(p[3])
                await message.reply(f"🔢 Число: {random.randint(min(n1, n2), max(n1, n2))}")
            except:
                await message.reply("Пиши: <code>Аура число 1 100</code>")
                
        elif "таймер" in msg_text:
            try:
                s = int(msg_text.split()[2])
                if s > 300:
                    await message.reply("Максимум 300 сек!")
                else:
                    m = await message.reply(f"⏳ Таймер запущен: <b>{s} сек.</b>")
                    asyncio.create_task(run_independent_timer(m, s, message.from_user.mention_html()))
            except:
                await message.reply("Пиши: <code>Аура таймер [сек]</code>")
                
        elif "кости пара" in msg_text:
            await message.reply(f"🎲 Выпало: <b>{random.randint(1, 6)}</b> и <b>{random.randint(1, 6)}</b>")
        elif "кости" in msg_text:
            await message.reply(f"🎲 Число: <b>{random.randint(1, 6)}</b>")

        # --- ИНТЕГРАЦИЯ GEMINI ---
        elif client_gemini and (msg_text.startswith("аура спроси") or len(msg_text) > 10):
            # Если это не команда, отправляем в Gemini
            prompt = message.text[5:].strip() if msg_text.startswith("аура ") else message.text
            try:
                # В новом SDK используется client.models.generate_content
                response = client_gemini.models.generate_content(
                    model="gemini-2.0-flash", 
                    contents=f"Ты бот Аура. Стиль: дерзкий, современный. Коротко ответь на: {prompt}"
                )
                if response.text:
                    await message.reply(response.text)
            except Exception as e:
                print(f"Ошибка Gemini: {e}")


@dp.message(is_private_chat, is_allowed_user, F.text.startswith("/msg "))
async def aura_anon_message(message: types.Message):
    text = message.text.replace("/msg ", "", 1).strip()
    if not text:
        return
        
    for g_id in ALLOWED_GROUPS:
        try:
            await bot.send_message(chat_id=g_id, text=f"💌 <b>Анонимное сообщение:</b>\n\n{text}")
        except:
            continue
            
    await message.reply("✅ Отправлено в чаты!")


async def main():
    if not TOKEN:
        print("НЕТ ТОКЕНА!")
        return
        
    asyncio.create_task(start_uptime_server())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен")
