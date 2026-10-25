import re
from typing import List, Optional, Tuple

from app.models import OrderItemLine

# OCR emits table cells one per line, so a row is recovered as a run of cells
# in which some quantity * unit price == amount.

QTY_HEADER = re.compile(r"^[^\d、：:]{0,6}(?:数量|套数|件数|只数|qty|quantity)[^：:\d]{0,4}$", re.I)
PRICE_HEADER = re.compile(r"单价|unit\s*price", re.I)
HEADER_WORD = re.compile(r"序号|品名|名称|物品|项目|规格|型号|编号|说明|单位|数量|套数|单价|金额|总价|小计|备注|合计|^#$")
TABLE_END = re.compile(r"^(?:合计|总计|小计|价税合计|金额合计)|大写")

UNITS = {
    "个", "台", "包", "箱", "袋", "套", "只", "件", "张", "卷", "把", "盒", "支", "米", "吨", "千克", "kg",
    "pcs", "pc", "set", "sets", "unit", "units", "each", "ea", "bag", "cup",
}
NUM_TOKEN = re.compile(
    r"^[¥￥$Y?？\s]*(?P<int>\d{1,3}(?:,\d{3})+|\d+)(?:\.\s?(?P<dec>\d{1,2}))?\s*(?P<unit>[^\d\s.,]{1,4})?$"
)


class _Num:
    def __init__(self, raw: str, value: float, unit: Optional[str]):
        self.raw = raw
        self.value = value
        self.unit = unit
        # Amount cells carry decimals or a currency mark; bare integers are often row numbers.
        self.money_like = "." in raw or bool(re.match(r"^[¥￥$Y]", raw))


def _parse_num(line: str) -> Optional[_Num]:
    m = NUM_TOKEN.match(line)
    if not m:
        return None
    unit = m.group("unit")
    if unit and unit.lower() not in UNITS:
        return None
    value = float(m.group("int").replace(",", "") + "." + (m.group("dec") or "0"))
    return _Num(line, value, unit)


def _find_header(lines: List[str]) -> Tuple[Optional[int], bool]:
    """Return (index of quantity header line, whether the price column precedes quantity)."""
    for i, line in enumerate(lines):
        if QTY_HEADER.match(line):
            window = range(max(0, i - 10), min(len(lines), i + 10))
            price_idx = next((j for j in window if len(lines[j]) <= 10 and PRICE_HEADER.search(lines[j])), None)
            return i, price_idx is not None and price_idx < i
    return None, False


def _split_qty_price(a: _Num, b: _Num, price_first: bool) -> Tuple[_Num, _Num]:
    if a.unit and not b.unit:
        return a, b
    if b.unit and not a.unit:
        return b, a
    return (b, a) if price_first else (a, b)


def parse_line_items(text: str) -> List[OrderItemLine]:
    """Recover order line items from OCR text without relying on document-specific keywords."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    start, price_first = _find_header(lines)
    if start is None:
        return []

    body = lines[start + 1:]
    items: List[OrderItemLine] = []
    buf: List[object] = []  # str for text cells, _Num for numeric cells

    for idx, line in enumerate(body):
        if items and TABLE_END.search(line):
            break
        num = _parse_num(line)
        if num is None:
            buf.append(line)
            continue

        # A row number followed by a text cell opens a new row; drop leftovers such as remark cells.
        next_is_text = idx + 1 < len(body) and _parse_num(body[idx + 1]) is None
        if num.value == len(items) + 1 and not num.unit and "." not in num.raw and next_is_text:
            buf = []
            continue

        prev_nums = [t for t in buf if isinstance(t, _Num)][-3:]
        match = None
        if num.money_like and num.value > 0:
            for i in range(len(prev_nums) - 1, 0, -1):
                for j in range(i - 1, -1, -1):
                    a, b = prev_nums[j], prev_nums[i]
                    if a.value > 0 and b.value > 0 and abs(a.value * b.value - num.value) <= max(0.011, num.value * 0.001):
                        match = (a, b)
                        break
                if match:
                    break

        if not match:
            buf.append(num)
            continue

        qty, price = _split_qty_price(*match, price_first)
        texts = [t for t in buf if isinstance(t, str)]
        if not items:
            # The first row's buffer still holds the header cells (and possibly text before them)
            is_header = [not re.search(r"\d", t) and len(t) <= 8 and bool(HEADER_WORD.search(t)) for t in texts]
            if any(is_header):
                last = len(is_header) - 1 - is_header[::-1].index(True)
                texts = texts[last + 1:]
        unit = qty.unit or next((t for t in texts if t.lower() in UNITS), None)
        descr = [t for t in texts if t.lower() not in UNITS]

        items.append(OrderItemLine(
            line_no=len(items) + 1,
            item_name=descr[0] if descr else "未识别品名",
            spec_model=descr[1] if len(descr) > 1 else None,
            quantity=qty.value,
            unit=unit or "pcs",
            unit_price=price.value,
            subtotal=num.value,
        ))
        buf = []

    return items
