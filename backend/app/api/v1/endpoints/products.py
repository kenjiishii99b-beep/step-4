from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentStaff, DbSession, require_roles
from app.models.enums import RoleEnum
from app.models.product import Product
from app.models.staff import Staff
from app.schemas.product import (
    ProductCreateRequest,
    ProductResponse,
    ProductUpdateRequest,
    SkuResponse,
)
from app.services import product_service

router = APIRouter()

_require_manager_or_admin = require_roles([RoleEnum.MANAGER, RoleEnum.ADMIN])


def _to_response(product: Product) -> ProductResponse:
    return ProductResponse(
        product_id=product.product_id,
        product_name=product.product_name,
        category=product.category,
        default_price=product.default_price,
        image_url=product.image_url,
        size_system_id=product.size_system_id,
        color_system_id=product.color_system_id,
        is_active=product.is_active,
        skus=[
            SkuResponse(
                sku_id=sku.sku_id,
                barcode_ean13=sku.barcode_ean13,
                size_system_id=sku.size_system_id,
                size_code=sku.size_code,
                color_system_id=sku.color_system_id,
                color_code=sku.color_code,
                store_stock=sku.store_stock,
                warehouse_stock=sku.warehouse_stock,
                location=sku.location,
                is_active=sku.is_active,
            )
            for sku in product.skus
        ],
    )


def _handle_sku_validation_errors(exc: Exception) -> None:
    if isinstance(exc, product_service.SkuAlreadyExistsError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "SKU_ALREADY_EXISTS", "sku_id": exc.sku_id},
        ) from exc
    if isinstance(exc, product_service.DuplicateBarcodeError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "BARCODE_ALREADY_EXISTS", "barcode_ean13": exc.barcode_ean13},
        ) from exc
    if isinstance(exc, product_service.SizeMasterNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "SIZE_MASTER_NOT_FOUND",
                "size_system_id": exc.size_system_id,
                "size_code": exc.size_code,
            },
        ) from exc
    if isinstance(exc, product_service.ColorMasterNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "COLOR_MASTER_NOT_FOUND",
                "color_system_id": exc.color_system_id,
                "color_code": exc.color_code,
            },
        ) from exc


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str, db: DbSession, _current_staff: CurrentStaff
) -> ProductResponse:
    try:
        product = await product_service.get_product(db, product_id)
    except product_service.ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "PRODUCT_NOT_FOUND", "product_id": exc.product_id},
        ) from exc
    return _to_response(product)


@router.post("/admin/products", response_model=ProductResponse)
async def create_product(
    payload: ProductCreateRequest,
    db: DbSession,
    _current_staff: Annotated[Staff, Depends(_require_manager_or_admin)],
) -> ProductResponse:
    try:
        product = await product_service.create_product_with_skus(db, payload)
    except product_service.ProductAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "PRODUCT_ALREADY_EXISTS", "product_id": exc.product_id},
        ) from exc
    except (
        product_service.SkuAlreadyExistsError,
        product_service.DuplicateBarcodeError,
        product_service.SizeMasterNotFoundError,
        product_service.ColorMasterNotFoundError,
    ) as exc:
        _handle_sku_validation_errors(exc)
        raise
    return _to_response(product)


@router.put("/admin/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    payload: ProductUpdateRequest,
    db: DbSession,
    _current_staff: Annotated[Staff, Depends(_require_manager_or_admin)],
) -> ProductResponse:
    try:
        product = await product_service.update_product(db, product_id, payload)
    except product_service.ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "PRODUCT_NOT_FOUND", "product_id": exc.product_id},
        ) from exc
    except (
        product_service.SkuAlreadyExistsError,
        product_service.DuplicateBarcodeError,
        product_service.SizeMasterNotFoundError,
        product_service.ColorMasterNotFoundError,
    ) as exc:
        _handle_sku_validation_errors(exc)
        raise
    return _to_response(product)
