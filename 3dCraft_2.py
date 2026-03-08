
from aiogram import Bot, Dispatcher, types, F
from token import TOKEN,ADMIN_ID
import asyncio
import aiosqlite
from aiogram.filters import Command,CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramForbiddenError
import token
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Стан для розсилки
class Broadcast(StatesGroup):
    writing = State()
    confirming = State()

# --- РОБОТА З БАЗОЮ (АСИНХРОННО) ---
async def init_db():
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
        await db.commit()

async def add_user(user_id):
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.commit()

# --- ХЕНДЛЕРИ ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await add_user(message.from_user.id)
    await message.answer("Ви зареєстровані для розсилки!")

# Початок створення розсилки (тільки для адміна)
@dp.message(Command("broadcast"), F.from_user.id == ADMIN_ID)
async def start_broadcast(message: types.Message, state: FSMContext):
    await message.answer("Надішліть текст розсилки:")
    await state.set_state(Broadcast.writing)

@dp.message(Broadcast.writing, F.from_user.id == ADMIN_ID)
async def get_text(message: types.Message, state: FSMContext):
    await state.update_data(text=message.text)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Пуск", callback_data="go")
    builder.button(text="❌ Відміна", callback_data="cancel")
    
    await message.answer(f"Текст розсилки:\n\n{message.text}\n\nНадсилаємо?", 
                         reply_markup=builder.as_markup())
    await state.set_state(Broadcast.confirming)

@dp.callback_query(Broadcast.confirming, F.data == "go")
async def send_broadcast(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data['text']
    await state.clear()
    
    await callback.message.edit_text("🚀 Розпочинаю відправку...")
    
    count = 0
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            async for row in cursor:
                user_id = row[0]
                try:
                    await bot.send_message(user_id, text)
                    count += 1
                    await asyncio.sleep(0.05) # Анти-флуд
                except TelegramForbiddenError:
                    pass # Користувач забанив бота
                except Exception as e:
                    print(f"Помилка {user_id}: {e}")
    
    await callback.message.answer(f"✅ Розсилка завершена!\nОтримали: {count} осіб.")

@dp.callback_query(F.data == "cancel")
async def cancel_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Скасовано.")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())