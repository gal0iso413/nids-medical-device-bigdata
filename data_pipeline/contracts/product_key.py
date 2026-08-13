"""Canonical normalization for the official NIDS three-key product identity."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import math
from numbers import Integral
import re
from typing import Any, Final

import numpy as np


MAX_EXACT_FLOAT_INTEGER: Final = 2**53
_INTEGER_CODE_PATTERN: Final = re.compile(r"^\+?\d+(?:\.0+)?$")


def normalize_integer_code(value: Any) -> str | None:
    """Return one canonical non-negative integer code, or ``None`` if invalid.

    The official item/model/UDI-DI serial fields are integer codes. Their
    leading zeroes are not meaningful, while arbitrary string dimensions keep
    their original leading zeroes and must not use this function.
    """
    if value is None or isinstance(value, (bool, np.bool_)):
        return None
    if isinstance(value, Integral):
        integer = int(value)
        return str(integer) if integer >= 0 else None
    if isinstance(value, Decimal):
        if (
            not value.is_finite()
            or value < 0
            or value != value.to_integral_value()
        ):
            return None
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        numeric = float(value)
        if (
            not math.isfinite(numeric)
            or abs(numeric) > MAX_EXACT_FLOAT_INTEGER
            or numeric < 0
            or not numeric.is_integer()
        ):
            return None
        return str(int(numeric))
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or not _INTEGER_CODE_PATTERN.fullmatch(text):
        return None
    try:
        parsed = Decimal(text)
    except InvalidOperation:
        return None
    if not parsed.is_finite() or parsed != parsed.to_integral_value():
        return None
    return str(int(parsed))
