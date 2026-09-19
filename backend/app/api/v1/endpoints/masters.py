from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import DbSession, require_roles
from app.models.enums import RoleEnum
from app.models.staff import Staff
from app.schemas.masters import (
    DiscountResponse,
    DiscountUpsertRequest,
    TaxRateResponse,
    TaxRateUpsertRequest,
)
from app.services import master_service

router = APIRouter()

_require_manager_or_admin = require_roles([RoleEnum.MANAGER, RoleEnum.ADMIN])
_require_admin = require_roles([RoleEnum.ADMIN])


@router.put("/masters/discounts", response_model=DiscountResponse)
async def upsert_discount(
    payload: DiscountUpsertRequest,
    db: DbSession,
    _current_staff: Annotated[Staff, Depends(_require_manager_or_admin)],
) -> DiscountResponse:
    try:
        discount = await master_service.upsert_discount(db, payload)
    except master_service.SkuNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "SKU_NOT_FOUND", "sku_id": exc.sku_id},
        ) from exc
    except master_service.ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "PRODUCT_NOT_FOUND", "product_id": exc.product_id},
        ) from exc

    return DiscountResponse(
        discount_id=discount.discount_id,
        target_type=discount.target_type,
        product_id=discount.product_id,
        sku_id=discount.sku_id,
        discount_type=discount.discount_type,
        discount_value=discount.discount_value,
        valid_from=discount.valid_from,
        valid_to=discount.valid_to,
        priority=discount.priority,
        is_active=discount.is_active,
    )


@router.put("/masters/tax-rates", response_model=TaxRateResponse)
async def upsert_tax_rate(
    payload: TaxRateUpsertRequest,
    db: DbSession,
    _current_staff: Annotated[Staff, Depends(_require_admin)],
) -> TaxRateResponse:
    tax_rate = await master_service.upsert_tax_rate(db, payload)
    return TaxRateResponse(
        tax_rate_id=tax_rate.tax_rate_id,
        tax_rate=tax_rate.tax_rate,
        valid_from=tax_rate.valid_from,
        valid_to=tax_rate.valid_to,
        is_active=tax_rate.is_active,
    )
