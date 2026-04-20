import asyncio
import random
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# --- НАСТРОЙКИ ---
TOKEN = os.environ.get('BOT_TOKEN')

def get_ids(env_name):
    data = os.environ.get(env_name, "")
    return [int(i.strip()) for i in data.split(",") if i.strip().replace("-", "").isdigit()]

ALLOWED_GROUPS = get_ids('ALLOWED_GROUPS')
ALLOWED_USERS = get_ids('ALLOWED_USERS')

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Список твоих легендарных фраз
AURA_QUOTES = [
    "Конечно", "А как иначе", "Черт возьми", "А когда не делали", 
    "Никогда не делали", "Делаем", "На колени", "Возможно", 
    "Это победа", "Легенда", "Внатуре", "Это реально круто", 
    "Естественно", "Че они там курят", "Потихоньку", "Дай Бог", 
    "Я это запомню", "Я это не запомню", "Я не мафия", "Я мафия", 
    "Я тебе доверяю", "Вам че денег дать", "Че она несет", "Мед по телу"
]

# --- ФИЛЬТРЫ ---
is_allowed_user = F.from_user.id.in_(ALLOWED_USERS)
is_allowed_group = F.chat.id.in_(ALLOWED_GROUPS)
is_private_chat = F.chat.type == "private"

# --- ВЕБ-СЕРВЕР ---
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

# --- КОМАНДЫ ---

@dp.message(is_allowed_group, is_allowed_user, F.text.lower().startswith("аура вероятность"))
async def aura_probability(message: types.Message):
    await message.reply(f"🔮 Вероятность: <b>{random.randint(0, 100)}%</b>")

@dp.message(is_allowed_group, is_allowed_user, F.text.lower().startswith("аура да нет"))
async def aura_yes_no(message: types.Message):
    # Добавил твои фразы в рандом
    ans = random.choice(["Конечно", "Возможно", "А как иначе", "Точно нет", "Да!", "Нет."])
    await message.reply(f"🎱 Ответ: <b>{ans}</b>")

# НОВАЯ КОМАНДА: Аура фраза
@dp.message(is_allowed_group, is_allowed_user, F.text.lower().startswith("аура фраза"))
async def aura_random_quote(message: types.Message):
    quote = random.choice(AURA_QUOTES)
    await message.reply(f"💬 <b>{quote}</b>")

@dp.message(is_allowed_group, is_allowed_user, F.text.lower().startswith("аура кто"))
async def aura_who(message: types.Message):
    user_id = random.choice(ALLOWED_USERS)
    await message.reply(f"🎯 Я выбираю <a href='tg://user?id={user_id}'>этого человека</a>!")

@dp.message(is_allowed_group, is_allowed_user, F.text.lower().startswith("аура удача"))
async def aura_luck(message: types.Message):
    luck = random.randint(0, 100)
    await message.reply(f"🍀 Удача сегодня: <b>{luck}%</b>")

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

# --- ЗАПУСК ---
async def main():
    if not TOKEN: return
    asyncio.create_task(start_uptime_server())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
