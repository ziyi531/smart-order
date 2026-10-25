import json
import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
SAMPLES_DIR = DATA_DIR / "samples"
UPLOADS_DIR = DATA_DIR / "uploads"

# Ensure directories exist
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# LLM Inference Configuration
OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434/v1")
DEFAULT_MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60.0"))

# OCR Configuration
# Options: 'auto', 'mock', 'easyocr', 'paddleocr'
OCR_ENGINE = os.getenv("OCR_ENGINE", "auto")

# App Metadata
APP_NAME = "SmartOrder (智单) - 包装单据智能结构化系统"
VERSION = "1.0.0"
TARGET_ENTERPRISE = "K.P.P. Packaging Co., Ltd."

# Editable business configuration (config/*.json, config/system_prompt.txt)
def _load_json(name: str):
    return json.loads((CONFIG_DIR / name).read_text(encoding="utf-8"))

SAMPLES = _load_json("samples.json")
ERP_TARGETS = _load_json("erp_targets.json")
PACKAGING_TERMS = _load_json("packaging_terms.json")
SYSTEM_PROMPT = (CONFIG_DIR / "system_prompt.txt").read_text(encoding="utf-8")
