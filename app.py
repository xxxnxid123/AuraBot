import asyncio, random, os, time, json
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

# --- ДАННЫЕ ---
def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}

def save_stats(st):
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f: json.dump(st, f, ensure_ascii=False, indent=4)
    except: pass

USER_MESSAGES = load_stats()
AURA_QUOTES = ["Конечно", "А как иначе", "Черт возьми", "Делаем", "На колени", "Возможно", "Это победа", "Легенда", "Внатуре", "Это реально круто", "Естественно", "Потихоньку", "Дай Бог", "Я это запомню", "Мед по телу"]
YES_NO_ANSWERS = ["Я думаю, что ДА", "Скорее всего, ДА", "Конечно, ДА", "Однозначно ДА", "Я думаю, что НЕТ", "Скорее всего, НЕТ", "Точно НЕТ", "Спроси позже", "Мои сенсоры говорят - ДА", "Звезды нашептали - НЕТ"]
BAD_WORDS = ["хуй", "пизд", "ебла", "сук", "бля", "гандон", "даун", "шлюх", "уеб", "чмо"]
SHAME_VARIATIONS = ["С такими выражениями твоя аура начнет сыпаться уже в 35 лет", "Из-за этих слов твоя аура только что потемнела", "Маты загрязняют твою ауру"]

HELP_TEXT = "✨ <b>Я Аура!</b> ✨\n\n<b>💎 ЭКОНОМИКА:</b>\n⛏ <code>Аура фарм</code> — раз в 3 часа\n💰 <code>Аура баланс</code>\n🛒 <code>Аура магазин</code>\n\n<b>🔮 КОМАНДЫ:</b>\n🔮 Вероятность | 🎱 Да/Нет | ⚖️ Выбор\n📊 Стата | 💬 Фраза | 🍀 Удача\n🎲 Кости | ⏳ Таймер | 📢 Сбор"

# --- КНОПКИ ---
def get_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⛏ Фарм (Раз в 3ч)", callback_data="farm_aura")],
        [InlineKeyboardButton(text="🛒 Магазин", callback_data="open_shop")],
        [InlineKeyboardButton(text="💎 Баланс", callback_data="check_balance")]
    ])

def get_shop_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎖 Админка (5000💎)", callback_data="buy_admin")],
        [InlineKeyboardButton(text="🏷 Сменить тег (500💎)", callback_data="buy_tag")],
        [InlineKeyboardButton(text="💸 Перевести 💎", callback_data="transfer_start")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")]
    ])

