"""RFC 8785 JSON Canonicalization Scheme, the subset the ledger needs.

Sorted keys (by UTF-16 code units), no whitespace, ES6 number formatting, no NaN or infinities.
"""

from __future__ import annotations

import json
import math
from typing import Any


def _es6_number(x: float) -> str:
    if math.isnan(x) or math.isinf(x):
        raise ValueError("JCS forbids NaN and infinities")
    if x == 0:
        return "0"
    if x == int(x) and abs(x) < 2**53:
        return str(int(x))
    r = repr(x)  # shortest round-trip repr, like ES6
    if "e" not in r and "E" not in r:
        return r
    mant, exp = r.lower().split("e")
    e = int(exp)
    if -7 < e < 21:
        # ES6 prints these without an exponent
        sign = "-" if mant.startswith("-") else ""
        mant = mant.lstrip("-")
        digits = mant.replace(".", "")
        point = (mant.index(".") if "." in mant else len(mant)) + e
        if point <= 0:
            return f"{sign}0.{'0' * (-point)}{digits}"
        if point >= len(digits):
            return f"{sign}{digits}{'0' * (point - len(digits))}"
        return f"{sign}{digits[:point]}.{digits[point:]}"
    return f"{mant}e{'+' if e > 0 else '-'}{abs(e)}"


def _emit(v: Any, out: list[str]) -> None:
    if v is None:
        out.append("null")
    elif v is True:
        out.append("true")
    elif v is False:
        out.append("false")
    elif isinstance(v, int):
        out.append(str(v))
    elif isinstance(v, float):
        out.append(_es6_number(v))
    elif isinstance(v, str):
        out.append(json.dumps(v, ensure_ascii=False))
    elif isinstance(v, list | tuple):
        out.append("[")
        for i, item in enumerate(v):
            if i:
                out.append(",")
            _emit(item, out)
        out.append("]")
    elif isinstance(v, dict):
        out.append("{")
        keys = sorted(v.keys(), key=lambda k: str(k).encode("utf-16-be"))
        for i, k in enumerate(keys):
            if i:
                out.append(",")
            out.append(json.dumps(str(k), ensure_ascii=False))
            out.append(":")
            _emit(v[k], out)
        out.append("}")
    else:
        raise TypeError(f"JCS cannot serialise {type(v).__name__}")


def canonicalize(obj: Any) -> str:
    out: list[str] = []
    _emit(obj, out)
    return "".join(out)
