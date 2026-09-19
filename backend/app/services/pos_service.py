import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_FLOOR, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.discount import get_active_discounts
from app.crud.member import get_member_by_id
from app.crud.pos import persist_checkout
from app.crud.pricing import get_active_price_histories
from app.crud.product import get_products_by_ids
from app.crud.sku import get_skus_for_update
from app.crud.tax import get_active_tax_rate
from app.crud.transaction import (
    get_returned_quantities,
    get_sales_items_for_transaction,
    get_transaction_for_update,
)
from app.models.enums import (
    DiscountTargetTypeEnum,
    DiscountTypeEnum,
    MovementTypeEnum,
    PaymentMethodEnum,
    TransactionTypeEnum,
)
from app.models.inventory import InventoryHistory
from app.models.product import DiscountMaster, PriceHistory, Product, Sku
from app.models.transaction import SalesItem, Transaction
from app.schemas.pos import (
    CheckoutRequest,
    CheckoutResponse,
    RefundExchangeRequest,
    RefundExchangeResponse,
)


class SkuNotFoundError(Exception):
    def __init__(self, sku_ids: list[str]) -> None:
        self.sku_ids = sku_ids


class MemberNotFoundError(Exception):
    def __init__(self, member_id: str) -> None:
        self.member_id = member_id


class InsufficientStockError(Exception):
    def __init__(self, sku_id: str, available: int, requested: int) -> None:
        self.sku_id = sku_id
        self.available = available
        self.requested = requested


class TaxRateNotConfiguredError(Exception):
    pass


class InsufficientPaymentError(Exception):
    def __init__(self, required: int, tendered: int) -> None:
        self.required = required
        self.tendered = tendered


class PriceMismatchError(Exception):
    def __init__(self, server_calculated_total: int) -> None:
        self.server_calculated_total = server_calculated_total


class ParentTransactionNotFoundError(Exception):
    def __init__(self, transaction_id: str) -> None:
        self.transaction_id = transaction_id


class ParentTransactionNotEligibleError(Exception):
    def __init__(self, transaction_id: str) -> None:
        self.transaction_id = transaction_id


class ReturnItemNotInOriginalTransactionError(Exception):
    def __init__(self, sku_id: str) -> None:
        self.sku_id = sku_id


class ReturnQuantityExceededError(Exception):
    def __init__(self, sku_id: str, requested: int, remaining: int) -> None:
        self.sku_id = sku_id
        self.requested = requested
        self.remaining = remaining


@dataclass
class _LineCalc:
    sku: Sku
    product: Product
    quantity: int
    unit_price: int
    discount_amount: int
    line_total_ex_tax: int
    tax_rate: Decimal
    tax_amount: int
    line_total_inc_tax: int


def _resolve_unit_price(sku: Sku, product: Product, price_histories: list[PriceHistory]) -> int:
    sku_candidates = [h for h in price_histories if h.sku_id == sku.sku_id]
    if sku_candidates:
        return max(sku_candidates, key=lambda h: h.valid_from).price

    product_candidates = [
        h for h in price_histories if h.sku_id is None and h.product_id == product.product_id
    ]
    if product_candidates:
        return max(product_candidates, key=lambda h: h.valid_from).price

    return product.default_price


def _select_best_discount(candidates: list[DiscountMaster]) -> DiscountMaster:
    # priority は数値が小さいほど優先度が高いものとして扱う。
    return min(candidates, key=lambda d: d.priority)


def _resolve_discount(
    sku: Sku,
    product: Product,
    discounts: list[DiscountMaster],
    has_member: bool,
) -> DiscountMaster | None:
    # 値引き優先順位：SKU > 商品ID > 会員（設計仕様書 8節チェックリスト）。
    sku_matches = [
        d
        for d in discounts
        if d.target_type == DiscountTargetTypeEnum.SKU and d.sku_id == sku.sku_id
    ]
    if sku_matches:
        return _select_best_discount(sku_matches)

    product_matches = [
        d
        for d in discounts
        if d.target_type == DiscountTargetTypeEnum.PRODUCT and d.product_id == product.product_id
    ]
    if product_matches:
        return _select_best_discount(product_matches)

    if has_member:
        member_matches = [d for d in discounts if d.target_type == DiscountTargetTypeEnum.MEMBER]
        if member_matches:
            return _select_best_discount(member_matches)

    return None


