from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str] = mapped_column(String(128), default="")
    stars_balance: Mapped[float] = mapped_column(Float, default=0.0)
    referrals_count: Mapped[int] = mapped_column(Integer, default=0)
    referrer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=True)
    last_bonus_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    referral_reward_pending: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BotSettings(Base):
    __tablename__ = "bot_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    reward: Mapped[float] = mapped_column(Float, default=0.0)
    is_random: Mapped[bool] = mapped_column(Boolean, default=False)
    reward_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    reward_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    usage_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PromoUse(Base):
    __tablename__ = "promo_uses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    promo_id: Mapped[int] = mapped_column(Integer, ForeignKey("promo_codes.id"))


class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    channel_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payments_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    reward: Mapped[float] = mapped_column(Float)
    channel_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    target_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # User-created task fields
    creator_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    creator_reward_rate: Mapped[float] = mapped_column(Float, default=0.0)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=True)
    max_completions: Mapped[int] = mapped_column(Integer, default=0)  # 0 = unlimited


class TaskCompletion(Base):
    __tablename__ = "task_completions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id"))
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)



class GameSession(Base):
    __tablename__ = "game_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    game_type: Mapped[str] = mapped_column(String(32))
    bet: Mapped[float] = mapped_column(Float)
    result: Mapped[str] = mapped_column(String(8))
    payout: Mapped[float] = mapped_column(Float, default=0.0)
    played_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ButtonContent(Base):
    __tablename__ = "button_contents"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    photo_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)


class Duel(Base):
    __tablename__ = "duels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    creator_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    joiner_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=True)
    amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default="waiting")
    creator_roll: Mapped[int | None] = mapped_column(Integer, nullable=True)
    joiner_roll: Mapped[int | None] = mapped_column(Integer, nullable=True)
    winner_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class Transfer(Base):
    __tablename__ = "transfers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    to_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    amount: Mapped[float] = mapped_column(Float)
    commission: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Lottery(Base):
    __tablename__ = "lotteries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active, finished
    tickets_sold: Mapped[int] = mapped_column(Integer, default=0)
    total_collected: Mapped[float] = mapped_column(Float, default=0.0)
    prize_pool: Mapped[float] = mapped_column(Float, default=0.0)
    winner_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    drawn_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Configurable per-lottery settings
    end_type: Mapped[str] = mapped_column(String(16), default="tickets")  # tickets | time | commission
    end_value: Mapped[float] = mapped_column(Float, default=10.0)  # ticket count / unix ts / stars amount
    ticket_price: Mapped[float] = mapped_column(Float, default=5.0)
    ticket_limit: Mapped[int] = mapped_column(Integer, default=0)  # 0 = unlimited
    channel_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ref_required: Mapped[int] = mapped_column(Integer, default=0)


class LotteryTicket(Base):
    __tablename__ = "lottery_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lottery_id: Mapped[int] = mapped_column(Integer, ForeignKey("lotteries.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


