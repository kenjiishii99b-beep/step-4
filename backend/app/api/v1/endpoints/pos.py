from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentStaff, DbSession
from app.schemas.pos import (
    CheckoutRequest,
    CheckoutResponse,
    RefundExchangeRequest,
    RefundExchangeResponse,
)
from app.services import pos_service

router = APIRouter()


@router.post("/pos/checkout", response_model=CheckoutResponse)
async def checkout(
    payload: CheckoutRequest, db: DbSession, current_staff: CurrentStaff
) -> CheckoutResponse:
    try:
        return await pos_service.checkout(db, current_staff.staff_id, payload)
    except pos_service.SkuNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "SKU_NOT_FOUND", "sku_ids": exc.sku_ids},
        ) from exc
    except pos_service.MemberNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "MEMBER_NOT_FOUND", "member_id": exc.member_id},
        ) from exc
    except pos_service.InsufficientStockError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "INSUFFICIENT_STOCK",
                "sku_id": exc.sku_id,
                "available": exc.available,
                "requested": exc.requested,
            },
        ) from exc
    except pos_service.TaxRateNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "TAX_RATE_NOT_CONFIGURED"},
        ) from exc
    except pos_service.PriceMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "PRICE_MISMATCH",
                "current_total": exc.server_calculated_total,
            },
        ) from exc
    except pos_service.InsufficientPaymentError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "INSUFFICIENT_PAYMENT",
                "required": exc.required,
                "tendered": exc.tendered,
            },
        ) from exc


@router.post("/pos/refund-exchange", response_model=RefundExchangeResponse)
async def refund_exchange(
    payload: RefundExchangeRequest, db: DbSession, current_staff: CurrentStaff
) -> RefundExchangeResponse:
    try:
        return await pos_service.refund_exchange(db, current_staff.staff_id, payload)
    except pos_service.ParentTransactionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "PARENT_TRANSACTION_NOT_FOUND",
                "transaction_id": exc.transaction_id,
            },
        ) from exc
    except pos_service.ParentTransactionNotEligibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "PARENT_TRANSACTION_NOT_ELIGIBLE",
                "transaction_id": exc.transaction_id,
            },
        ) from exc
    except pos_service.ReturnItemNotInOriginalTransactionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "RETURN_ITEM_NOT_IN_ORIGINAL_TRANSACTION",
                "sku_id": exc.sku_id,
            },
        ) from exc
    except pos_service.ReturnQuantityExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "RETURN_QUANTITY_EXCEEDED",
                "sku_id": exc.sku_id,
                "requested": exc.requested,
                "remaining": exc.remaining,
            },
        ) from exc
    except pos_service.SkuNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "SKU_NOT_FOUND", "sku_ids": exc.sku_ids},
        ) from exc
    except pos_service.InsufficientStockError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "INSUFFICIENT_STOCK",
                "sku_id": exc.sku_id,
                "available": exc.available,
                "requested": exc.requested,
            },
        ) from exc
    except pos_service.TaxRateNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "TAX_RATE_NOT_CONFIGURED"},
        ) from exc
    except pos_service.PriceMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "PRICE_MISMATCH",
                "current_total": exc.server_calculated_total,
            },
        ) from exc
    except pos_service.InsufficientPaymentError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "INSUFFICIENT_PAYMENT",
                "required": exc.required,
                "tendered": exc.tendered,
            },
        ) from exc
