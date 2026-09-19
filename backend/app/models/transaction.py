from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum, ForeignKey, Index, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MYSQL_TABLE_ARGS, Base, CreatedAtMixin
from app.models.enums import PaymentMethodEnum, TransactionTypeEnum

if TYPE_CHECKING:
    from app.models.inventory import InventoryHistory
    from app.models.member import Member
    from app.models.product import Product, Sku
    from app.models.staff import Staff


class Transaction(CreatedAtMixin, Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("idx_created", "created_at"),
        Index("idx_member", "member_id"),
        MYSQL_TABLE_ARGS,
    )

    transaction_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    member_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("members.member_id", name="fk_tx_member", ondelete="RESTRICT"),
    )
    staff_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("staff.staff_id", name="fk_tx_staff", ondelete="RESTRICT"),
    )
    payment_method: Mapped[PaymentMethodEnum] = mapped_column(Enum(PaymentMethodEnum))
    subtotal_ex_tax: Mapped[int] = mapped_column(Integer)
    discount_total: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    tax_amount: Mapped[int] = mapped_column(Integer)
    total_inc_tax: Mapped[int] = mapped_column(Integer)
    tx_type: Mapped[TransactionTypeEnum] = mapped_column(
        Enum(TransactionTypeEnum),
        server_default=text(f"'{TransactionTypeEnum.SALE.value}'"),
    )
    parent_transaction_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("transactions.transaction_id", name="fk_tx_parent", ondelete="RESTRICT"),
    )

    staff: Mapped["Staff"] = relationship(back_populates="transactions")
    member: Mapped["Member | None"] = relationship(back_populates="transactions")
    items: Mapped[list["SalesItem"]] = relationship(back_populates="transaction")
    parent_transaction: Mapped["Transaction | None"] = relationship(
        remote_side=[transaction_id], back_populates="child_transactions"
    )
    child_transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="parent_transaction"
    )
    inventory_histories: Mapped[list["InventoryHistory"]] = relationship(
        back_populates="transaction"
    )


class SalesItem(Base):
    __tablename__ = "sales_items"
    __table_args__ = MYSQL_TABLE_ARGS

    item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("transactions.transaction_id", name="fk_item_tx", ondelete="RESTRICT"),
    )
    sku_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("skus.sku_id", name="fk_item_sku", ondelete="RESTRICT"),
    )
    product_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("products.product_id", name="fk_item_prod", ondelete="RESTRICT"),
    )
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price_snapshot: Mapped[int] = mapped_column(Integer)
    discount_amount_snapshot: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    tax_rate_snapshot: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    tax_amount_snapshot: Mapped[int] = mapped_column(Integer)
    line_total_ex_tax: Mapped[int] = mapped_column(Integer)
    line_total_inc_tax: Mapped[int] = mapped_column(Integer)

    transaction: Mapped["Transaction"] = relationship(back_populates="items")
    sku: Mapped["Sku"] = relationship(back_populates="sales_items")
    product: Mapped["Product"] = relationship(back_populates="sales_items")
