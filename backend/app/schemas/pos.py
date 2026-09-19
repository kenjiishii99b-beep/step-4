from pydantic import BaseModel, Field, model_validator

from app.models.enums import PaymentMethodEnum, TransactionTypeEnum


class CheckoutItemRequest(BaseModel):
    sku_id: str = Field(min_length=1, max_length=64)
    quantity: int = Field(ge=1, le=99)


class CheckoutRequest(BaseModel):
    items: list[CheckoutItemRequest] = Field(min_length=1, max_length=100)
    client_total: int = Field(ge=0)
    payment_method: PaymentMethodEnum
    member_id: str | None = Field(default=None, max_length=32)
    amount_tendered: int | None = Field(default=None, ge=0)


class CheckoutResponse(BaseModel):
    transaction_id: str
    subtotal_ex_tax: int
    discount_total: int
    tax_amount: int
    total_inc_tax: int
    change: int


class RefundExchangeItemRequest(BaseModel):
    sku_id: str = Field(min_length=1, max_length=64)
    quantity: int = Field(ge=1, le=99)


class RefundExchangeRequest(BaseModel):
    parent_transaction_id: str = Field(min_length=1, max_length=64)
    tx_type: TransactionTypeEnum
    return_items: list[RefundExchangeItemRequest] = Field(min_length=1, max_length=100)
    # EXCHANGE の場合のみ指定する、顧客へ新たに渡す商品（現在の単価・値引き・
    # 税率で再計算する。RETURN の場合は空でなければならない）。
    exchange_items: list[RefundExchangeItemRequest] = Field(default_factory=list, max_length=100)
    # 差額の符号付き合計。マイナス＝店舗が顧客へ返金、プラス＝顧客が追加支払い、
    # ゼロ＝等価交換。バックエンド再計算額と不一致なら 422 で中断する。
    client_total: int
    payment_method: PaymentMethodEnum
    amount_tendered: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _validate_tx_type_consistency(self) -> "RefundExchangeRequest":
        if self.tx_type == TransactionTypeEnum.SALE:
            raise ValueError("tx_type には RETURN または EXCHANGE のみ指定できます。")
        if self.tx_type == TransactionTypeEnum.RETURN and self.exchange_items:
            raise ValueError("RETURN では exchange_items を指定できません。")
        if self.tx_type == TransactionTypeEnum.EXCHANGE and not self.exchange_items:
            raise ValueError("EXCHANGE では exchange_items が必須です。")
        return self


class RefundExchangeResponse(BaseModel):
    transaction_id: str
    parent_transaction_id: str
    tx_type: TransactionTypeEnum
    subtotal_ex_tax: int
    discount_total: int
    tax_amount: int
    total_inc_tax: int
    change: int