# --- CALLBACKS ---
@dp.callback_query(F.data == "farm_aura")
async def cb_farm(callback: CallbackQuery):
    uid = str(callback.from_user.id)
    if int(uid) not in ALLOWED_USERS: await callback.answer("Нет доступа", show_alert=True); return
    now = time.time(); u = USER_MESSAGES.get(uid, {"balance": 0, "last_farm": 0})
    if now - u.get("last_farm", 0) < 10800:
        rem = int((10800 - (now - u["last_farm"])) // 60)
        await callback.answer(f"⏳ Жди {rem // 60}ч {rem % 60}мин", show_alert=True); return
    rew = random.randint(50, 400); USER_MESSAGES[uid]["balance"] = u.get("balance", 0) + rew
    USER_MESSAGES[uid]["last_farm"] = now; save_stats(USER_MESSAGES)
    await callback.message.answer(f"⛏ +{rew} 💎! Баланс: {USER_MESSAGES[uid]['balance']}"); await callback.answer()

@dp.callback_query(F.data == "check_balance")
async def cb_bal(callback: CallbackQuery):
    uid = str(callback.from_user.id)
    bal = "∞" if int(uid) == ALLOWED_USERS[0] else USER_MESSAGES.get(uid, {}).get("balance", 0)
    await callback.answer(f"Твой баланс: {bal} 💎", show_alert=True)

@dp.callback_query(F.data == "open_shop")
async def cb_shop(callback: CallbackQuery):
    await callback.message.edit_text("🛒 <b>Магазин Ауры</b>", reply_markup=get_shop_kb())

@dp.callback_query(F.data == "back_to_main")
async def cb_back(callback: CallbackQuery):
    await callback.message.edit_text(HELP_TEXT, reply_markup=get_main_kb())

@dp.callback_query(F.data == "buy_admin")
async def cb_buy_admin(callback: CallbackQuery):
    await callback.message.answer("📝 Введи текст для админки (ответь на это сообщение):", reply_markup=ForceReply(selective=True)); await callback.answer()

@dp.callback_query(F.data == "buy_tag")
async def cb_buy_tag(callback: CallbackQuery):
    await callback.message.answer("🏷 Введи новый тег (ответь на это сообщение):", reply_markup=ForceReply(selective=True)); await callback.answer()

@dp.callback_query(F.data == "transfer_start")
async def cb_transfer(callback: CallbackQuery):
    await callback.message.answer("💸 <b>Перевод Ауры:</b>\nОтветь на сообщение того, кому хочешь скинуть 💎, и напиши сумму.", reply_markup=ForceReply(selective=True)); await callback.answer()

# --- ГЛАВНЫЙ ОБРАБОТЧИК ---
@dp.message(F.chat.id.in_(ALLOWED_GROUPS), F.text)
async def main_handler(message: types.Message):
    txt = message.text.lower(); uid = str(message.from_user.id); now = time.time(); owner = int(uid) == ALLOWED_USERS[0]
    if uid not in USER_MESSAGES: USER_MESSAGES[uid] = {"name": message.from_user.first_name, "times": [], "balance": 0, "last_farm": 0}
    USER_MESSAGES[uid]["times"].append(now); save_stats(USER_MESSAGES)

    # Логика ответов (ForceReply) и Переводов
    if message.reply_to_message:
        rt = message.reply_to_message.text; val = message.text.strip()
        if message.reply_to_message.from_user.id == (await bot.get_me()).id:
            if "текст для админки" in rt or "новый тег" in rt:
                price = 5000 if "админки" in rt else 500
                if not owner and USER_MESSAGES[uid]["balance"] < price:
                    await message.reply("❌ Мало 💎"); return
                try:
                    if "админки" in rt: await bot.promote_chat_member(message.chat.id, int(uid), can_manage_chat=True)
                    await bot.set_chat_administrator_custom_title(message.chat.id, int(uid), val)
                    if not owner: USER_MESSAGES[uid]["balance"] -= price
                    save_stats(USER_MESSAGES); await message.reply(f"✅ Успешно! Тег: <b>{val}</b>")
                except: await message.reply("❌ Ошибка прав.")
                return
        elif val.isdigit() and not message.reply_to_message.from_user.is_bot:
            amt = int(val); tid = str(message.reply_to_message.from_user.id)
            if amt > 0 and (owner or USER_MESSAGES[uid]["balance"] >= amt) and tid != uid:
                if tid not in USER_MESSAGES: USER_MESSAGES[tid] = {"name": message.reply_to_message.from_user.first_name, "times": [], "balance": 0, "last_farm": 0}
                if not owner: USER_MESSAGES[uid]["balance"] -= amt
                USER_MESSAGES[tid]["balance"] += amt; save_stats(USER_MESSAGES)
                await message.reply(f"💸 Переведено {amt} 💎 пользователю {USER_MESSAGES[tid]['name']}")
                return

    if txt.startswith("аура"):
        if int(uid) not in ALLOWED_USERS: return
        if txt == "аура фарм":
            u = USER_MESSAGES[uid]
            if now - u["last_farm"] < 10800:
                r = int((10800-(now-u["last_farm"]))//60)
                await message.reply(f"⏳ Жди {r//60}ч {r%60}м")
            else:
                rew = random.randint(50, 400); u["balance"] += rew; u["last_farm"] = now
                save_stats(USER_MESSAGES); await message.reply(f"⛏ +{rew} 💎! Баланс: {u['balance']}")
        elif txt == "аура баланс": await message.reply(f"💎 Баланс: <b>{'∞' if owner else USER_MESSAGES[uid]['balance']}</b>")
        elif txt == "аура магазин": await message.reply("🛒 Магазин", reply_markup=get_shop_kb())
        elif "стата" in txt:
            stats = sorted([(d["name"], sum(1 for t in d["times"] if (now-t)<=86400)) for d in USER_MESSAGES.values()], key=lambda x: x[1], reverse=True)
            await message.answer("📊 <b>Топ за сутки:</b>\n" + "\n".join([f"{i}. {n} — {c}" for i, (n, c) in enumerate(stats[:10], 1)]))
        elif "команды" in txt: await message.reply(HELP_TEXT, reply_markup=get_main_kb())
        elif "вероятность" in txt: await message.reply(f"🔮: {random.randint(0, 100)}%")
        elif "да нет" in txt: await message.reply(f"🎱: {random.choice(YES_NO_ANSWERS)}")
        elif "выбор" in txt:
            opts = txt.replace("аура выбор", "").split(" или ")
            if len(opts) > 1: await message.reply(f"⚖️: {random.choice(opts).strip()}")
        elif "удач" in txt: await message.reply(f"🍀: {random.randint(0, 100)}%")
        elif "фраз" in txt: await message.reply(f"💬 {random.choice(AURA_QUOTES)}")
        elif "кости" in txt: await message.reply(f"🎲: {random.randint(1, 6)}")
        elif "сбор" in txt:
            mentions = "".join([f'<a href="tg://user?id={tid}">\u2063</a>' for tid in ALLOWED_USERS])
            await message.answer(f"📢 <b>Общий сбор!</b>{mentions}")

    if any(w in txt for w in BAD_WORDS) and random.random() < 0.2: await message.reply(random.choice(SHAME_VARIATIONS))

async def handle(r): return web.Response(text="Aura")
async def main():
    asyncio.create_task(web._run_app(web.Application().add_routes([web.get('/', handle)]), port=int(os.environ.get("PORT", 8080))))
    await bot.delete_webhook(drop_pending_updates=True); await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())
