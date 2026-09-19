import asyncio
import sys

from app.core.database import AsyncSessionLocal
from app.models import Product, Sku

SIZE_SYSTEM = "STANDARD"
COLOR_SYSTEM = "BASIC"
SIZES = ["S", "M", "L", "XL"]
COLORS = ["BLK", "WHT", "GRY", "NVY", "RED"]

# GS1の「restricted circulation number」用プレフィックス(20-29)を使用。
# 実在の商品バーコードと衝突しない、社内・デモ専用の採番範囲。
BARCODE_PREFIX = "20"


def ean13_check_digit(digits12: str) -> str:
    total = 0
    for i, d in enumerate(digits12):
        n = int(d)
        total += n * (3 if i % 2 == 1 else 1)
    return str((10 - total % 10) % 10)


def make_ean13(sequence: int) -> str:
    body = f"{BARCODE_PREFIX}{sequence:010d}"
    assert len(body) == 12, body
    return body + ean13_check_digit(body)


PRODUCTS = [
    ("トップス", "ベーシッククルーネックTシャツ ロング丈", 2800),
    ("トップス", "オーバーサイズロンT", 3200),
    ("トップス", "リネンブレンドシャツ", 5800),
    ("トップス", "シルクブラウス", 8900),
    ("トップス", "ローゲージニットプルオーバー", 6500),
    ("トップス", "カシミヤブレンドカーディガン", 9800),
    ("トップス", "裏起毛スウェットパーカー", 5200),
    ("トップス", "無地スウェットクルー", 4200),
    ("トップス", "リブタンクトップ", 1800),
    ("トップス", "鹿の子ポロシャツ", 4500),
    ("トップス", "オックスフォードボタンダウンシャツ", 6200),
    ("トップス", "ボーダーカットソー", 3400),
    ("ボトムス", "スリムストレートデニムパンツ", 7800),
    ("ボトムス", "テーパードチノパンツ", 6800),
    ("ボトムス", "ウールブレンドスラックス", 9200),
    ("ボトムス", "プリーツロングスカート", 6900),
    ("ボトムス", "デニムショートパンツ", 4800),
    ("ボトムス", "ワイドイージーパンツ", 7200),
    ("ボトムス", "リブレギンスパンツ", 3600),
    ("ボトムス", "コーデュロイパンツ", 6400),
    ("アウター", "ステンカラーコート", 15800),
    ("アウター", "ダウンジャケット", 18900),
    ("アウター", "マウンテンパーカー", 12800),
    ("アウター", "ライダースジャケット", 16500),
    ("アウター", "トレンチコート", 14200),
    ("アウター", "キルティングブルゾン", 11800),
    ("ワンピース", "シャツワンピース", 8400),
    ("ワンピース", "ニットワンピース", 7600),
    ("ワンピース", "サロペット・オールインワン", 8900),
    ("トップス", "フーデッドジップアップパーカー", 5600),
    ("トップス", "ヘンリーネックカットソー", 3100),
    ("トップス", "ワッフルロングスリーブT", 3800),
    ("トップス", "ドライメッシュTシャツ", 2600),
    ("トップス", "モックネックニット", 5900),
    ("ボトムス", "センタープレステーパードパンツ", 7400),
    ("ボトムス", "フレアデニムパンツ", 8200),
    ("ボトムス", "ミニプリーツスカート", 5800),
    ("ボトムス", "カーゴパンツ", 7900),
    ("アウター", "ノーカラーツイードジャケット", 13400),
    ("アウター", "フリースジャケット", 6800),
    ("トップス", "半袖ポロシャツ ドライ素材", 4100),
    ("トップス", "ボアフリースプルオーバー", 6200),
    ("ボトムス", "アンクル丈テーパードデニム", 8600),
    ("ボトムス", "サルエルパンツ", 6900),
    ("アウター", "ノーカラーコート", 15200),
    ("アウター", "デニムジャケット", 9800),
    ("ワンピース", "キャミワンピース", 6800),
    ("トップス", "コットンニットベスト", 4600),
    ("トップス", "オーバーシャツジャケット", 7200),
    ("ボトムス", "スウェットジョガーパンツ", 5400),
]

assert len(PRODUCTS) == 50, len(PRODUCTS)


async def ensure_product(db, product_id, name, category, price):
    if await db.get(Product, product_id) is None:
        db.add(Product(product_id=product_id, product_name=name, category=category, default_price=price))
        await db.flush()


async def ensure_sku(db, sku_id, product_id, barcode, size_code, color_code, store_stock):
    if await db.get(Sku, sku_id) is None:
        db.add(Sku(
            sku_id=sku_id, product_id=product_id, barcode_ean13=barcode,
            size_system_id=SIZE_SYSTEM, size_code=size_code,
            color_system_id=COLOR_SYSTEM, color_code=color_code,
            store_stock=store_stock,
        ))


async def main():
    seq = 1
    created_products = []
    async with AsyncSessionLocal() as db:
        for i, (category, name, price) in enumerate(PRODUCTS, start=1):
            product_id = f"DEMO-{i:03d}"
            await ensure_product(db, product_id, name, category, price)

            size_a = SIZES[i % len(SIZES)]
            color_a = COLORS[i % len(COLORS)]
            size_b = SIZES[(i + 1) % len(SIZES)]
            color_b = COLORS[(i + 2) % len(COLORS)]

            barcode_a = make_ean13(seq); seq += 1
            barcode_b = make_ean13(seq); seq += 1

            sku_a_id = f"{product_id}-{size_a}-{color_a}"
            sku_b_id = f"{product_id}-{size_b}-{color_b}"

            await ensure_sku(db, sku_a_id, product_id, barcode_a, size_a, color_a, store_stock=10 + i)
            await ensure_sku(db, sku_b_id, product_id, barcode_b, size_b, color_b, store_stock=8 + i)

            created_products.append((product_id, name, sku_a_id, barcode_a, sku_b_id, barcode_b))

        await db.commit()

    for row in created_products:
        print("\t".join(str(x) for x in row))
    print(f"TOTAL_PRODUCTS={len(created_products)} TOTAL_SKUS={len(created_products) * 2}", file=sys.stderr)


asyncio.run(main())