def _compute_discount_amount(
    discount: DiscountMaster | None, unit_price: int, quantity: int
) -> int:
    line_subtotal = unit_price * quantity
    if discount is None:
        return 0

    if discount.discount_type == DiscountTypeEnum.RATE:
        raw = Decimal(line_subtotal) * discount.discount_value / Decimal(100)
    else:
        raw = discount.discount_value * quantity

    amount = int(raw.to_integral_value(rounding=ROUND_FLOOR))
    return max(0, min(amount, line_subtotal))


def _generate_transaction_id(now: datetime) -> str:
    return f"TX-{now:%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


@dataclass
class _OriginalAggregate:
    quantity: int
    unit_price: int
    tax_rate: Decimal
    discount_total: int
    tax_total: int
    line_total_ex_tax: int


def _aggregate_original_items(items: list[SalesItem]) -> dict[str, _OriginalAggregate]:
    # 通常販売の行（quantity > 0）のみを対象に、SKU単位で合算する。
    # tax_rate_snapshot は代表値として最初の行の値をそのまま引き継ぐ（除算による
    # 逆算は端数処理の丸め誤差で元の税率と一致しなくなるため避ける）。
    aggregates: dict[str, _OriginalAggregate] = {}
    for item in items:
        if item.quantity <= 0:
            continue
        existing = aggregates.get(item.sku_id)
        if existing is None:
            aggregates[item.sku_id] = _OriginalAggregate(
                quantity=item.quantity,
                unit_price=item.unit_price_snapshot,
                tax_rate=item.tax_rate_snapshot,
                discount_total=item.discount_amount_snapshot,
                tax_total=item.tax_amount_snapshot,
                line_total_ex_tax=item.line_total_ex_tax,
            )
        else:
            existing.quantity += item.quantity
            existing.discount_total += item.discount_amount_snapshot
            existing.tax_total += item.tax_amount_snapshot
            existing.line_total_ex_tax += item.line_total_ex_tax
    return aggregates


def _prorate_floor(total: int, numerator: int, denominator: int) -> int:
    return int(
        (Decimal(total) * numerator / Decimal(denominator)).to_integral_value(rounding=ROUND_FLOOR)
    )


