from app.services.fee_engines.rotating.resolver.schemas.payment_type import PaymentType


def classify_payment(
    entered: int,
    total_outstanding: int,
    has_arrears: bool,
    is_partial: bool,
    is_advance: bool,
) -> PaymentType:
    if has_arrears and entered < total_outstanding:
        return PaymentType.ARREARS_PARTIAL
    if has_arrears:
        return PaymentType.ARREARS
    if is_partial:
        return PaymentType.PARTIAL
    if is_advance:
        return PaymentType.ADVANCE
    return PaymentType.NORMAL
