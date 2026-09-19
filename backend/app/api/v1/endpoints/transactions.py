from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentStaff, DbSession
from app.schemas.transaction import SalesItemResponse, TransactionResponse
from app.services import transaction_service

router = APIRouter()


@router.get("/transactions/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: str, db: DbSession, _current_staff: CurrentStaff
) -> TransactionResponse:
    try:
        transaction, items = await transaction_service.get_transaction_detail(db, transaction_id)
    except transaction_service.TransactionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "TRANSACTION_NOT_FOUND", "transaction_id": exc.transaction_id},
        ) from exc

    return TransactionResponse(
        transaction_id=transaction.transaction_id,
        member_id=transaction.member_id,
        staff_id=transaction.staff_id,
        payment_method=transaction.payment_method,
        subtotal_ex_tax=transaction.subtotal_ex_tax,
        discount_total=transaction.discount_total,
        tax_amount=transaction.tax_amount,
        total_inc_tax=transaction.total_inc_tax,
        tx_type=transaction.tx_type,
        parent_transaction_id=transaction.parent_transaction_id,
        created_at=transaction.created_at,
        items=[
            SalesItemResponse(
                sku_id=item.sku_id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price_snapshot=item.unit_price_snapshot,
                discount_amount_snapshot=item.discount_amount_snapshot,
                tax_rate_snapshot=item.tax_rate_snapshot,
                tax_amount_snapshot=item.tax_amount_snapshot,
                line_total_ex_tax=item.line_total_ex_tax,
                line_total_inc_tax=item.line_total_inc_tax,
            )
            for item in items
        ],
    )
