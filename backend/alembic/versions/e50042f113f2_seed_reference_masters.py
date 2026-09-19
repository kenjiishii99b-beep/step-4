"""seed reference masters

Revision ID: e50042f113f2
Revises: 936f0e6b6f53
Create Date: 2026-09-11 21:42:28.299962

サイズ・カラー分類システムと税率マスターは、設計仕様書のAPIエンドポイント表に
管理用エンドポイントが存在しない（システム設定として運用担当が直接投入する
想定の）参照データであるため、Alembicのデータマイグレーションで初期投入する。
これにより、商品登録APIがSKU作成時に参照するsize_masters/color_masters、
および会計処理が参照するtax_ratesが、新規環境でも即座に利用可能になる。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e50042f113f2"
down_revision: Union[str, None] = "936f0e6b6f53"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SIZE_SYSTEM_ID = "STANDARD"
COLOR_SYSTEM_ID = "BASIC"
TAX_RATE_ID = "DEFAULT"

size_masters = sa.table(
    "size_masters",
    sa.column("size_system_id", sa.String),
    sa.column("size_code", sa.String),
    sa.column("size_name", sa.String),
    sa.column("display_order", sa.Integer),
)

color_masters = sa.table(
    "color_masters",
    sa.column("color_system_id", sa.String),
    sa.column("color_code", sa.String),
    sa.column("color_name", sa.String),
    sa.column("display_order", sa.Integer),
)

tax_rates = sa.table(
    "tax_rates",
    sa.column("tax_rate_id", sa.String),
    sa.column("tax_rate", sa.Numeric),
    sa.column("valid_from", sa.DateTime),
    sa.column("valid_to", sa.DateTime),
)


def upgrade() -> None:
    op.bulk_insert(
        size_masters,
        [
            {
                "size_system_id": SIZE_SYSTEM_ID,
                "size_code": code,
                "size_name": code,
                "display_order": order,
            }
            for order, code in enumerate(["S", "M", "L", "XL"])
        ],
    )
    op.bulk_insert(
        color_masters,
        [
            {
                "color_system_id": COLOR_SYSTEM_ID,
                "color_code": code,
                "color_name": name,
                "display_order": order,
            }
            for order, (code, name) in enumerate(
                [
                    ("BLK", "Black"),
                    ("WHT", "White"),
                    ("GRY", "Gray"),
                    ("NVY", "Navy"),
                    ("RED", "Red"),
                ]
            )
        ],
    )
    op.bulk_insert(
        tax_rates,
        [
            {
                "tax_rate_id": TAX_RATE_ID,
                "tax_rate": 10.00,
                "valid_from": "1970-01-01 00:00:00",
                "valid_to": None,
            }
        ],
    )


def downgrade() -> None:
    op.execute(sa.delete(tax_rates).where(tax_rates.c.tax_rate_id == TAX_RATE_ID))
    op.execute(sa.delete(color_masters).where(color_masters.c.color_system_id == COLOR_SYSTEM_ID))
    op.execute(sa.delete(size_masters).where(size_masters.c.size_system_id == SIZE_SYSTEM_ID))
