from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MYSQL_TABLE_ARGS, Base

if TYPE_CHECKING:
    from app.models.product import Sku


class SizeMaster(Base):
    __tablename__ = "size_masters"
    __table_args__ = MYSQL_TABLE_ARGS

    size_system_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    size_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    size_name: Mapped[str] = mapped_column(String(32))
    display_order: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("1"))

    skus: Mapped[list["Sku"]] = relationship(back_populates="size_master")


class ColorMaster(Base):
    __tablename__ = "color_masters"
    __table_args__ = MYSQL_TABLE_ARGS

    color_system_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    color_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    color_name: Mapped[str] = mapped_column(String(64))
    display_order: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("1"))

    skus: Mapped[list["Sku"]] = relationship(back_populates="color_master")


class TaxRate(Base):
    __tablename__ = "tax_rates"
    __table_args__ = (
        Index("idx_tax_validity", "valid_from", "valid_to"),
        MYSQL_TABLE_ARGS,
    )

    tax_rate_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    valid_from: Mapped[datetime] = mapped_column(DateTime)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("1"))
