"""Telegram-бот «Дневник Спокойного Материнства».

Ничего не пишется на диск: ни ответы, ни Telegram ID. Состояние диалога
живёт только в оперативной памяти и удаляется после сводки или отмены.
"""

import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
# from dotenv import load_dotenv
# load_dotenv()
import texts

MAX_ANSWER_LEN = 500

CB_DIARY = "diary"
CB_RESOURCE = "resource"
CB_MENU = "menu"
CB_CANCEL = "cancel"

router = Router()


class Survey(StatesGroup):
    answering = State()


def _kb(*buttons: tuple[str, str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=cb)] for t, cb in buttons]
    )


def menu_kb() -> InlineKeyboardMarkup:
    return _kb((texts.BTN_DIARY, CB_DIARY), (texts.BTN_RESOURCE, CB_RESOURCE))


def back_kb() -> InlineKeyboardMarkup:
    return _kb((texts.BTN_BACK, CB_MENU))


def cancel_kb() -> InlineKeyboardMarkup:
    return _kb((texts.BTN_CANCEL, CB_CANCEL))


async def wipe(state: FSMContext) -> None:
    """Полностью удалить состояние пользователя из памяти, включая запись с ID."""
    await state.clear()
    storage = state.storage
    if isinstance(storage, MemoryStorage):
        storage.storage.pop(state.key, None)


# ---------- Главное меню ----------

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await wipe(state)
    await message.answer(texts.WELCOME, reply_markup=menu_kb())


@router.callback_query(F.data == CB_MENU)
async def cb_menu(call: CallbackQuery, state: FSMContext) -> None:
    await wipe(state)
    await call.answer()
    await call.message.answer(texts.WELCOME, reply_markup=menu_kb())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await wipe(state)
    await message.answer(texts.CANCELLED, reply_markup=menu_kb())


@router.callback_query(F.data == CB_CANCEL)
async def cb_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await wipe(state)
    await call.answer()
    await call.message.answer(texts.CANCELLED, reply_markup=menu_kb())


# ---------- Ветка 2: «Мой ресурс» ----------

@router.callback_query(F.data == CB_RESOURCE)
async def cb_resource(call: CallbackQuery, state: FSMContext) -> None:
    await wipe(state)
    await call.answer()
    await call.message.answer(texts.RESOURCE, reply_markup=back_kb())


# ---------- Ветка 1: дневник малыша ----------

@router.callback_query(F.data == CB_DIARY)
async def cb_diary(call: CallbackQuery, state: FSMContext) -> None:
    await wipe(state)
    await state.set_state(Survey.answering)
    await state.update_data(answers=[])
    await call.answer()
    await call.message.answer(texts.QUESTIONS[0], reply_markup=cancel_kb())


@router.message(Survey.answering, F.text, ~F.text.startswith("/"))
async def collect_answer(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if len(text) > MAX_ANSWER_LEN:
        await message.answer(texts.ANSWER_TOO_LONG.format(limit=MAX_ANSWER_LEN))
        return

    data = await state.get_data()
    answers = data.get("answers", []) + [text]

    if len(answers) < len(texts.QUESTIONS):
        await state.update_data(answers=answers)
        await message.answer(texts.QUESTIONS[len(answers)], reply_markup=cancel_kb())
        return

    lines = [texts.SUMMARY_TITLE]
    for label, answer in zip(texts.SUMMARY_LABELS, answers):
        lines.append(f"• {label}: {answer}")
    lines.append("")
    lines.append(texts.SUMMARY_FOOTER)

    await wipe(state)
    await message.answer("\n".join(lines), reply_markup=back_kb())


@router.message(Survey.answering, ~F.text)
async def answer_not_text(message: Message) -> None:
    await message.answer(texts.ONLY_TEXT)


@router.message()
async def fallback(message: Message) -> None:
    await message.answer(texts.UNKNOWN, reply_markup=menu_kb())


async def main() -> None:
    # WARNING: в логи не попадают ни тексты, ни ID пользователей
    logging.basicConfig(level=logging.WARNING)

    token = os.getenv("BOT_TOKEN")
    if not token:
        sys.exit("Не задана переменная окружения BOT_TOKEN")

    if len(texts.QUESTIONS) != 6 or len(texts.SUMMARY_LABELS) != 6:
        sys.exit("В texts.py должно быть ровно 6 вопросов и 6 подписей")

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=None))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
