from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, model_validator


class StockLocation(StrEnum):
    STORE = "STORE"
    WAREHOUSE = "WAREHOUSE"


class InventoryStatusResponse(BaseModel):
    sku_id: str
    store_stock: int
    warehouse_stock: int


class InventoryReceiptRequest(BaseModel):
    sku_id: str = Field(min_length=1, max_length=64)
    location: StockLocation = StockLocation.STORE
    quantity: int = Field(ge=1)


class InventoryTransferRequest(BaseModel):
    sku_id: str = Field(min_length=1, max_length=64)
    from_location: StockLocation
    to_location: StockLocation
    quantity: int = Field(ge=1)

    @model_validator(mode="after")
    def _validate_different_locations(self) -> Self:
        if self.from_location == self.to_location:
            raise ValueError("from_location と to_location には異なる場所を指定してください。")
        return self