async def checkout(db: AsyncSession, staff_id: str, request: CheckoutRequest) -> CheckoutResponse:
    now = datetime.now(UTC).replace(tzinfo=None)

    sku_ids = [item.sku_id for item in request.items]
    skus = await get_skus_for_update(db, sku_ids)
    missing = [sku_id for sku_id in sku_ids if sku_id not in skus or not skus[sku_id].is_active]
    if missing:
        await db.rollback()
        raise SkuNotFoundError(missing)

    if request.member_id is not None:
        member = await get_member_by_id(db, request.member_id)
        if member is None:
            await db.rollback()
            raise MemberNotFoundError(request.member_id)

    product_ids = {sku.product_id for sku in skus.values()}
    products = await get_products_by_ids(db, product_ids)
    price_histories = await get_active_price_histories(db, set(sku_ids), product_ids, now)
    discounts = await get_active_discounts(db, set(sku_ids), product_ids, now)
    tax_rate = await get_active_tax_rate(db, now)
    if tax_rate is None:
        await db.rollback()
        raise TaxRateNotConfiguredError

    lines: list[_LineCalc] = []
    for item in request.items:
        sku = skus[item.sku_id]
        if sku.store_stock < item.quantity:
            # rollback は ORM オブジェクトの属性を失効させるため、遅延ロードを
            # 誘発する前に必要な値をローカル変数へ退避しておく。
            available = sku.store_stock
            await db.rollback()
            raise InsufficientStockError(item.sku_id, available, item.quantity)

        product = products[sku.product_id]
        unit_price = _resolve_unit_price(sku, product, price_histories)
        discount = _resolve_discount(sku, product, discounts, request.member_id is not None)
        discount_amount = _compute_discount_amount(discount, unit_price, item.quantity)

        line_total_ex_tax = unit_price * item.quantity - discount_amount
        tax_amount = int(
            (Decimal(line_total_ex_tax) * tax_rate.tax_rate / Decimal(100)).to_integral_value(
                rounding=ROUND_FLOOR
            )
        )
        line_total_inc_tax = line_total_ex_tax + tax_amount

        lines.append(
            _LineCalc(
                sku=sku,
                product=product,
                quantity=item.quantity,
                unit_price=unit_price,
                discount_amount=discount_amount,
                line_total_ex_tax=line_total_ex_tax,
                tax_rate=tax_rate.tax_rate,
                tax_amount=tax_amount,
                line_total_inc_tax=line_total_inc_tax,
            )
        )

    subtotal_ex_tax = sum(line.unit_price * line.quantity for line in lines)
    discount_total = sum(line.discount_amount for line in lines)
    tax_amount_total = sum(line.tax_amount for line in lines)
    total_inc_tax = subtotal_ex_tax - discount_total + tax_amount_total

    if total_inc_tax != request.client_total:
        await db.rollback()
        raise PriceMismatchError(server_calculated_total=total_inc_tax)

    if (
        request.payment_method == PaymentMethodEnum.CASH
        and request.amount_tendered is not None
        and request.amount_tendered < total_inc_tax
    ):
        # 在庫引当・取引確定より前に検証する。ここで弾かないと、預かり不足の
        # まま売上・在庫が確定してしまう。
        await db.rollback()
        raise InsufficientPaymentError(required=total_inc_tax, tendered=request.amount_tendered)

    transaction_id = _generate_transaction_id(now)
    transaction = Transaction(
        transaction_id=transaction_id,
        member_id=request.member_id,
        staff_id=staff_id,
        payment_method=request.payment_method,
        subtotal_ex_tax=subtotal_ex_tax,
        discount_total=discount_total,
        tax_amount=tax_amount_total,
        total_inc_tax=total_inc_tax,
    )

    sales_items = [
        SalesItem(
            transaction_id=transaction_id,
            sku_id=line.sku.sku_id,
            product_id=line.product.product_id,
            quantity=line.quantity,
            unit_price_snapshot=line.unit_price,
            discount_amount_snapshot=line.discount_amount,
            tax_rate_snapshot=line.tax_rate,
            tax_amount_snapshot=line.tax_amount,
            line_total_ex_tax=line.line_total_ex_tax,
            line_total_inc_tax=line.line_total_inc_tax,
        )
        for line in lines
    ]

    inventory_histories = []
    for line in lines:
        line.sku.store_stock -= line.quantity
        inventory_histories.append(
            InventoryHistory(
                sku_id=line.sku.sku_id,
                location="STORE",
                quantity_delta=-line.quantity,
                movement_type=MovementTypeEnum.SALE,
                transaction_id=transaction_id,
                staff_id=staff_id,
            )
        )

    await persist_checkout(db, transaction, sales_items, inventory_histories)
    await db.commit()

    change = 0
    if request.payment_method == PaymentMethodEnum.CASH and request.amount_tendered is not None:
        change = request.amount_tendered - total_inc_tax

    return CheckoutResponse(
        transaction_id=transaction_id,
        subtotal_ex_tax=subtotal_ex_tax,
        discount_total=discount_total,
        tax_amount=tax_amount_total,
        total_inc_tax=total_inc_tax,
        change=change,
    )


