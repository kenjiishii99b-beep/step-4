from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.product import Product


async def get_products_by_ids(db: AsyncSession, product_ids: set[str]) -> dict[str, Product]:
    result = await db.execute(select(Product).where(Product.product_id.in_(product_ids)))
    return {product.product_id: product for product in result.scalars()}


async def get_product_by_id(db: AsyncSession, product_id: str) -> Product | None:
    result = await db.execute(
        select(Product).options(selectinload(Product.skus)).where(Product.product_id == product_id)
    )
    return result.scalar_one_or_none()


async def create_product(db: AsyncSession, product: Product) -> None:
    db.add(product)
    await db.flush()
