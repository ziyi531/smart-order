import re
from typing import Tuple, Optional, List

CN_DIGITS = {
    '零': 0, '壹': 1, '贰': 2, '叁': 3, '肆': 4, '伍': 5,
    '陆': 6, '柒': 7, '捌': 8, '玖': 9,
    '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5,
    '6': 6, '7': 7, '8': 8, '9': 9,
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9
}

def parse_section(sec: str) -> int:
    """Parse a section within 10,000 (e.g. 壹仟伍佰柒拾肆 -> 1574)."""
    val = 0
    digit = 0
    for ch in sec:
        if ch in CN_DIGITS:
            digit = CN_DIGITS[ch]
        elif ch in ('拾', '十'):
            val += (digit if digit != 0 else 1) * 10
            digit = 0
        elif ch in ('佰', '百'):
            val += digit * 100
            digit = 0
        elif ch in ('仟', '千'):
            val += digit * 1000
            digit = 0
    val += digit
    return val

def cn_currency_to_float(s: str) -> Optional[float]:
    """Convert Chinese financial uppercase currency to float.
    Supports: 壹仟伍佰柒拾肆元整 -> 1574.0, 贰万叁仟元 -> 23000.0, etc.
    """
    if not s:
        return None
    s = s.replace('元', '圆').replace('正', '整')
    m = re.search(r'([零壹贰叁肆伍陆柒捌玖一二三四五六七八九拾十佰百仟千万亿圆角分整]+)', s)
    if not m:
        return None
    content = m.group(1).rstrip('整')
    if not content:
        return None

    jiao_val = 0.0
    fen_val = 0.0

    # Extract 角 and 分
    if '角' in content:
        parts = content.split('角')
        pre_jiao = parts[0]
        post_jiao = parts[1] if len(parts) > 1 else ''
        if pre_jiao and pre_jiao[-1] in CN_DIGITS:
            jiao_val = CN_DIGITS[pre_jiao[-1]] * 0.1
            content = pre_jiao[:-1]
        if '分' in post_jiao:
            fen_part = post_jiao.split('分')[0]
            if fen_part and fen_part[-1] in CN_DIGITS:
                fen_val = CN_DIGITS[fen_part[-1]] * 0.01
    elif '分' in content:
        parts = content.split('分')
        pre_fen = parts[0]
        if pre_fen and pre_fen[-1] in CN_DIGITS:
            fen_val = CN_DIGITS[pre_fen[-1]] * 0.01
            content = pre_fen[:-1]

    content = content.rstrip('圆')

    total = 0
    if '亿' in content:
        parts = content.split('亿')
        total += parse_section(parts[0]) * 100000000
        content = parts[1] if len(parts) > 1 else ''
    if '万' in content:
        parts = content.split('万')
        total += parse_section(parts[0]) * 10000
        content = parts[1] if len(parts) > 1 else ''

    total += parse_section(content)
    result = round(float(total) + jiao_val + fen_val, 2)
    return result if result > 0 else None

def extract_uppercase_string(full_text: str) -> Optional[str]:
    """Find the Chinese uppercase amount line or snippet in OCR text."""
    patterns = [
        r"(?:合计（大写）|合计\(大写\)|金额（大写）|金额\(大写\)|大写金额|大写)[:：\s]*([零壹贰叁肆伍陆柒捌玖拾佰仟万亿圆元角分整正\s]+)",
        r"([零壹贰叁肆伍陆柒捌玖][拾佰仟万亿零壹贰叁肆伍陆柒捌玖]+[圆元][整正]?)",
        r"([零壹贰叁肆伍陆柒捌玖拾佰仟万]+元[整正]?)"
    ]
    for p in patterns:
        m = re.search(p, full_text)
        if m:
            clean = m.group(1).strip().replace(" ", "")
            if len(clean) >= 3:
                return clean
    return None

