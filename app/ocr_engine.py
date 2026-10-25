import time
import os
from pathlib import Path
from typing import Tuple, List, Dict, Any
from PIL import Image, ImageEnhance
import pymupdf as fitz

class OCREngine:
    """Production-grade Multi-backend OCR Engine with Industrial Image Preprocessing.
    Uses RapidOCR (PaddleOCR ONNX runtime) + Lanczos Super-resolution + Contrast Sharpening
    to resolve tiny fonts and digit confusion (such as 0 vs 3, 8 vs 3).
    """

    def __init__(self):
        self._active_backend = "none"
        self._ocr_instance = None
        self._init_backend()

    def _init_backend(self):
        # 1. Primary Engine: RapidOCR (Official ONNX runtime of PaddleOCR)
        try:
            from rapidocr_onnxruntime import RapidOCR
            self._ocr_instance = RapidOCR()
            self._active_backend = "RapidOCR (PaddleOCR ONNX)"
            print("[OCR] Successfully initialized RapidOCR (PaddleOCR ONNX)")
            return
        except Exception as e:
            print(f"[OCR] RapidOCR initialization error: {e}")

        # 2. Try EasyOCR
        try:
            import easyocr
            self._ocr_instance = easyocr.Reader(['ch_sim', 'en'], gpu=False)
            self._active_backend = "EasyOCR"
            return
        except Exception:
            pass

        # 3. Fallback
        self._active_backend = "builtin_mock"

    @property
    def backend_name(self) -> str:
        return self._active_backend

    def is_real_ocr(self) -> bool:
        return "RapidOCR" in self._active_backend or "EasyOCR" in self._active_backend

    def preprocess_image(self, img_path: Path) -> Path:
        """
        Industrial preprocessing pipeline:
        1. RGB normalization (resolves palette/alpha channel distortion)
        2. Dynamic 2x/1.5x Lanczos Super-resolution (clarifies needle-printer & tiny font numbers)
        3. Contrast stretching (1.35x) to separate strokes from paper texture
        4. Edge sharpening (1.8x) to ensure closed digit loops (0, 8) do not break into open curves (3)
        """
        try:
            pil_img = Image.open(img_path).convert("RGB")
            w, h = pil_img.size

            # Apply super-resolution if resolution is low or medium
            scale = 1.0
            if max(w, h) < 1200:
                scale = 2.0
            elif max(w, h) < 2200:
                scale = 1.5

            if scale > 1.0:
                new_w = int(w * scale)
                new_h = int(h * scale)
                pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # Contrast enhancement
            enh = ImageEnhance.Contrast(pil_img).enhance(1.35)
            # Edge sharpness enhancement
            enh = ImageEnhance.Sharpness(enh).enhance(1.8)

            preprocessed_path = img_path.parent / f"_proc_{img_path.name}.png"
            enh.save(preprocessed_path, format="PNG")
            return preprocessed_path
        except Exception as e:
            print(f"[OCR] Preprocessing error, using raw image: {e}")
            return img_path

    def extract_from_pdf(self, pdf_path: str) -> Tuple[str, float]:
        """Extract text from PDF using PyMuPDF."""
        start = time.time()
        doc = fitz.open(pdf_path)
        full_text = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            if text.strip():
                full_text.append(f"--- [Page {page_num + 1}] ---\n" + text.strip())
        doc.close()
        elapsed = (time.time() - start) * 1000.0
        return "\n\n".join(full_text), elapsed

    def extract_text(self, file_path: str) -> Tuple[str, float]:
        """Runs REAL OCR with Super-Resolution Preprocessing."""
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # PDF native text extraction
        if p.suffix.lower() == ".pdf":
            text, latency = self.extract_from_pdf(str(p))
            if text.strip():
                return text, latency

        start = time.time()

        # Apply image preprocessing
        proc_path = self.preprocess_image(p)
        target_path = proc_path if proc_path.exists() else p

        # 1. Real OCR via RapidOCR (PaddleOCR ONNX)
        if "RapidOCR" in self._active_backend and self._ocr_instance:
            try:
                result, elapse_list = self._ocr_instance(str(target_path))
                elapsed = sum(elapse_list) * 1000.0 if elapse_list else (time.time() - start) * 1000.0
                # Clean up temporary preprocessed file
                if proc_path != p and proc_path.exists():
                    try:
                        proc_path.unlink()
                    except Exception:
                        pass

                if result:
                    lines = [item[1].strip() for item in result if item and len(item) > 1 and item[1].strip()]
                    raw_text = "\n".join(lines)
                    return raw_text, round(elapsed, 2)
                else:
                    return "【OCR提示】图像中未检测到清晰文字，请检查图像清晰度或旋转角度。", round(elapsed, 2)
            except Exception as e:
                print(f"[OCR] RapidOCR execution error: {e}")

        # 2. EasyOCR
        if "EasyOCR" in self._active_backend and self._ocr_instance:
            try:
                results = self._ocr_instance.readtext(str(target_path), detail=0)
                elapsed = (time.time() - start) * 1000.0
                return "\n".join(results), round(elapsed, 2)
            except Exception as e:
                print(f"[OCR] EasyOCR execution error: {e}")

        elapsed = (time.time() - start) * 1000.0
        return f"【未安装OCR引擎】无法识别 {p.name}", elapsed

# Singleton instance
ocr_engine = OCREngine()
