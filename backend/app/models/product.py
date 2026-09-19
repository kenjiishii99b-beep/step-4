from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MYSQL_TABLE_ARGS, Base, CreatedAtMixin, TimestampMixin
from app.models.enums import DiscountTargetTypeEnum, DiscountTypeEnum

if TYPE_CHECKING:
    from app.models.inventory import InventoryHistory
    from app.models.master import ColorMaster, SizeMaster
    from app.models.transaction import SalesItem


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = MYSQL_TABLE_ARGS

    product_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    product_name: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(64))
    default_price: Mapped[int] = mapped_column(Integer)
    image_url: Mapped[str | None] = mapped_column(String(512))
    size_system_id: Mapped[str | None] = mapped_column(String(32))
    color_system_id: Mapped[str | None] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("1"))

    skus: Mapped[list["Sku"]] = relationship(back_populates="product")
    price_histories: Mapped[list["PriceHistory"]] = relationship(back_populates="product")
    discounts: Mapped[list["DiscountMaster"]] = relationship(back_populates="product")
    sales_items: Mapped[list["SalesItem"]] = relationship(back_populates="product")


class Sku(CreatedAtMixin, Base):
    __tablename__ = "skus"
    __table_args__ = (
        ForeignKeyConstraint(
            ["size_system_id", "size_code"],
            ["size_masters.size_system_id", "size_masters.size_code"],
            name="fk_sku_size",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["color_system_id", "color_code"],
            ["color_masters.color_system_id", "color_masters.color_code"],
            name="fk_sku_color",
            ondelete="RESTRICT",
        ),
        CheckConstraint("store_stock >= 0", name="chk_stock"),
        Index("idx_product", "product_id"),
        MYSQL_TABLE_ARGS,
    )

    sku_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("products.product_id", name="fk_sku_product", ondelete="RESTRICT"),
    )
    barcode_ean13: Mapped[str] = mapped_column(String(13), unique=True)
    size_system_id: Mapped[str] = mapped_column(String(32))
    size_code: Mapped[str] = mapped_column(String(16))
    color_system_id: Mapped[str] = mapped_column(String(32))
    color_code: Mapped[str] = mapped_column(String(16))
    store_stock: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    warehouse_stock: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    location: Mapped[str | None] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("1"))

    product: Mapped["Product"] = relationship(back_populates="skus")
    size_master: Mapped["SizeMaster"] = relationship(back_populates="skus")
    color_master: Mapped["ColorMaster"] = relationship(back_populates="skus")
    price_histories: Mapped[list["PriceHistory"]] = relationship(back_populates="sku")
    discounts: Mapped[list["DiscountMaster"]] = relationship(back_populates="sku")
    sales_items: Mapped[list["SalesItem"]] = relationship(back_populates="sku")
    inventory_histories: Mapped[list["InventoryHistory"]] = relationship(back_populates="sku")


class PriceHistory(Base):
    __tablename__ = "price_histories"
    __table_args__ = (
        Index("idx_price_target", "product_id", "sku_id", "valid_from", "valid_to"),
        MYSQL_TABLE_ARGS,
    )

    price_history_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("products.product_id", name="fk_price_prod", ondelete="RESTRICT"),
    )
    sku_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("skus.sku_id", name="fk_price_sku", ondelete="RESTRICT"),
    )
    price: Mapped[int] = mapped_column(Integer)
    valid_from: Mapped[datetime] = mapped_column(DateTime)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("1"))

    product: Mapped["Product"] = relationship(back_populates="price_histories")
    sku: Mapped["Sku | None"] = relationship(back_populates="price_histories")


class DiscountMaster(Base):
    __tablename__ = "discount_masters"
    __table_args__ = (
        Index(
            "idx_discount_target", "target_type", "product_id", "sku_id", "valid_from", "valid_to"
        ),
        MYSQL_TABLE_ARGS,
    )

    discount_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    target_type: Mapped[DiscountTargetTypeEnum] = mapped_column(Enum(DiscountTargetTypeEnum))
    product_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("products.product_id", name="fk_discount_product", ondelete="RESTRICT"),
    )
    sku_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("skus.sku_id", name="fk_discount_sku", ondelete="RESTRICT"),
    )
    discount_type: Mapped[DiscountTypeEnum] = mapped_column(Enum(DiscountTypeEnum))
    discount_value: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    valid_from: Mapped[datetime] = mapped_column(DateTime)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime)
    priority: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("1"))

    product: Mapped["Product | None"] = relationship(back_populates="discounts")
    sku: Mapped["Sku | None"] = relationship(back_populates="discounts")
