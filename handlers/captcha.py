import logging
from datetime import datetime, timedelta

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
BLOCK_MINUTES = 10


class CaptchaStates(StatesGroup):
    waiting = State()


async def show_captcha(
    target: Message | CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    from services.captcha_gen import generate_code, generate_image

    code = generate_code()
    await state.set_state(CaptchaStates.waiting)
    await state.update_data(code=code, attempts=0)

    img = BufferedInputFile(generate_image(code), filename="captcha.png")
    text = (
        "🔐 <b>Введите код с картинки</b>\n\n"
        "Это разовая проверка — просто введите символы из изображения."
    )

    if isinstance(target, CallbackQuery):
        await target.message.answer_photo(img, caption=text, parse_mode="HTML")
    else:
        await target.answer_photo(img, caption=text, parse_mode="HTML")

    logger.info("Captcha shown to user %s", target.from_user.id)


router = Router()


@router.message(StateFilter(CaptchaStates.waiting))
async def captcha_input(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    code: str = data.get("code", "")
    attempts: int = data.get("attempts", 0) + 1
    user_input = (message.text or "").strip().upper()

    if user_input == code.upper():
        db_user = await session.get(User, message.from_user.id)
        if db_user:
            db_user.captcha_passed = True
            await session.commit()
        await state.clear()

        from handlers.button_helper import send_with_content
        from keyboards.main import main_menu_kb
        from utils.emoji import pe

        await send_with_content(
            message,
            session,
            "menu:main",
            pe("👋 <b>Добро пожаловать!</b>\n\nВыбери раздел 👇"),
            main_menu_kb(),
        )
        logger.info("Captcha passed by user %s", message.from_user.id)

    elif attempts >= MAX_ATTEMPTS:
        db_user = await session.get(User, message.from_user.id)
        if db_user:
            db_user.captcha_blocked_until = datetime.utcnow() + timedelta(minutes=BLOCK_MINUTES)
            await session.commit()
        await state.clear()
        await message.answer(
            f"❌ <b>Слишком много неверных попыток.</b>\n"
            f"Попробуй снова через <b>{BLOCK_MINUTES} минут</b>.",
            parse_mode="HTML",
        )
        logger.info("Captcha blocked user %s after %d wrong attempts", message.from_user.id, attempts)

    else:
        await state.update_data(attempts=attempts)
        remaining = MAX_ATTEMPTS - attempts
        await message.answer(
            f"❌ Неверный код. Осталось попыток: <b>{remaining}</b>",
            parse_mode="HTML",
        )


@router.callback_query(StateFilter(CaptchaStates.waiting))
async def captcha_callback_block(callback: CallbackQuery) -> None:
    await callback.answer("🔐 Сначала введите код с картинки!", show_alert=True)
