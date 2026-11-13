from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import SupportsInt


def as_decimal(value: object) -> Decimal:
    """Convert numeric input without introducing binary floating-point drift."""
    if isinstance(value, bool):
        raise ValueError("Boolean values are not valid monetary amounts.")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Amount must be a finite decimal number.") from exc
    if not amount.is_finite():
        raise ValueError("Amount must be a finite decimal number.")
    return amount


def quantize_money(value: object, decimal_places: int = 2) -> Decimal:
    if decimal_places < 0:
        raise ValueError("decimal_places must be non-negative.")
    amount = as_decimal(value)
    quantum = Decimal(1).scaleb(-decimal_places)
    return amount.quantize(quantum, rounding=ROUND_HALF_UP)


def to_minor_units(value: object, decimal_places: int = 0) -> int:
    return int(quantize_money(value, decimal_places).scaleb(decimal_places))


def from_minor_units(value: SupportsInt, decimal_places: int = 0) -> Decimal:
    if decimal_places < 0:
        raise ValueError("decimal_places must be non-negative.")
    return Decimal(int(value)).scaleb(-decimal_places)
