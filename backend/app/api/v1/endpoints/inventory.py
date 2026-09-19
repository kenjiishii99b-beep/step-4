from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentStaff, DbSession, require_roles
from app.models.enums import RoleEnum
from app.models.product import Sku
from app.models.staff import Staff
from app.schemas.inventory import (
    InventoryReceiptRequest,
    InventoryStatusResponse,
    InventoryTransferRequest,
)
from app.services import inventory_service

router = APIRouter()

_require_manager_or_admin = require_roles([RoleEnum.MANAGER, RoleEnum.ADMIN])


def _to_response(sku: Sku) -> InventoryStatusResponse:
    return InventoryStatusResponse(
        sku_id=sku.sku_id,
        store_stock=sku.store_stock,
        warehouse_stock=sku.warehouse_stock,
    )


@router.get("/inventory/{sku_id}", response_model=InventoryStatusResponse)
async def get_inventory_status(
    sku_id: str, db: DbSession, _current_staff: CurrentStaff
) -> InventoryStatusResponse:
    try:
        sku = await inventory_service.get_inventory_status(db, sku_id)
    except inventory_service.SkuNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "SKU_NOT_FOUND", "sku_id": exc.sku_id},
        ) from exc
    return _to_response(sku)


@router.post("/inventory/receipt", response_model=InventoryStatusResponse)
async def receive_stock(
    payload: InventoryReceiptRequest, db: DbSession, current_staff: CurrentStaff
) -> InventoryStatusResponse:
    try:
        sku = await inventory_service.receive_stock(db, current_staff.staff_id, payload)
    except inventory_service.SkuNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "SKU_NOT_FOUND", "sku_id": exc.sku_id},
        ) from exc
    return _to_response(sku)


@router.post("/inventory/transfer", response_model=InventoryStatusResponse)
async def transfer_stock(
    payload: InventoryTransferRequest,
    db: DbSession,
    current_staff: Annotated[Staff, Depends(_require_manager_or_admin)],
) -> InventoryStatusResponse:
    try:
        sku = await inventory_service.transfer_stock(db, current_staff.staff_id, payload)
    except inventory_service.SkuNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "SKU_NOT_FOUND", "sku_id": exc.sku_id},
        ) from exc
    except inventory_service.InsufficientStockError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "INSUFFICIENT_STOCK",
                "sku_id": exc.sku_id,
                "location": exc.location.value,
                "available": exc.available,
                "requested": exc.requested,
            },
        ) from exc
    return _to_response(sku)
