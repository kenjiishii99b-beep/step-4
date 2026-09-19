from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentStaff, DbSession
from app.schemas.product import SkuLookupResponse
from app.services import product_service

router = APIRouter()


@router.get("/skus/barcode/{ean13}", response_model=SkuLookupResponse)
async def get_sku_by_barcode(
    ean13: str, db: DbSession, _current_staff: CurrentStaff
) -> SkuLookupResponse:
    try:
        return await product_service.lookup_sku_by_barcode(db, ean13)
    except product_service.SkuNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "SKU_NOT_FOUND", "barcode_ean13": exc.barcode_ean13},
        ) from exc
