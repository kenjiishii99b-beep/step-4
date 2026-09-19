from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MYSQL_TABLE_ARGS, Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.transaction import Transaction


class Member(TimestampMixin, Base):
    __tablename__ = "members"
    __table_args__ = MYSQL_TABLE_ARGS

    member_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    member_name: Mapped[str] = mapped_column(String(128))
    phone_number: Mapped[str | None] = mapped_column(String(32))
    address: Mapped[str | None] = mapped_column(String(255))
    gender: Mapped[str | None] = mapped_column(String(16))
    age: Mapped[int | None] = mapped_column(Integer)
    point_balance: Mapped[int] = mapped_column(Integer, server_default=text("0"))

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="member")
