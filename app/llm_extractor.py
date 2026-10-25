import json
import re
import time
from datetime import date
from typing import Tuple, Dict, Any, Optional
import httpx

from app.config import OLLAMA_API_BASE, DEFAULT_MODEL, LLM_TIMEOUT, PACKAGING_TERMS, SYSTEM_PROMPT
from app.currency_cross_check import cross_validate_and_heal_amount, verify_and_heal_line_item
from app.line_items import parse_line_items
from app.models import (
    PackagingOrderSchema,
    BoxDimensions,
    MaterialSpecification,
    CartonSpecification,
    OrderHeader,
    CommercialDetail,
    ExtractionResponse,
    LatencyMetrics
)

def _drop_nulls(d: Any, keys) -> None:
    if isinstance(d, dict):
        for k in keys:
            if k in d and d[k] is None:
                del d[k]


def _drop_nulls_for_required(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """The prompt asks for null when a value is absent; for fields that cannot be None,
    remove the null so the schema default applies instead of failing validation."""
    _drop_nulls(parsed, ["header", "carton", "material", "commercial", "special_requirements"])
    _drop_nulls(parsed.get("carton"), ["dimensions"])
    commercial = parsed.get("commercial")
    _drop_nulls(commercial, ["items", "unit"])
    if isinstance(commercial, dict):
        commercial["items"] = [
            {k: v for k, v in it.items() if v is not None}
            for it in commercial.get("items", []) if isinstance(it, dict)
        ]
    return parsed


PLACEHOLDER_VALUES = {"无", "n/a", "na", "none", "null", "未知", "不详", "-", "--", "/"}


def _clean_placeholders(value: Any) -> Any:
    """Recursively turn placeholder strings the LLM uses for 'absent' (无, N/A, XXX...) into None."""
    if isinstance(value, dict):
        return {k: _clean_placeholders(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean_placeholders(v) for v in value]
    if isinstance(value, str):
        s = value.strip()
        if not s or s.lower() in PLACEHOLDER_VALUES or re.match(r"^[Xx×]{3,}", s):
            return None
        return s
    return value


def _normalize_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    m = re.search(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})", value)
    if not m:
        return None
    y, mo, d = (int(g) for g in m.groups())
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def _validate_header(order: PackagingOrderSchema) -> None:
    """Format checks that reject table labels and template placeholders taken as values."""
    h = order.header
    h.delivery_date = _normalize_date(h.delivery_date)
    if h.contact_phone:
        digits = re.sub(r"\D", "", h.contact_phone)
        if len(digits) < 7 or len(set(digits)) == 1:
            h.contact_phone = None
    if h.order_no and not re.search(r"[1-9]", h.order_no):
        h.order_no = None


def _detect_currency(text: str) -> Optional[str]:
    if re.search(r"USD|US\$|\$", text):
        return "USD"
    if re.search(r"EUR|€", text):
        return "EUR"
    if re.search(r"[¥￥元]|CNY|RMB|人民币", text):
        return "CNY"
    return None


KEY_FIELDS = 8


def compute_completeness(order: PackagingOrderSchema) -> float:
    """Share of key order fields that were filled. Measures coverage, not correctness."""
    d = order.carton.dimensions
    c = order.commercial
    filled = [
        bool(order.header.customer_name),
        bool(order.header.order_no),
        bool(order.header.delivery_date),
        bool(c.items) or bool(c.quantity),
        c.total_amount is not None,
        bool(d.length_mm and d.width_mm and d.height_mm),
        bool(order.carton.box_type),
        bool(order.material.flute_type),
    ]
    return round(sum(filled) / KEY_FIELDS, 3)


class LLMExtractor:
    def __init__(self, api_base: str = OLLAMA_API_BASE, default_model: str = DEFAULT_MODEL):
        self.api_base = api_base.rstrip("/")
        self.default_model = default_model

    def check_ollama_status(self) -> Dict[str, Any]:
        """Check if local Ollama service is reachable and list models."""
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(f"{self.api_base}/models")
                if res.status_code == 200:
                    data = res.json()
                    models = [m.get("id") or m.get("name") for m in data.get("data", [])]
                    return {"available": True, "models": models, "url": self.api_base}
        except Exception:
            pass
        return {"available": False, "models": [], "url": self.api_base}

    def loaded_models(self) -> list[Dict[str, Any]]:
        """Models currently held in memory by Ollama, with their VRAM use (native /api/ps endpoint)."""
        root = re.sub(r"/v1$", "", self.api_base)
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(f"{root}/api/ps")
            if res.status_code == 200:
                return [
                    {
                        "name": m.get("name"),
                        "size_vram": m.get("size_vram", 0),
                        "quantization": (m.get("details") or {}).get("quantization_level"),
                    }
                    for m in res.json().get("models", [])
                ]
        except Exception:
            pass
        return []

    def _fallback_rule_extractor(self, text: str) -> PackagingOrderSchema:
        """Generalized heuristic packaging document parser based strictly on real OCR text."""
        order = PackagingOrderSchema()

        # 1. Customer Name
        m_cust = re.search(r"(?:客户名称|买方客户|订货单位|需方|购买方|收货单位|客户)[:：\s]+([^\n\r]+)", text)
        if m_cust:
            order.header.customer_name = m_cust.group(1).strip()
        else:
            for line in text.split("\n"):
                line = line.strip()
                if any(k in line for k in ["有限公司", "有限责任公司", "科技", "电子", "包装", "供应链"]):
                    clean = re.sub(r"^(?:客户|买方|需方|单位|送达)[:：\s]*", "", line)
                    if len(clean) >= 4 and len(clean) <= 30:
                        order.header.customer_name = clean
                        break

        # 2. Order No
        m_no = re.search(r"(?:采购单号|采购编号|销售单号|工单编号|订单编号|单号|合同号|PO|[Nn][eo]\.?|NO\.?|No\.?)[:：\s]*([A-Za-z0-9\-_]{4,})", text)
        if m_no:
            order.header.order_no = m_no.group(1).strip()

        # 3. Delivery Date
        m_date = re.search(r"(?:交货日期|交割日期|承诺交期|交期|交货期)[:：\s]*([0-9]{4}[-/年][0-9]{1,2}[-/月][0-9]{1,2}日?)", text)
        if not m_date:
            m_date = re.search(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})", text)
        if m_date:
            order.header.delivery_date = re.sub(r"[年月]", "-", m_date.group(1).rstrip("日"))

        # 4. Contact & Phone
        m_phone = re.search(r"(?:联系人|联系人员|业务代表|联 系 人)[:：\s]+([^\n\r\(\)]+)(?:\(([^)]+)\)|（([^）]+)）)?", text)
        if m_phone:
            order.header.contact_person = m_phone.group(1).strip()
            phone = m_phone.group(2) or m_phone.group(3)
            if phone:
                order.header.contact_phone = phone.strip()
        else:
            m_raw_phone = re.search(r"(1[3-9]\d{9}|0\d{2,3}-?\d{7,8})", text)
            if m_raw_phone:
                order.header.contact_phone = m_raw_phone.group(1)

        # 5. Delivery Address
        m_addr = re.search(r"(?:送货地址|送达车间|收货地址|地址)[:：\s]+([^\n\r]+)", text)
        if m_addr:
            order.header.delivery_address = m_addr.group(1).strip()

        # 6. Dimensions: e.g. 530 × 380 × 420 or 530*380*420 or 530x380x420
        m_dim = re.search(r"(\d+(?:\.\d+)?)\s*[×\*xX*]\s*(\d+(?:\.\d+)?)\s*[×\*xX*]\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米|CM|cm)?(?:\s*[\(（]([^）\)]+)[\)）])?", text)
        if m_dim:
            order.carton.dimensions.length_mm = float(m_dim.group(1))
            order.carton.dimensions.width_mm = float(m_dim.group(2))
            order.carton.dimensions.height_mm = float(m_dim.group(3))
            if m_dim.group(4):
                order.carton.dimensions.dimension_type = m_dim.group(4).strip()

        # 7. Box Type
        m_box = re.search(r"(?:【箱型结构】|【盒型分类】|【箱型款式】|箱型|盒型)[:：\s]+([^\n\r]+)", text)
        if m_box:
            order.carton.box_type = m_box.group(1).strip()
        else:
            for keyword, box_type in PACKAGING_TERMS["box_type_keywords"]:
                if keyword in text:
                    order.carton.box_type = box_type
                    break

        # 8. Material & Flute
        m_mat = re.search(r"(?:【瓦楞材质】|【材质楞型】|【芯板基材】|材质|材质说明)[:：\s]+([^\n\r]+)", text)
        if m_mat:
            mat_raw = m_mat.group(1).strip()
            for fl in PACKAGING_TERMS["flute_types"] + PACKAGING_TERMS["flute_layer_fallbacks"]:
                if fl in mat_raw or fl in text:
                    order.material.flute_type = fl
                    break
            m_comb = re.search(r"([KABWT9][=\-][KABWT9]|[A-Z]\d[A-Z])", mat_raw)
            if m_comb:
                order.material.paper_combination = m_comb.group(1)
            order.material.board_quality = mat_raw
        else:
            for fl in PACKAGING_TERMS["flute_types"]:
                if fl in text:
                    order.material.flute_type = fl
                    break

        # 9. Joint / Craft
        m_joint = re.search(r"(?:【接缝工艺】|接头工艺|【成型方式】|接缝)[:：\s]+([^\n\r]+)", text)
        if m_joint:
            order.carton.joint_type = m_joint.group(1).strip()

        # 10. Printing
        m_print = re.search(r"(?:印刷工艺|印刷颜色|印刷内容|印刷)[:：\s]+([^\n\r]+)", text)
        if m_print:
            order.carton.printing_process = m_print.group(1).strip()

        # 11. Die-cut code
        m_die = re.search(r"(?:刀模号|激光刀模号|图纸号)[:：\s]+([A-Za-z0-9\-_]+)", text)
        if m_die:
            order.carton.die_cut_code = m_die.group(1).strip()

        # 12. Line Items, Quantity & Commercial
        # Labels and values must share a line: OCR puts table cells on separate lines,
        # so matching across newlines pairs a header cell with an unrelated value.
        items = parse_line_items(text)
        order.commercial.items = items

        m_qty = re.search(r"(?:生产数量|交付数量|订购数量|订购套数|数量|件数|套数|总数)[:： \t]*([0-9,]+)[ \t]*([个套PCS支只]*)", text)
        if m_qty:
            order.commercial.quantity = int(m_qty.group(1).replace(",", ""))
            if m_qty.group(2):
                order.commercial.unit = m_qty.group(2).strip()

        m_price = re.search(r"(?:单价|含税单价)[^\d\n]*([0-9]+\.[0-9]{1,2})", text)
        if m_price:
            order.commercial.unit_price = float(m_price.group(1))

        m_total = re.search(r"(?:金额（小写）|金额\(小写\)|合计金额|总金额|价税合计|总计|合计|小写金额|小写)[:： \t]*[¥￥$]?[ \t]*([0-9,]+(?:\.[0-9]{1,2})?)", text)
        if m_total:
            order.commercial.total_amount = float(m_total.group(1).replace(",", ""))
        order.commercial.currency = _detect_currency(text)

        # 13. Special Requirements
        reqs = []
        for line in text.split("\n"):
            line = line.strip()
            if any(k in line for k in PACKAGING_TERMS["special_requirement_keywords"]):
                reqs.append(line)
        order.special_requirements = reqs[:5]
        return order

    def _validate_commercial(self, order: PackagingOrderSchema, text: str) -> None:
        """Arithmetic and uppercase-amount checks shared by the LLM and fallback paths."""
        c = order.commercial
        notes = []

        # Blank template rows carry neither a price nor an amount
        c.items = [it for it in c.items if it.unit_price > 0 or it.subtotal > 0]

        # Per-line consistency: quantity * unit price == subtotal
        for item in c.items:
            healed, note = verify_and_heal_line_item(item.quantity, item.unit_price, item.subtotal)
            if healed is not None:
                item.subtotal = healed
            if note:
                notes.append(f"第{item.line_no}行 {note}")

        if c.items:
            # Order totals derive from the lines; quantities in different units cannot be summed
            units = {it.unit for it in c.items}
            if len(units) == 1:
                c.quantity = int(round(sum(it.quantity for it in c.items)))
                c.unit = units.pop()
            else:
                c.quantity = None
            if len(c.items) == 1 and c.unit_price is None:
                c.unit_price = c.items[0].unit_price

            lines_consistent = all(
                it.quantity > 0 and abs(it.quantity * it.unit_price - it.subtotal) <= 0.011
                for it in c.items
            )
            if c.total_amount is None and lines_consistent:
                c.total_amount = round(sum(it.subtotal for it in c.items), 2)

        # Order-level consistency only applies to single-product orders
        if len(c.items) <= 1:
            healed, note = verify_and_heal_line_item(c.quantity, c.unit_price, c.total_amount)
            if healed is not None:
                c.total_amount = healed
            if note:
                notes.append(note)

        # Financial cross-validation against the Chinese uppercase amount
        healed_amt, upper_str, is_verified, healing_note = cross_validate_and_heal_amount(c.total_amount, text)
        c.total_amount = healed_amt
        c.chinese_uppercase_amount = upper_str
        c.cross_check_verified = is_verified
        if healing_note:
            notes.append(healing_note)
        c.healing_note = "\n".join(notes) or None

    def extract_structured_order(
        self,
        raw_ocr_text: str,
        model_name: Optional[str] = None,
        use_llm: bool = True
    ) -> Tuple[PackagingOrderSchema, LatencyMetrics]:
        """Extract structured packaging order data using Local LLM or Smart Heuristic Fallback."""
        selected_model = model_name or self.default_model
        start_time = time.time()
        is_mock = False

        # 1. Attempt to invoke local Ollama if online
        if use_llm and self.check_ollama_status()["available"]:
            try:
                payload = {
                    "model": selected_model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"请对以下印刷包装订单OCR文本执行精准结构化提取：\n\n{raw_ocr_text}"}
                    ],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"}
                }
                with httpx.Client(timeout=LLM_TIMEOUT) as client:
                    res = client.post(f"{self.api_base}/chat/completions", json=payload)
                if res.status_code == 200:
                    content = res.json()["choices"][0]["message"]["content"]
                    # Clean markdown fence if present
                    clean_json = re.sub(r"^```json\s*", "", content.strip())
                    clean_json = re.sub(r"\s*```$", "", clean_json.strip())
                    parsed = _drop_nulls_for_required(_clean_placeholders(json.loads(clean_json)))
                    order_data = PackagingOrderSchema.model_validate(parsed)
                    _validate_header(order_data)
                    self._validate_commercial(order_data, raw_ocr_text)
                    elapsed = (time.time() - start_time) * 1000.0
                    return order_data, LatencyMetrics(
                        ocr_time_ms=0.0,
                        llm_time_ms=round(elapsed, 2),
                        total_time_ms=round(elapsed, 2),
                        model_name=selected_model,
                        is_mock=False
                    )
            except Exception as e:
                print(f"[LLM] {selected_model} extraction failed, using rule engine: {e}")
                is_mock = True
        else:
            is_mock = True

        # Fallback path
        order_data = self._fallback_rule_extractor(raw_ocr_text)
        _validate_header(order_data)
        self._validate_commercial(order_data, raw_ocr_text)
        elapsed = (time.time() - start_time) * 1000.0
        return order_data, LatencyMetrics(
            ocr_time_ms=0.0,
            llm_time_ms=round(elapsed, 2),
            total_time_ms=round(elapsed, 2),
            model_name=f"{selected_model} (内置自适应规则引擎)",
            is_mock=is_mock
        )

    def generate_warning_flags(self, order: PackagingOrderSchema) -> list[str]:
        """Packaging business validation flags."""
        warnings = []
        if not order.carton.dimensions.length_mm or not order.carton.dimensions.width_mm or not order.carton.dimensions.height_mm:
            warnings.append("⚠️ 纸箱三维尺寸未完整识别，请人工确认纸箱规格。")
        if not order.carton.box_type:
            warnings.append("⚠️ 箱型未识别，请人工确认箱型代号。")
        if not order.material.flute_type:
            warnings.append("⚠️ 瓦楞楞型（如五层AB瓦/三层B瓦）未明确，影响瓦线排产。")
        has_item_qty = any(it.quantity > 0 for it in order.commercial.items)
        if (not order.commercial.quantity or order.commercial.quantity <= 0) and not has_item_qty:
            warnings.append("⚠️ 订单订购数量异常或为0。")
        if not order.header.delivery_date:
            warnings.append("⚠️ 订单未标注承诺交货期，无法安排车间排程。")
        return warnings

# Singleton instance
llm_extractor = LLMExtractor()
