#!/usr/bin/env python3

import asyncio
import sqlite3
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not BOT_TOKEN:
    print("Xato: BOT_TOKEN topilmadi. .env faylga BOT_TOKEN=... qo'ying.")
    exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

DB_PATH = "tasks.db"

pending_edit = {}
pending_add = set()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def add_task(user_id: int, text: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO tasks (user_id, text) VALUES (?, ?)", (user_id, text))
    conn.commit()
    tid = cur.lastrowid
    conn.close()
    return tid

def get_tasks(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, text FROM tasks WHERE user_id = ? ORDER BY id", (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_task_by_id(user_id: int, task_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, text FROM tasks WHERE user_id = ? AND id = ?", (user_id, task_id))
    row = cur.fetchone()
    conn.close()
    return row

def delete_task(user_id: int, task_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks WHERE user_id = ? AND id = ?", (user_id, task_id))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok

def edit_task(user_id: int, task_id: int, new_text: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE tasks SET text = ? WHERE user_id = ? AND id = ?", (new_text, user_id, task_id))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok

def task_inline_kb(task_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Edit", callback_data=f"edit:{task_id}"),
                InlineKeyboardButton(text="🗑️ Delete", callback_data=f"delete:{task_id}")
            ]
        ]
    )
    return kb

def start_reply_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Vazifa qo'shish"), KeyboardButton(text="Mening vazifalarim")],
        ],
        resize_keyboard=True
    )
    return kb

@dp.message(Command("start"))
async def cmd_start(message: Message):
    text = (
        "Salom! 👋\n"
        "Quyidagilardan birini tanlang yoki komandalarni yozing:\n\n"
        "/add <matn> — qo'shish\n"
        "/mytasks — vazifalarni ko'rish\n"
        "/delete <id> — o'chirish\n"
        "/edit <id> <yangi matn> — tahrirlash\n\n"
        "Oddiy tugmalar: 'Vazifa qo\'shish' va 'Mening vazifalarim'."
    )
    await message.answer(text, reply_markup=start_reply_kb())

@dp.message(lambda m: m.text == "Vazifa qo'shish")
async def btn_add_task(message: Message):
    user_id = message.from_user.id
    pending_add.add(user_id)
    await message.answer("✍️ Yangi vazifa matnini yuboring (bekor qilish uchun /cancel).", reply_markup=ReplyKeyboardRemove())

@dp.message(lambda m: m.text == "Mening vazifalarim")
async def btn_mytasks(message: Message):
    await send_user_tasks(message.from_user.id, chat_id=message.chat.id)

@dp.message(Command("add"))
async def cmd_add(message: Message):
    args = message.text.replace("/add", "", 1).strip()
    if not args:
        pending_add.add(message.from_user.id)
        await message.answer("✍️ Vazifa matnini yuboring (bekor uchun /cancel).", reply_markup=ReplyKeyboardRemove())
        return
    tid = add_task(message.from_user.id, args)
    await message.answer(f"✅ Vazifa qo'shildi (ID: {tid})", reply_markup=start_reply_kb())

@dp.message(Command("mytasks"))
async def cmd_mytasks(message: Message):
    await send_user_tasks(message.from_user.id, chat_id=message.chat.id)

@dp.message(Command("cancel"))
async def cmd_cancel(message: Message):
    uid = message.from_user.id
    removed = False
    if uid in pending_add:
        pending_add.discard(uid)
        removed = True
    if uid in pending_edit:
        pending_edit.pop(uid, None)
        removed = True
    if removed:
        await message.answer("✅ Amal bekor qilindi.", reply_markup=start_reply_kb())
    else:
        await message.answer("Bekor qilish uchun hech nima yo'q.", reply_markup=start_reply_kb())

@dp.message(Command("delete"))
async def cmd_delete_text(message: Message):
    args = message.text.replace("/delete", "", 1).strip()
    if not args.isdigit():
        await message.answer("Iltimos: /delete <id>. Misol: /delete 3")
        return
    ok = delete_task(message.from_user.id, int(args))
    if ok:
        await message.answer("🗑️ Vazifa o'chirildi.", reply_markup=start_reply_kb())
    else:
        await message.answer("Topilmadi yoki sizga tegishli emas.", reply_markup=start_reply_kb())

@dp.message(Command("edit"))
async def cmd_edit_text(message: Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3 or not parts[1].isdigit():
        await message.answer("Foydalanish: /edit <id> <yangi matn>")
        return
    task_id = int(parts[1])
    new_text = parts[2]
    ok = edit_task(message.from_user.id, task_id, new_text)
    if ok:
        await message.answer("✏️ Vazifa yangilandi.", reply_markup=start_reply_kb())
    else:
        await message.answer("Topilmadi yoki sizga tegishli emas.", reply_markup=start_reply_kb())

@dp.callback_query()
async def cb_handler(query: CallbackQuery):
    data = query.data or ""
    user_id = query.from_user.id

    if ":" not in data:
        await query.answer("Noma'lum tugma.")
        return

    action, sid = data.split(":", 1)
    if not sid.isdigit():
        await query.answer("Noto'g'ri ID.")
        return
    task_id = int(sid)

    if action == "delete":
        ok = delete_task(user_id, task_id)
        if ok:
            try:
                await query.message.edit_text(f"✅ Vazifa (ID: {task_id}) o'chirildi.")
            except Exception:
                pass
            await query.answer("Vazifa o'chirildi.")
        else:
            await query.answer("Topilmadi yoki ruxsat yo'q.", show_alert=True)

    elif action == "edit":
        row = get_task_by_id(user_id, task_id)
        if not row:
            await query.answer("Bunday vazifa topilmadi.", show_alert=True)
            return
        pending_edit[user_id] = task_id
        await query.message.reply("✏️ Iltimos, yangi matnni yuboring (bekor uchun /cancel).", reply_markup=ReplyKeyboardRemove())
        await query.answer()

    else:
        await query.answer("Noma'lum amal.", show_alert=True)

@dp.message()
async def plain_text_handler(message: Message):
    text = (message.text or "").strip()
    if not text:
        return

    user_id = message.from_user.id

    if user_id in pending_edit:
        task_id = pending_edit.pop(user_id)
        ok = edit_task(user_id, task_id, text)
        if ok:
            await message.answer(f"✏️ Vazifa (ID: {task_id}) yangilandi.", reply_markup=start_reply_kb())
        else:
            await message.answer("Xatolik: yangilash muvaffaqiyatsiz yoki ruxsat yo'q.", reply_markup=start_reply_kb())
        return

    if user_id in pending_add:
        pending_add.discard(user_id)
        tid = add_task(user_id, text)
        await message.answer(f"✅ Vazifa qo'shildi (ID: {tid}).", reply_markup=start_reply_kb())
        return

    if text.startswith("/"):
        return

    await message.answer("Agar yangi vazifa qo'shmoqchi bo'lsangiz — 'Vazifa qo\'shish' tugmasini bosing yoki /add komandasi bilan yuboring.", reply_markup=start_reply_kb())

async def send_user_tasks(user_id: int, chat_id: int):
    rows = get_tasks(user_id)
    if not rows:
        await bot.send_message(chat_id, "Sizda vazifa yo‘q.", reply_markup=start_reply_kb())
        return

    for r in rows:
        tid, txt = r
        await bot.send_message(chat_id, f"{tid}. {txt}", reply_markup=task_inline_kb(tid))
    await bot.send_message(chat_id, "Boshqa amalni tanlang:", reply_markup=start_reply_kb())

async def main():
    init_db()
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
