from pydantic import BaseModel, Field


class SkuInput(BaseModel):
    sku_id: str = Field(min_length=1, max_length=64)
    barcode_ean13: str = Field(min_length=13, max_length=13)
    size_system_id: str = Field(min_length=1, max_length=32)
    size_code: str = Field(min_length=1, max_length=16)
    color_system_id: str = Field(min_length=1, max_length=32)
    color_code: str = Field(min_length=1, max_length=16)
    store_stock: int = Field(default=0, ge=0)
    warehouse_stock: int = Field(default=0, ge=0)
    location: str | None = Field(default=None, max_length=32)


class SkuResponse(BaseModel):
    sku_id: str
    barcode_ean13: str
    size_system_id: str
    size_code: str
    color_system_id: str
    color_code: str
    store_stock: int
    warehouse_stock: int
    location: str | None
    is_active: bool


class ProductCreateRequest(BaseModel):
    product_id: str = Field(min_length=1, max_length=32)
    product_name: str = Field(min_length=1, max_length=128)
    category: str = Field(min_length=1, max_length=64)
    default_price: int = Field(ge=0)
    image_url: str | None = Field(default=None, max_length=512)
    size_system_id: str | None = Field(default=None, max_length=32)
    color_system_id: str | None = Field(default=None, max_length=32)
    # 登録と同時に販売可能な SKU（サイズ・カラー展開）を作成する。
    # 仕様書のエンドポイント表に個別の SKU 作成 API がないため、商品登録に
    # 内包する形とした。
    skus: list[SkuInput] = Field(default_factory=list, max_length=100)


class ProductUpdateRequest(BaseModel):
    product_name: str = Field(min_length=1, max_length=128)
    category: str = Field(min_length=1, max_length=64)
    default_price: int = Field(ge=0)
    image_url: str | None = Field(default=None, max_length=512)
    size_system_id: str | None = Field(default=None, max_length=32)
    color_system_id: str | None = Field(default=None, max_length=32)
    is_active: bool = True
    # 新規 sku_id のみ追加登録される（バリエーション拡張用）。既存SKUの在庫数・
    # バーコード等は在庫API（/inventory/receipt, /inventory/transfer）で
    # 履歴を残しながら変更する運用とし、ここでは上書きしない。
    skus: list[SkuInput] = Field(default_factory=list, max_length=100)


class ProductResponse(BaseModel):
    product_id: str
    product_name: str
    category: str
    default_price: int
    image_url: str | None
    size_system_id: str | None
    color_system_id: str | None
    is_active: bool
    skus: list[SkuResponse]


class SkuLookupResponse(BaseModel):
    sku_id: str
    barcode_ean13: str
    product_id: str
    product_name: str
    # 参考表示用の現在価格（商品の定価）。値引き・期間限定価格・税込み額は
    # 含まない概算であり、確定額は会計時にサーバー側で再計算される
    # （設計仕様書 3.4節：金額改ざん防止）。
    reference_price: int
    size_code: str
    color_code: str
    store_stock: int
    is_active: bool
