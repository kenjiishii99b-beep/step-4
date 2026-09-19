from enum import StrEnum


class RoleEnum(StrEnum):
    STAFF = "STAFF"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"


class PaymentMethodEnum(StrEnum):
    CASH = "CASH"
    CREDIT_CARD = "CREDIT_CARD"
    QR_CODE = "QR_CODE"
    IC = "IC"


class TransactionTypeEnum(StrEnum):
    SALE = "SALE"
    RETURN = "RETURN"
    EXCHANGE = "EXCHANGE"


class DiscountTargetTypeEnum(StrEnum):
    SKU = "SKU"
    PRODUCT = "PRODUCT"
    MEMBER = "MEMBER"


class DiscountTypeEnum(StrEnum):
    RATE = "RATE"
    AMOUNT = "AMOUNT"


class MovementTypeEnum(StrEnum):
    RECEIPT = "RECEIPT"
    SALE = "SALE"
    RETURN = "RETURN"
    TRANSFER = "TRANSFER"
    ADJUSTMENT = "ADJUSTMENT"


__all__ = [
    "DiscountTargetTypeEnum",
    "DiscountTypeEnum",
    "MovementTypeEnum",
    "PaymentMethodEnum",
    "RoleEnum",
    "TransactionTypeEnum",
]