async def refund_exchange(
    db: AsyncSession, staff_id: str, request: RefundExchangeRequest
) -> RefundExchangeResponse:
    now = datetime.now(UTC).replace(tzinfo=None)

    # 同一元取引に対する返品・交換の同時登録による二重返品を防ぐため、
    # 元取引行自体をロックしてから返品済み数量を確認する。
    parent = await get_transaction_for_update(db, request.parent_transaction_id)
    if parent is None:
        raise ParentTransactionNotFoundError(request.parent_transaction_id)
    if parent.tx_type != TransactionTypeEnum.SALE:
        await db.rollback()
        raise ParentTransactionNotEligibleError(request.parent_transaction_id)

    # member_id はクライアントに送らせず、元取引から引き継ぐ（改ざん防止）。
    parent_member_id = parent.member_id
    parent_transaction_id = parent.transaction_id

    original_items = await get_sales_items_for_transaction(db, parent_transaction_id)
    original_agg = _aggregate_original_items(original_items)
    already_returned = await get_returned_quantities(db, parent_transaction_id)

    for ret in request.return_items:
        if ret.sku_id not in original_agg:
            raise ReturnItemNotInOriginalTransactionError(ret.sku_id)
        remaining = original_agg[ret.sku_id].quantity - already_returned.get(ret.sku_id, 0)
        if ret.quantity > remaining:
            raise ReturnQuantityExceededError(ret.sku_id, ret.quantity, remaining)

    all_sku_ids = {item.sku_id for item in request.return_items} | {
        item.sku_id for item in request.exchange_items
    }
    skus = await get_skus_for_update(db, list(all_sku_ids))
    missing = [sku_id for sku_id in all_sku_ids if sku_id not in skus]
    if missing:
        await db.rollback()
        raise SkuNotFoundError(missing)

    # exchange_items（顧客へ新たに渡す商品）は通常販売と同様に有効なSKUのみ許可。
    inactive_exchange = sorted(
        {item.sku_id for item in request.exchange_items if not skus[item.sku_id].is_active}
    )
    if inactive_exchange:
        await db.rollback()
        raise SkuNotFoundError(inactive_exchange)

    exchange_product_ids = {skus[item.sku_id].product_id for item in request.exchange_items}
    products: dict[str, Product] = {}
    price_histories: list[PriceHistory] = []
    discounts: list[DiscountMaster] = []
    tax_rate = None
    if request.exchange_items:
        products = await get_products_by_ids(db, exchange_product_ids)
        price_histories = await get_active_price_histories(
            db, {item.sku_id for item in request.exchange_items}, exchange_product_ids, now
        )
        discounts = await get_active_discounts(
            db, {item.sku_id for item in request.exchange_items}, exchange_product_ids, now
        )
        tax_rate = await get_active_tax_rate(db, now)
        if tax_rate is None:
            await db.rollback()
            raise TaxRateNotConfiguredError

    sales_items: list[SalesItem] = []
    inventory_histories: list[InventoryHistory] = []
    subtotal_ex_tax = 0
    discount_total = 0
    tax_amount_total = 0
    stock_deltas: dict[str, int] = {}

    for ret in request.return_items:
        orig = original_agg[ret.sku_id]
        discount = -_prorate_floor(orig.discount_total, ret.quantity, orig.quantity)
        tax = -_prorate_floor(orig.tax_total, ret.quantity, orig.quantity)
        line_ex_tax = -_prorate_floor(orig.line_total_ex_tax, ret.quantity, orig.quantity)
        line_inc_tax = line_ex_tax + tax

        subtotal_ex_tax += -(orig.unit_price * ret.quantity)
        discount_total += discount
        tax_amount_total += tax

        sales_items.append(
            SalesItem(
                sku_id=ret.sku_id,
                product_id=skus[ret.sku_id].product_id,
                quantity=-ret.quantity,
                unit_price_snapshot=orig.unit_price,
                discount_amount_snapshot=discount,
                tax_rate_snapshot=orig.tax_rate,
                tax_amount_snapshot=tax,
                line_total_ex_tax=line_ex_tax,
                line_total_inc_tax=line_inc_tax,
            )
        )
        stock_deltas[ret.sku_id] = stock_deltas.get(ret.sku_id, 0) + ret.quantity

    for exc in request.exchange_items:
        sku = skus[exc.sku_id]
        if sku.store_stock + stock_deltas.get(exc.sku_id, 0) < exc.quantity:
            available = sku.store_stock + stock_deltas.get(exc.sku_id, 0)
            await db.rollback()
            raise InsufficientStockError(exc.sku_id, available, exc.quantity)

        product = products[sku.product_id]
        unit_price = _resolve_unit_price(sku, product, price_histories)
        discount_master = _resolve_discount(sku, product, discounts, parent_member_id is not None)
        discount = _compute_discount_amount(discount_master, unit_price, exc.quantity)
        line_ex_tax = unit_price * exc.quantity - discount
        tax = int(
            (Decimal(line_ex_tax) * tax_rate.tax_rate / Decimal(100)).to_integral_value(
                rounding=ROUND_FLOOR
            )
        )
        line_inc_tax = line_ex_tax + tax

        subtotal_ex_tax += unit_price * exc.quantity
        discount_total += discount
        tax_amount_total += tax

        sales_items.append(
            SalesItem(
                sku_id=exc.sku_id,
                product_id=product.product_id,
                quantity=exc.quantity,
                unit_price_snapshot=unit_price,
                discount_amount_snapshot=discount,
                tax_rate_snapshot=tax_rate.tax_rate,
                tax_amount_snapshot=tax,
                line_total_ex_tax=line_ex_tax,
                line_total_inc_tax=line_inc_tax,
            )
        )
        stock_deltas[exc.sku_id] = stock_deltas.get(exc.sku_id, 0) - exc.quantity

    total_inc_tax = subtotal_ex_tax - discount_total + tax_amount_total

    if total_inc_tax != request.client_total:
        await db.rollback()
        raise PriceMismatchError(server_calculated_total=total_inc_tax)

    if (
        request.payment_method == PaymentMethodEnum.CASH
        and total_inc_tax > 0
        and request.amount_tendered is not None
        and request.amount_tendered < total_inc_tax
    ):
        # total_inc_tax が正（＝顧客が追加支払いする交換差額）の場合のみ検証する。
        # 返金（負）や差額なし（0）の場合は預かり金額の過不足という概念自体が
        # 存在しないため対象外とする。
        await db.rollback()
        raise InsufficientPaymentError(required=total_inc_tax, tendered=request.amount_tendered)

    transaction_id = _generate_transaction_id(now)
    transaction = Transaction(
        transaction_id=transaction_id,
        member_id=parent_member_id,
        staff_id=staff_id,
        payment_method=request.payment_method,
        subtotal_ex_tax=subtotal_ex_tax,
        discount_total=discount_total,
        tax_amount=tax_amount_total,
        total_inc_tax=total_inc_tax,
        tx_type=request.tx_type,
        parent_transaction_id=parent_transaction_id,
    )
    for item in sales_items:
        item.transaction_id = transaction_id

    for ret in request.return_items:
        skus[ret.sku_id].store_stock += ret.quantity
        inventory_histories.append(
            InventoryHistory(
                sku_id=ret.sku_id,
                location="STORE",
                quantity_delta=ret.quantity,
                movement_type=MovementTypeEnum.RETURN,
                transaction_id=transaction_id,
                staff_id=staff_id,
            )
        )
    for exc in request.exchange_items:
        skus[exc.sku_id].store_stock -= exc.quantity
        inventory_histories.append(
            InventoryHistory(
                sku_id=exc.sku_id,
                location="STORE",
                quantity_delta=-exc.quantity,
                movement_type=MovementTypeEnum.SALE,
                transaction_id=transaction_id,
                staff_id=staff_id,
            )
        )

    await persist_checkout(db, transaction, sales_items, inventory_histories)
    await db.commit()

    change = 0
    if (
        request.payment_method == PaymentMethodEnum.CASH
        and request.amount_tendered is not None
        and total_inc_tax > 0
    ):
        change = request.amount_tendered - total_inc_tax

    return RefundExchangeResponse(
        transaction_id=transaction_id,
        parent_transaction_id=parent_transaction_id,
        tx_type=request.tx_type,
        subtotal_ex_tax=subtotal_ex_tax,
        discount_total=discount_total,
        tax_amount=tax_amount_total,
        total_inc_tax=total_inc_tax,
        change=change,
    )
