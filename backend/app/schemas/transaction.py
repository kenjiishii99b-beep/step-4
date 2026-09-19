from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import PaymentMethodEnum, TransactionTypeEnum


class SalesItemResponse(BaseModel):
    sku_id: str
    product_id: str
    quantity: int
    unit_price_snapshot: int
    discount_amount_snapshot: int
    tax_rate_snapshot: Decimal
    tax_amount_snapshot: int
    line_total_ex_tax: int
    line_total_inc_tax: int


class TransactionResponse(BaseModel):
    transaction_id: str
    member_id: str | None
    staff_id: str
    payment_method: PaymentMethodEnum
    subtotal_ex_tax: int
    discount_total: int
    tax_amount: int
    total_inc_tax: int
    tx_type: TransactionTypeEnum
    parent_transaction_id: str | None
    created_at: datetime
    items: list[SalesItemResponse]
