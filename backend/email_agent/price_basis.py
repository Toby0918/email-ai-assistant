"""Explicit price bases, decimal normalization and bounded worksheet row binding."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext
from datetime import date, datetime
import re

from .attachment_identifiers import valid_constructed_reference


_NUMBER = r"(?:\d{1,3}(?:,\d{3}){1,3}|\d{1,12})(?:\.\d{1,6})?"
_CURRENCY = r"(?:USD|EUR|CNY|RMB|GBP|JPY|CAD|AUD|INR)"
_UNIT = r"(?:EA|PCS|PC|SET|SETS|KG)"
_PRICE = re.compile(rf"(?:net\s+)?price\s*:\s*(?P<currency>{_CURRENCY})\s+(?P<amount>{_NUMBER})\s+per\s+(?P<basis>{_NUMBER})\s+(?P<unit>{_UNIT})", re.I)
_FACT = re.compile(
    rf"Price basis: (?P<amount>{_NUMBER}) (?P<currency>{_CURRENCY}) per (?P<basis>{_NUMBER}) (?P<unit>{_UNIT}) "
    rf"(?P<sign>=|≈) (?P<normalized>{_NUMBER}) (?P=currency)/(?P=unit)"
    r"(?P<scope>(?:; (?:Item|Org|Plant): [A-Za-z0-9][A-Za-z0-9_.-]{0,39})*)"
    r"(?:; Effective: \d{4}-\d{2}-\d{2})?"
    r"(?:; sheet (?P<sheet>\d{1,2}) row (?P<row>\d{1,3}))?", re.I,
)
_HEADERS = {
    "newprice": "amount", "crcy": "currency", "ircur": "currency", "priceunit": "basis",
    "opu": "unit", "ordun": "unit", "porg": "org", "purchorg": "org", "materialnumber": "item",
    "effectivedate": "effective_date",
    "netprice": "amount", "netpricechangerequest": "amount", "price": "amount",
    "currency": "currency", "priceperqty": "basis", "priceperquantity": "basis",
    "orderunit": "unit", "unit": "unit", "material": "item", "sku": "item", "item": "item",
    "purchaseorg": "org", "purchasingorganization": "org", "plant": "plant",
}
_REQUIRED = {"amount", "currency", "basis", "unit"}


def _number(value: object) -> Decimal | None:
    text = str(value).strip()
    if not re.fullmatch(_NUMBER, text):
        return None
    try:
        return Decimal(text.replace(",", ""))
    except InvalidOperation:
        return None


def _calculation(amount: object, basis: object, currency: object, unit: object) -> str:
    price, base = _number(amount), _number(basis)
    curr, order_unit = str(currency).strip().upper(), str(unit).strip().upper()
    if price is None or base is None or base <= 0 or not re.fullmatch(_CURRENCY, curr) or not re.fullmatch(_UNIT, order_unit):
        return ""
    with localcontext() as context:
        context.prec = 32
        normalized = price / base
        # Display exact cents where possible; otherwise bound and label rounding.
        places = Decimal("0.01") if normalized == normalized.quantize(Decimal("0.01")) else Decimal("0.000001")
        displayed = normalized.quantize(places)
        sign = "=" if displayed * base == price else "≈"
    return f"Price basis: {format(price, 'f')} {curr} per {format(base, 'f')} {order_unit} {sign} {displayed} {curr}/{order_unit}"


def price_context_is_qualified(text: str) -> bool:
    return bool(re.search(r"\b(?:correction|incorrect|retracted|withdrawn|cancelled|canceled|void|superseded|hypothetical|if|unless|example|template|options)\b|not confirmed|do not use|更正|取消|作废|如果|假设|示例|模板", text, re.I))


def price_statement_facts(text: str) -> list[str]:
    if price_context_is_qualified(text):
        return []
    facts = []
    for clause in re.split(r"[\n;；。]|\.(?=\s|$)", text[:8000]):
        match = _PRICE.fullmatch(clause.strip())
        if match and (fact := _calculation(match['amount'], match['basis'], match['currency'], match['unit'])):
            facts.append(fact)
    return list(dict.fromkeys(facts))[:5]


def valid_price_fact(value: str) -> bool:
    match = _FACT.fullmatch(value)
    if not match:
        return False
    if any(not _valid_scope(token) for token in re.findall(r"; (?:Item|Org|Plant): ([^;]+)", value)):
        return False
    expected = _calculation(match['amount'], match['basis'], match['currency'], match['unit'])
    prefix = value.split(";", 1)[0]
    return bool(expected) and expected == prefix


def _valid_scope(value: str) -> bool:
    # Retain existing identifier privacy checks; alphabetic organization/plant
    # codes are also permitted, but links and phone/account-like shapes are not.
    return valid_constructed_reference(value) or bool(re.fullmatch(r"[A-Za-z][A-Za-z_-]{0,31}", value))


class PriceTable:
    """One worksheet's explicit header map; blank/header rows reset the scope."""
    def __init__(self, sheet_number: int):
        self.sheet_number = sheet_number
        self.columns: dict[str, int] = {}

    def read_row(self, row: tuple[object, ...], row_number: int) -> str:
        bounded = row[:32]
        # Workbooks provide scalar values. Do not inspect deferred/non-scalar cells
        # or stringify content outside the existing per-row/per-cell read budget.
        if any(value is not None and not isinstance(value, (str, int, float, Decimal, date)) for value in bounded):
            self.columns = {}
            return ""
        if sum(min(len(str(value)), 1000) for value in bounded if value is not None) > 1000:
            self.columns = {}
            return ""
        if not any(value is not None and str(value).strip() for value in bounded):
            self.columns = {}
            return ""
        tokens = [re.sub(r"[^a-z0-9]", "", str(value)[:1000].lower()) for value in bounded]
        names = [_HEADERS.get(token, "amount" if re.fullmatch(r"q[1-4]20\d{2}", token) else None) for token in tokens]
        recognized = [name for name in names if name]
        if len(recognized) >= 2:
            self.columns = ({name: index for index, name in enumerate(names) if name}
                            if len(recognized) == len(set(recognized)) and _REQUIRED.issubset(recognized) else {})
            return ""
        if not self.columns:
            return ""
        values = {name: bounded[index] if index < len(bounded) else None for name, index in self.columns.items()}
        fact = _calculation(values['amount'], values['basis'], values['currency'], values['unit'])
        if not fact:
            if _number(values['amount']) is None and _number(values['basis']) is None:
                self.columns = {}
            return ""
        for field, label in (("item", "Item"), ("org", "Org"), ("plant", "Plant")):
            if field in values:
                token = str(values[field]).strip() if values[field] is not None else ""
                if not _valid_scope(token):
                    return ""  # Never silently drop a mapped scope field.
                fact += f"; {label}: {token}"
        if "effective_date" in values:
            value = values['effective_date']
            if isinstance(value, datetime):
                value = value.date()
            token = value.isoformat() if isinstance(value, date) else str(value).strip()
            try:
                date.fromisoformat(token)
            except ValueError:
                return ""
            fact += f"; Effective: {token}"
        fact += f"; sheet {self.sheet_number} row {row_number}"
        return fact if len(fact) <= 240 else ""
