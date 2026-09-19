from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MYSQL_TABLE_ARGS, Base, TimestampMixin
from app.models.enums import RoleEnum

if TYPE_CHECKING:
    from app.models.inventory import InventoryHistory
    from app.models.transaction import Transaction


class Staff(TimestampMixin, Base):
    __tablename__ = "staff"
    __table_args__ = MYSQL_TABLE_ARGS

    staff_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    staff_name: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[RoleEnum] = mapped_column(
        Enum(RoleEnum), server_default=text(f"'{RoleEnum.STAFF.value}'")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("1"))

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="staff")
    inventory_histories: Mapped[list["InventoryHistory"]] = relationship(back_populates="staff")
