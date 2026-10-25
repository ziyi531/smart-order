"""Field-level accuracy of the extraction pipeline against hand-labelled documents.

Usage (from the project root):
    python eval/evaluate.py                  # rule engine and LLM (if Ollama is reachable)
    python eval/evaluate.py --mode rule
    python eval/evaluate.py --no-cache -v    # re-run OCR, list every mismatch

Labels live in eval/labels/*.json and were transcribed from the images, not from OCR output,
so OCR errors count against the pipeline. A list value means any of the listed answers is
accepted; null means nothing should be extracted (hallucinated values count as wrong).
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.llm_extractor import llm_extractor  # noqa: E402

LABELS_DIR = ROOT / "eval" / "labels"
OCR_CACHE = ROOT / "eval" / ".ocr_cache.json"

NUMERIC_SUFFIXES = ("_mm", "total_amount", "quantity", "unit_price", "subtotal")
CONTAINS_FIELDS = {"carton.box_type", "material.flute_type"}  # labels hold the key code, e.g. "0201"
PHONE_FIELDS = {"header.contact_phone"}


def _norm_text(v) -> str:
    s = str(v).lower()
    s = s.translate(str.maketrans("（）：，", "():,"))
    return re.sub(r"\s+", "", s)


def _matches(field: str, expected, got) -> bool:
    if isinstance(expected, list):
        return any(_matches(field, e, got) for e in expected)
    if expected is None:
        return got is None or got == "" or got == []
    if got is None or got == "":
        return False
    if field.endswith(NUMERIC_SUFFIXES):
        try:
            return abs(float(got) - float(expected)) <= 0.01
        except (TypeError, ValueError):
            return False
    if field in PHONE_FIELDS:
        return re.sub(r"\D", "", str(got)) == re.sub(r"\D", "", str(expected))
    if field in CONTAINS_FIELDS:
        return _norm_text(expected) in _norm_text(got)
    return _norm_text(got) == _norm_text(expected)


def _get(obj, path: str):
    for part in path.split("."):
        obj = obj.get(part) if isinstance(obj, dict) else None
    return obj


def score_document(label: dict, order: dict):
    """Return a list of (field, expected, got, ok)."""
    results = []
    for field, expected in label["fields"].items():
        got = _get(order, field)
        results.append((field, expected, got, _matches(field, expected, got)))

    expected_items = label.get("items")
    if expected_items is not None:
        got_items = order["commercial"]["items"]
        results.append(("items.count", len(expected_items), len(got_items), len(expected_items) == len(got_items)))
        for i, exp in enumerate(expected_items):
            got_item = got_items[i] if i < len(got_items) else {}
            for key, value in exp.items():
                got = got_item.get(key)
                results.append((f"items[{i}].{key}", value, got, _matches(key, value, got)))
    return results


def load_ocr_text(path: Path, cache: dict, use_cache: bool) -> str:
    stat = path.stat()
    key = f"{path.relative_to(ROOT).as_posix()}|{stat.st_size}|{int(stat.st_mtime)}"
    if use_cache and key in cache:
        return cache[key]
    from app.ocr_engine import ocr_engine
    text, _ = ocr_engine.extract_text(str(path))
    cache[key] = text
    return text


def _group(field: str) -> str:
    if field.startswith("items"):
        return "items"
    return field.split(".")[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["rule", "llm", "both"], default="both")
    parser.add_argument("--no-cache", action="store_true", help="re-run OCR instead of using eval/.ocr_cache.json")
    parser.add_argument("-v", "--verbose", action="store_true", help="print every mismatching field")
    args = parser.parse_args()

    modes = ["rule", "llm"] if args.mode == "both" else [args.mode]
    if "llm" in modes and not llm_extractor.check_ollama_status()["available"]:
        print("Ollama is not reachable; skipping LLM mode.")
        modes.remove("llm")

    labels = [json.loads(p.read_text(encoding="utf-8")) | {"_name": p.stem} for p in sorted(LABELS_DIR.glob("*.json"))]
    cache = json.loads(OCR_CACHE.read_text(encoding="utf-8")) if OCR_CACHE.exists() else {}
    texts = {lb["_name"]: load_ocr_text(ROOT / lb["file"], cache, not args.no_cache) for lb in labels}
    OCR_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    for mode in modes:
        print(f"\n===== mode: {mode} =====")
        by_group = defaultdict(lambda: [0, 0])
        total_ok = total = 0
        for lb in labels:
            order, metrics = llm_extractor.extract_structured_order(texts[lb["_name"]], use_llm=(mode == "llm"))
            if mode == "llm" and metrics.is_mock:
                print(f"  !! {lb['_name']}: LLM call failed, scored rule-engine output instead")
            results = score_document(lb, order.model_dump())
            ok = sum(r[3] for r in results)
            total_ok += ok
            total += len(results)
            print(f"  {lb['_name']:<28} {ok:>3}/{len(results):<3} {ok / len(results):6.1%}")
            for field, expected, got, good in results:
                by_group[_group(field)][0] += good
                by_group[_group(field)][1] += 1
                if args.verbose and not good:
                    print(f"      ✗ {field}: expected {expected!r}, got {got!r}")
        print(f"  {'-' * 46}")
        for group, (ok, n) in sorted(by_group.items()):
            print(f"  {group:<28} {ok:>3}/{n:<3} {ok / n:6.1%}")
        print(f"  {'OVERALL':<28} {total_ok:>3}/{total:<3} {total_ok / total:6.1%}")


if __name__ == "__main__":
    main()
