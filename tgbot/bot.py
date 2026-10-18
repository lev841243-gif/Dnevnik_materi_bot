"""Telegram-бот «Дневник Спокойного Материнства» (Webhook + Cloudflare Worker Relay)."""

import asyncio
import logging
import os
import sys

from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

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
    await state.clear()
    storage = state.storage
    if isinstance(storage, MemoryStorage):
        storage.storage.pop(state.key, None)


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


@router.callback_query(F.data == CB_RESOURCE)
async def cb_resource(call: CallbackQuery, state: FSMContext) -> None:
    await wipe(state)
    await call.answer()
    await call.message.answer(texts.RESOURCE, reply_markup=back_kb())


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
    logging.basicConfig(level=logging.INFO)

    token = os.getenv("BOT_TOKEN")
    if not token:
        sys.exit("Не задана переменная окружения BOT_TOKEN")

    # URL, на который BotGate будет присылать вебхуки
    webhook_path = "/"

    # --- НАСТРОЙКА CLOUDFLARE WORKER КАК РЕЛЕЯ ---
    relay_url = "https://tg-relay.lev841243.workers.dev"
    logging.info(f"Используем релей: {relay_url}")
    
    api_server = TelegramAPIServer.from_base(relay_url)
    session = AiohttpSession(api=api_server)
    # ---------------------------------------------

    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=None),
        session=session
    )

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    app = web.Application()

    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path=webhook_path)
    setup_application(app, dp, bot=bot)

    async def health_check(request):
        return web.Response(text="OK")

    app.router.add_get("/", health_check)

    port = int(os.getenv("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logging.info(f"Веб-сервер запущен на порту {port}. Ожидаем вебхуки на {webhook_path}")

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())