from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.models.enums import DiscountTargetTypeEnum, DiscountTypeEnum


class DiscountUpsertRequest(BaseModel):
    discount_id: str = Field(min_length=1, max_length=64)
    target_type: DiscountTargetTypeEnum
    product_id: str | None = Field(default=None, max_length=32)
    sku_id: str | None = Field(default=None, max_length=64)
    discount_type: DiscountTypeEnum
    discount_value: Decimal = Field(ge=0)
    valid_from: datetime
    valid_to: datetime | None = None
    priority: int
    is_active: bool = True

    @model_validator(mode="after")
    def _validate_target(self) -> Self:
        if self.target_type == DiscountTargetTypeEnum.SKU:
            if not self.sku_id or self.product_id:
                raise ValueError("target_type=SKU では sku_id のみを指定してください。")
        elif self.target_type == DiscountTargetTypeEnum.PRODUCT:
            if not self.product_id or self.sku_id:
                raise ValueError("target_type=PRODUCT では product_id のみを指定してください。")
        else:  # MEMBER
            if self.product_id or self.sku_id:
                raise ValueError("target_type=MEMBER では product_id・sku_id を指定できません。")

        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to は valid_from より後の日時にしてください。")

        if self.discount_type == DiscountTypeEnum.RATE and self.discount_value > 100:
            raise ValueError("discount_type=RATE の場合、discount_value は100以下にしてください。")

        return self


class DiscountResponse(BaseModel):
    discount_id: str
    target_type: DiscountTargetTypeEnum
    product_id: str | None
    sku_id: str | None
    discount_type: DiscountTypeEnum
    discount_value: Decimal
    valid_from: datetime
    valid_to: datetime | None
    priority: int
    is_active: bool


class TaxRateUpsertRequest(BaseModel):
    tax_rate_id: str = Field(min_length=1, max_length=32)
    tax_rate: Decimal = Field(ge=0, le=100)
    valid_from: datetime
    valid_to: datetime | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def _validate_window(self) -> Self:
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to は valid_from より後の日時にしてください。")
        return self


class TaxRateResponse(BaseModel):
    tax_rate_id: str
    tax_rate: Decimal
    valid_from: datetime
    valid_to: datetime | None
    is_active: bool
