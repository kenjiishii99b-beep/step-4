from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MYSQL_TABLE_ARGS, Base, CreatedAtMixin
from app.models.enums import MovementTypeEnum

if TYPE_CHECKING:
    from app.models.product import Sku
    from app.models.staff import Staff
    from app.models.transaction import Transaction


class InventoryHistory(CreatedAtMixin, Base):
    __tablename__ = "inventory_histories"
    __table_args__ = (
        Index("idx_inventory_sku_time", "sku_id", "created_at"),
        Index("idx_inventory_transaction", "transaction_id"),
        MYSQL_TABLE_ARGS,
    )

    inventory_history_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    sku_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("skus.sku_id", name="fk_inv_sku", ondelete="RESTRICT"),
    )
    location: Mapped[str] = mapped_column(String(32))
    quantity_delta: Mapped[int] = mapped_column(Integer)
    movement_type: Mapped[MovementTypeEnum] = mapped_column(Enum(MovementTypeEnum))
    transaction_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("transactions.transaction_id", name="fk_inv_transaction", ondelete="RESTRICT"),
    )
    staff_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("staff.staff_id", name="fk_inv_staff", ondelete="RESTRICT"),
    )

    sku: Mapped["Sku"] = relationship(back_populates="inventory_histories")
    staff: Mapped["Staff"] = relationship(back_populates="inventory_histories")
    transaction: Mapped["Transaction | None"] = relationship(back_populates="inventory_histories")