def cross_validate_and_heal_amount(
    raw_arabic_amount: Optional[float],
    full_text: str
) -> Tuple[Optional[float], Optional[str], bool, Optional[str]]:
    """
    Financial-grade cross validation:
    Checks Arabic numeral against Chinese uppercase amount and heals missing decimal points.
    
    Returns:
        (healed_amount, uppercase_str, is_verified, healing_note)
    """
    uppercase_str = extract_uppercase_string(full_text)
    cn_amount = cn_currency_to_float(uppercase_str) if uppercase_str else None

    # Case 1: Both exist
    if cn_amount and raw_arabic_amount is not None:
        # Exact match
        if abs(raw_arabic_amount - cn_amount) < 0.001:
            return raw_arabic_amount, uppercase_str, True, "大写与小写金额完全吻合，双向确认通过。"

        # 100x missing decimal point defect (e.g. 157400 vs 1574.00)
        ratio = raw_arabic_amount / cn_amount if cn_amount > 0 else 0
        if 99.9 < ratio < 100.1:
            healed = round(raw_arabic_amount / 100.0, 2)
            note = (
                f"🛡️ [OCR自愈成功] 检测到小写金额 '{raw_arabic_amount:g}' 缺失小数点（OCR漏识点号），"
                f"已依据大写金额 '{uppercase_str}' 自动二次对齐纠正为 ¥{healed:,.2f}。"
            )
            return healed, uppercase_str, True, note

        # 10x missing decimal point defect
        if 9.9 < ratio < 10.1:
            healed = round(raw_arabic_amount / 10.0, 2)
            note = (
                f"🛡️ [OCR自愈成功] 检测到小写金额 '{raw_arabic_amount:g}' 小数位缺失，"
                f"已依据大写金额 '{uppercase_str}' 自动修正为 ¥{healed:,.2f}。"
            )
            return healed, uppercase_str, True, note

        # Discrepancy: trust Chinese uppercase amount in Chinese business practice,
        # but the two channels did not agree, so this is not a verified amount
        note = (
            f"⚠️ [金额存在分歧] 小写识别为 ¥{raw_arabic_amount:,.2f}，大写为 '{uppercase_str}' (¥{cn_amount:,.2f})。"
            f"依据财务法规暂以法定大写金额为准，请人工核对。"
        )
        return cn_amount, uppercase_str, False, note

    # Case 2: Only uppercase exists
    if cn_amount and (raw_arabic_amount is None or raw_arabic_amount == 0):
        note = f"🛡️ 小写金额模糊或未识别，已从大写金额 '{uppercase_str}' 逆向还原为 ¥{cn_amount:,.2f}。"
        return cn_amount, uppercase_str, True, note

    # Case 3: Only lowercase exists
    return raw_arabic_amount, None, False, None

def verify_and_heal_line_item(
    quantity: Optional[int],
    unit_price: Optional[float],
    subtotal: Optional[float]
) -> Tuple[Optional[float], Optional[str]]:
    """
    Arithmetic column consistency check:
    Checks if Quantity * Unit Price equals Subtotal.
    A subtotal differing from the product in exactly one digit is treated as an OCR
    misread (0 vs 3, 8 vs 0, ...) and corrected; any other mismatch is flagged, not changed.
    """
    if quantity and unit_price and quantity > 0 and unit_price > 0:
        expected = round(quantity * unit_price, 2)
        if subtotal is not None and subtotal != 0 and abs(expected - subtotal) > 0.001:
            if _differs_by_one_digit(expected, subtotal):
                note = (
                    f"🛡️ [算术一致性纠偏] OCR小计识别为 ¥{subtotal:,.2f}，与 单价(¥{unit_price:,.2f}) × 数量({quantity:g}) "
                    f"仅差一位数字，判定为OCR误识，已纠正为 ¥{expected:,.2f}。"
                )
                return expected, note
            note = (
                f"⚠️ [算术不一致] 小计 ¥{subtotal:,.2f} ≠ 单价(¥{unit_price:,.2f}) × 数量({quantity:g}) = ¥{expected:,.2f}，"
                f"差异超出单字误识范围，未自动修改，请人工核对。"
            )
            return subtotal, note
        elif subtotal is None or subtotal == 0:
            return expected, None
    return subtotal, None


def _differs_by_one_digit(a: float, b: float) -> bool:
    """True when both amounts have the same digit layout and differ in exactly one digit."""
    sa, sb = f"{a:.2f}", f"{b:.2f}"
    return len(sa) == len(sb) and sum(x != y for x, y in zip(sa, sb)) == 1
