import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import (
    APP_NAME,
    VERSION,
    TARGET_ENTERPRISE,
    SAMPLES_DIR,
    UPLOADS_DIR,
    DEFAULT_MODEL,
    SAMPLES,
    ERP_TARGETS
)
from app.erp import get_erp_adapter
from app.hardware import detect_gpu
from app.models import (
    ExtractionResponse,
    PackagingOrderSchema,
    ERPPushRequest,
    ERPPushResponse,
    LatencyMetrics
)
from app.ocr_engine import ocr_engine
from app.llm_extractor import llm_extractor, compute_completeness

app = FastAPI(
    title=APP_NAME,
    version=VERSION,
    description=f"针对 {TARGET_ENTERPRISE} 智能制造场景定制的单据自动化结构化提取服务"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static mounts for sample images & uploaded docs
app.mount("/static/samples", StaticFiles(directory=str(SAMPLES_DIR)), name="samples")
app.mount("/static/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

@app.get("/")
def read_root():
    return {
        "service": APP_NAME,
        "version": VERSION,
        "target_client": TARGET_ENTERPRISE,
        "docs_url": "/docs",
        "health_check": "/api/health"
    }

@app.get("/api/health")
def health_check():
    ollama_info = llm_extractor.check_ollama_status()
    return {
        "status": "healthy",
        "ocr_backend": ocr_engine.backend_name,
        "gpu": detect_gpu(),
        "llm_service": ollama_info,
        "default_model": DEFAULT_MODEL,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/samples")
def list_samples():
    samples = []
    metadata = {s["filename"]: s for s in SAMPLES}

    for p in SAMPLES_DIR.glob("*.png"):
        meta = metadata.get(p.name, {
            "title": p.name,
            "category": "通用单据",
            "desc": "包装订单单据样张"
        })
        samples.append({
            "filename": p.name,
            "url": f"/static/samples/{p.name}",
            "title": meta["title"],
            "category": meta["category"],
            "desc": meta["desc"]
        })
    return {"samples": samples}

@app.post("/api/extract", response_model=ExtractionResponse)
async def extract_order(
    file: Optional[UploadFile] = File(None),
    sample_filename: Optional[str] = Form(None),
    model_name: Optional[str] = Form(None)
):
    """
    Core extraction API:
    Accepts either an uploaded file (PNG/JPG/PDF) or a sample filename.
    Performs: OCR extraction -> Local LLM structured extraction -> Packaging validation.
    """
    target_path: Optional[Path] = None

    if sample_filename:
        target_path = SAMPLES_DIR / sample_filename
        if not target_path.exists():
            raise HTTPException(status_code=404, detail=f"Sample not found: {sample_filename}")
    elif file:
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in [".png", ".jpg", ".jpeg", ".bmp", ".pdf"]:
            raise HTTPException(status_code=400, detail="Unsupported file type. Use PNG, JPG, or PDF.")
        unique_name = f"{uuid.uuid4().hex[:10]}_{file.filename}"
        target_path = UPLOADS_DIR / unique_name
        with open(target_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    else:
        raise HTTPException(status_code=400, detail="Either 'file' or 'sample_filename' must be provided.")

    # 1. OCR Extraction
    try:
        raw_ocr_text, ocr_time = ocr_engine.extract_text(str(target_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR extraction failed: {str(e)}")

    # 2. LLM Extraction
    try:
        order_data, llm_metrics = llm_extractor.extract_structured_order(
            raw_ocr_text=raw_ocr_text,
            model_name=model_name
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM extraction failed: {str(e)}")

    # 3. Combine Metrics & Warnings
    total_time = round(ocr_time + llm_metrics.llm_time_ms, 2)
    metrics = LatencyMetrics(
        ocr_time_ms=round(ocr_time, 2),
        llm_time_ms=llm_metrics.llm_time_ms,
        total_time_ms=total_time,
        model_name=llm_metrics.model_name,
        is_mock=llm_metrics.is_mock
    )
    warnings = llm_extractor.generate_warning_flags(order_data)

    return ExtractionResponse(
        success=True,
        order_data=order_data,
        raw_ocr_text=raw_ocr_text,
        completeness_score=compute_completeness(order_data),
        warning_flags=warnings,
        metrics=metrics
    )

@app.post("/api/erp_export", response_model=ERPPushResponse)
def push_to_erp(request: ERPPushRequest):
    """
    Push a structured order to an ERP target from config/erp_targets.json.
    No real ERP connector exists yet: responses carry simulated=True.
    """
    try:
        adapter = get_erp_adapter(request.target_erp)
    except KeyError:
        valid = [t["id"] for t in ERP_TARGETS]
        raise HTTPException(status_code=400, detail=f"Unknown target_erp '{request.target_erp}'. Valid: {valid}")
    return adapter.push(request.order_data, request.operator)

@app.get("/api/erp_targets")
def list_erp_targets():
    return {"targets": ERP_TARGETS}
