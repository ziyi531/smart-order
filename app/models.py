from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class BoxDimensions(BaseModel):
    length_mm: Optional[float] = Field(None, description="Carton outer/inner length in mm")
    width_mm: Optional[float] = Field(None, description="Carton width in mm")
    height_mm: Optional[float] = Field(None, description="Carton height in mm")
    dimension_type: Optional[str] = Field(None, description="Dimension type as written: Outer / Inner / Manufacturing")

    @property
    def display_dimension(self) -> Optional[str]:
        if self.length_mm and self.width_mm and self.height_mm:
            dims = f"{self.length_mm:g} × {self.width_mm:g} × {self.height_mm:g} mm"
            return f"{dims} ({self.dimension_type})" if self.dimension_type else dims
        return None

class MaterialSpecification(BaseModel):
    paper_combination: Optional[str] = Field(None, description="Linerboard paper combination, e.g., K=A, A=B, B3B, W=K")
    flute_type: Optional[str] = Field(None, description="Flute profile: Single Wall (B/E), Double Wall (AB/BC), Triple (AAA)")
    board_quality: Optional[str] = Field(None, description="Grammage and board grade details")

class CartonSpecification(BaseModel):
    box_type: Optional[str] = Field(None, description="FEFCO international box code or type")
    dimensions: BoxDimensions = Field(default_factory=BoxDimensions)
    joint_type: Optional[str] = Field(None, description="Joint style: Stitched (Staples) / Glued (Adhesive)")
    printing_process: Optional[str] = Field(None, description="Printing: Flexo 2-color / Offset / Unprinted / Hot Stamping")
    die_cut_code: Optional[str] = Field(None, description="Die-cutter tooling code or engineering drawing reference")

class OrderHeader(BaseModel):
    order_no: Optional[str] = Field(None, description="Customer Purchase Order No. or Factory Job No.")
    customer_name: Optional[str] = Field(None, description="Customer legal entity name")
    contact_person: Optional[str] = Field(None, description="Procurement contact person")
    contact_phone: Optional[str] = Field(None, description="Contact phone or mobile number")
    delivery_date: Optional[str] = Field(None, description="Committed delivery date (YYYY-MM-DD)")
    delivery_address: Optional[str] = Field(None, description="Ship-to factory/warehouse address")

class OrderItemLine(BaseModel):
    line_no: int = Field(1, description="Item sequence number")
    item_name: str = Field("Packaging Product / Item", description="Product description or item name")
    spec_model: Optional[str] = Field(None, description="Specification or model code")
    quantity: float = Field(0.0, description="Quantity")
    unit: str = Field("pcs", description="Unit of measure: pcs, sets, boxes, packs")
    unit_price: float = Field(0.0, description="Unit price per item")
    subtotal: float = Field(0.0, description="Line subtotal amount")

class CommercialDetail(BaseModel):
    items: List[OrderItemLine] = Field(default_factory=list, description="Individual line items and price breakdown")
    quantity: Optional[int] = Field(0, description="Total order volume/quantity")
    unit: str = Field("pcs", description="Primary unit: pcs / sets / units")
    unit_price: Optional[float] = Field(None, description="Primary or weighted unit price")
    currency: Optional[str] = Field(None, description="Currency: CNY, USD, EUR, etc.; None when the document does not show one")
    total_amount: Optional[float] = Field(None, description="Grand total amount")
    chinese_uppercase_amount: Optional[str] = Field(None, description="Legal uppercase amount for audit verification")
    cross_check_verified: bool = Field(False, description="Whether dual-channel cross-validation passed")
    healing_note: Optional[str] = Field(None, description="Audit log of automated self-healing & corrections")

class PackagingOrderSchema(BaseModel):
    header: OrderHeader = Field(default_factory=OrderHeader)
    carton: CartonSpecification = Field(default_factory=CartonSpecification)
    material: MaterialSpecification = Field(default_factory=MaterialSpecification)
    commercial: CommercialDetail = Field(default_factory=CommercialDetail)
    special_requirements: List[str] = Field(default_factory=list, description="Special instructions: Palletization, burst strength, SGS certs")

class LatencyMetrics(BaseModel):
    ocr_time_ms: float = Field(0.0, description="OCR recognition latency (ms)")
    llm_time_ms: float = Field(0.0, description="LLM structuring latency (ms)")
    total_time_ms: float = Field(0.0, description="Total end-to-end latency (ms)")
    model_name: str = Field("qwen2.5:7b", description="Model engine employed")
    is_mock: bool = Field(False, description="Whether running in heuristic fallback mode")

class ExtractionResponse(BaseModel):
    success: bool = True
    order_data: PackagingOrderSchema
    raw_ocr_text: str = Field("", description="Raw unstructured OCR text stream")
    completeness_score: float = Field(..., description="Share of key order fields that were filled (0-1); not a correctness measure")
    warning_flags: List[str] = Field(default_factory=list, description="Business rule & validation warnings")
    metrics: LatencyMetrics

class ERPPushRequest(BaseModel):
    order_data: PackagingOrderSchema
    target_erp: str = Field("SAP_S4HANA", description="Target ERP id from config/erp_targets.json")
    operator: str = Field("AI_Auto_Ingestion_Agent", description="Operator identity")

class ERPPushResponse(BaseModel):
    success: bool
    simulated: bool = Field(..., description="True when no real ERP was contacted")
    erp_bill_no: str
    target_erp: str
    message: str
    pushed_at: str
