"""Bounded, sign-preserving numeric parsing shared by checks and report diffs."""

import re
import unicodedata
from decimal import Decimal, InvalidOperation

_NUMBER = r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_SCALAR = re.compile(rf"{_NUMBER}\Z", re.ASCII)
_TOKEN = re.compile(rf"(?<![\d.])({_NUMBER})(\s*[%‰])?(?![\d.])", re.ASCII)


def normalize_number_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).replace("−", "-")


def parse_number(value: str) -> Decimal | None:
    text = normalize_number_text(value).strip()
    # Exponents, NaN, infinity and excessive magnitudes are not valid report scalars.
    if len(text) > 64 or not _SCALAR.fullmatch(text):
        return None
    try:
        return Decimal(text.replace(",", ""))
    except InvalidOperation:
        return None


def number_tokens(value: str) -> list[tuple[Decimal, str]]:
    tokens = []
    for match in _TOKEN.finditer(normalize_number_text(value)):
        number = parse_number(match[1])
        if number is not None:
            tokens.append((number, (match[2] or "").strip()))
    return tokens

# Product/precision specifications are not measured quantities (FP16, 1.6T, 800G).
_SPEC = re.compile(r"(?i)\b(?:FP|BF|INT)\d+\b|(?<![\w.])\d+(?:\.\d+)?\s*(?:T|G)(?![A-Za-z])")
_QUANTITY = re.compile(rf"(?<![\w.])({_NUMBER})\s*(万亿|亿|万|千)?\s*([%‰])?(?![\d.])", re.ASCII)
_SCALES = {"": Decimal(1), "千": Decimal(1000), "万": Decimal(10000), "亿": Decimal(100000000), "万亿": Decimal(1000000000000)}


def quantity_tokens(value: str) -> list[tuple[Decimal, str]]:
    text = _SPEC.sub("", normalize_number_text(value))
    return [(number * _SCALES[match[2] or ""], match[3] or "")
            for match in _QUANTITY.finditer(text)
            if (number := parse_number(match[1])) is not None]


def scalar_in_display_unit(value: str, unit: str) -> Decimal | None:
    number = parse_number(value)
    if number is None:
        return None
    match = re.match(r"^(万亿|亿|万|千)", normalize_number_text(unit).strip())
    return number * _SCALES[match[1] if match else ""]


def is_bounded_quantity(value: str) -> bool:
    return bool(re.search(r"超过|超出|超(?=\d)|不足|以上|以下|至少|至多|不低于|不超过|约?\s*[<>≤≥]|[~～–—]|至|到", value))


def specification_tokens(value: str) -> set[str]:
    return {re.sub(r"\s+", "", match[0]).upper() for match in _SPEC.finditer(normalize_number_text(value))}
