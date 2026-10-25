import streamlit as st
import os
import json
import uuid
from pathlib import Path
from PIL import Image
import pandas as pd
import httpx

from app.config import (
    APP_NAME,
    VERSION,
    TARGET_ENTERPRISE,
    SAMPLES_DIR,
    DEFAULT_MODEL,
    OLLAMA_API_BASE,
    SAMPLES,
    ERP_TARGETS
)
from app.erp import get_erp_adapter
from app.hardware import detect_gpu
from app.ocr_engine import ocr_engine
from app.llm_extractor import llm_extractor, compute_completeness

WS_DOCS = "📦 Document Structuring & ERP Hub"
WS_CHAT = "💬 Real-Time Chat with Local LLM"
CURRENCY_SYMBOLS = {"CNY": "¥", "USD": "$", "EUR": "€"}
NOT_DETECTED = '<span style="color: #94A3B8; font-weight: 500;">未识别 / Not detected</span>'


@st.cache_data(ttl=300)
def cached_gpu():
    return detect_gpu()


@st.cache_data(ttl=30)
def cached_loaded_models():
    return llm_extractor.loaded_models()

# Streamlit Page Configuration
st.set_page_config(
    page_title=f"SmartOrder AI - {TARGET_ENTERPRISE}",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Enterprise CSS Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.15rem;
        font-weight: 750;
        color: #0F172A;
        letter-spacing: -0.02em;
        margin-bottom: 0.15rem;
    }
    .sub-header {
        font-size: 1.0rem;
        color: #475569;
        margin-bottom: 1.4rem;
    }
    .badge-enterprise {
        background-color: #EFF6FF;
        color: #1D4ED8;
        padding: 5px 14px;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 600;
        border: 1px solid #BFDBFE;
    }
    .spec-card {
        background: linear-gradient(135deg, #F8FAFC 0%, #F1F5F9 100%);
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }
    .spec-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .spec-val {
        font-size: 1.25rem;
        font-weight: 700;
        margin-top: 4px;
    }
    .stMetric {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        padding: 10px 14px;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar: System Controls & Workspace Navigation
with st.sidebar:
    st.image("https://img.icons8.com/color/96/cardboard-box.png", width=60)
    st.title("SmartOrder AI")
    st.markdown(f"**Target Enterprise**: `{TARGET_ENTERPRISE}`")
    st.caption("Industrial OCR & Local LLM Edge Intelligence Platform")
    st.divider()

    st.subheader("🧭 Workspace Navigator")
    workspace_mode = st.radio(
        "Select Active Workspace",
        [WS_DOCS, WS_CHAT],
        index=0
    )

    st.divider()
    st.subheader("⚙️ Local AI Engine Setup")
    ollama_status = llm_extractor.check_ollama_status()
    gpu_name = cached_gpu()

    if ollama_status["available"]:
        st.success(f"🟢 Local Ollama Online\n\nHardware: {gpu_name or 'no NVIDIA GPU detected (CPU)'}")
        available_models = ollama_status.get("models", [])
        if DEFAULT_MODEL not in available_models and available_models:
            model_selected = st.selectbox("Inference Model", available_models, index=0)
        else:
            model_selected = st.selectbox("Inference Model", [DEFAULT_MODEL] + [m for m in available_models if m != DEFAULT_MODEL], index=0)
    else:
        st.info("ℹ️ Local LLM (Ollama) offline. Adaptive Domain Heuristic Engine active.")
        model_selected = DEFAULT_MODEL

    st.subheader("👁️ Vision & OCR Pipeline")
    if ocr_engine.is_real_ocr():
        st.success(f"🟢 {ocr_engine.backend_name}\n\n(Adaptive Lanczos upscaling, up to 2x)")
    else:
        st.warning(f"⚠️ {ocr_engine.backend_name}")

    st.divider()
    st.subheader("💡 Strategic Value for Packaging")
    with st.expander("Why Local LLM over Cloud APIs?"):
        st.write("""
        - **Commercial Secrecy**: Factory pricing formulas, customer drawings, and delivery sites never leave the corporate LAN.
        - **Zero Marginal Token Cost**: Inference runs on in-house hardware, with no per-token API fees.
        - **Network Resilience**: 100% operational even in factory sub-networks with restricted internet access.
        """)

# ==========================================
# WORKSPACE 1: DOCUMENT STRUCTURING & ERP
# ==========================================
if workspace_mode == WS_DOCS:
    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.markdown('<div class="main-header">📦 SmartOrder AI — Packaging Document Structuring Platform</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sub-header">Automated Ingestion · Packaging Engineering Domain Extraction · Enterprise ERP Sync · <b>{TARGET_ENTERPRISE}</b></div>', unsafe_allow_html=True)
    with col_h2:
        st.markdown('<div style="text-align: right; padding-top: 15px;"><span class="badge-enterprise">v{VERSION}</span></div>', unsafe_allow_html=True)

    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.subheader("1. Ingest Document")

        input_mode = st.radio(
            "Select Document Input Method",
            ["📋 Packaging Benchmark Samples", "📤 Upload Custom PO / Invoice (PNG/JPG/PDF)"],
            horizontal=True
        )

        selected_image_path = None

        if input_mode == "📋 Packaging Benchmark Samples":
            sample_options = {s["label_en"]: SAMPLES_DIR / s["filename"] for s in SAMPLES}
            chosen_sample_name = st.selectbox("Select Business Benchmark Scenario", list(sample_options.keys()))
            selected_image_path = sample_options[chosen_sample_name]
        else:
            uploaded_file = st.file_uploader("Upload Scanned Invoice, Photo, or Vector PDF", type=["png", "jpg", "jpeg", "pdf"])
            if uploaded_file:
                temp_path = SAMPLES_DIR.parent / "uploads" / uploaded_file.name
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                selected_image_path = temp_path

        if selected_image_path and os.path.exists(selected_image_path):
            if str(selected_image_path).endswith(".pdf"):
                st.info(f"📄 Loaded Digital PDF Document: `{Path(selected_image_path).name}`")
            else:
                img = Image.open(selected_image_path)
                st.image(img, caption=f"Document Preview: {Path(selected_image_path).name}", use_container_width=True)

        parse_btn = st.button("🤖 Run AI Vision Extraction & Structuring", type="primary", use_container_width=True)

    # Trigger Processing
    if parse_btn and selected_image_path:
        with st.spinner("Executing Super-Resolution Vision OCR & Domain LLM Reasoning..."):
            ocr_text, ocr_time = ocr_engine.extract_text(str(selected_image_path))
            order_data, llm_metrics = llm_extractor.extract_structured_order(
                raw_ocr_text=ocr_text,
                model_name=model_selected
            )
            total_time = round(ocr_time + llm_metrics.llm_time_ms, 2)
            warnings = llm_extractor.generate_warning_flags(order_data)

            st.session_state["parsed_result"] = {
                # Distinct per parse so editable widgets reset instead of keeping the previous document's values
                "run_id": uuid.uuid4().hex[:8],
                "ocr_text": ocr_text,
                "order_data": order_data,
                "ocr_time": round(ocr_time, 2),
                "llm_time": llm_metrics.llm_time_ms,
                "total_time": total_time,
                "model_name": llm_metrics.model_name,
                "is_mock": llm_metrics.is_mock,
                "warnings": warnings,
                "completeness": compute_completeness(order_data)
            }

    with col_right:
        st.subheader("2. Structured Engineering & Commercial Data")

        if "parsed_result" in st.session_state:
            res = st.session_state["parsed_result"]
            order = res["order_data"]

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Latency", f"{res['total_time']} ms")
            m2.metric("Vision OCR", f"{res['ocr_time']} ms")
            m3.metric("LLM Extraction", f"{res['llm_time']} ms")
            m4.metric("Field Completeness", f"{res['completeness']:.0%}",
                      help="Share of 8 key order fields that were filled. It measures coverage, not correctness.")

            st.caption(f"⚡ **Active Engine**: `{res['model_name']}` {'(Rule engine fallback)' if res['is_mock'] else '(Local Ollama inference)'}")
            for w in res["warnings"]:
                st.warning(w)

            st.markdown("#### 🎯 Packaging & Corrugation Engineering Specs")

            mat = order.material
            flute = " ".join(v for v in [mat.flute_type, f"({mat.paper_combination})" if mat.paper_combination else None] if v)

            sc1, sc2 = st.columns(2)
            with sc1:
                st.markdown(f"""
                <div class="spec-card">
                    <div class="spec-title">📐 Carton Dimensions (L × W × H)</div>
                    <div class="spec-val" style="color: #2563EB;">{order.carton.dimensions.display_dimension or NOT_DETECTED}</div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown(f"""
                <div class="spec-card">
                    <div class="spec-title">🧱 Board Grade & Flute Profile</div>
                    <div class="spec-val" style="color: #059669;">{flute or NOT_DETECTED}</div>
                </div>
                """, unsafe_allow_html=True)

            with sc2:
                st.markdown(f"""
                <div class="spec-card">
                    <div class="spec-title">📦 FEFCO Box Style Code</div>
                    <div class="spec-val" style="color: #D97706;">{order.carton.box_type or NOT_DETECTED}</div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown(f"""
                <div class="spec-card">
                    <div class="spec-title">🏷️ Joint Style & Craft</div>
                    <div class="spec-val" style="color: #7C3AED;">{order.carton.joint_type or NOT_DETECTED}</div>
                </div>
                """, unsafe_allow_html=True)

            cur = CURRENCY_SYMBOLS.get(order.commercial.currency, order.commercial.currency or "")

            tab_items, tab_header, tab_audit, tab_raw, tab_json = st.tabs([
                "📋 Line Items & Pricing", "🏢 Customer & Logistics", "🛡️ Financial Audit", "📝 Raw OCR Stream", "🧩 Standard JSON"
            ])

            with tab_items:
                st.markdown("##### 🛒 Itemized Products & Price Breakdown")

                if order.commercial.items:
                    table_data = []
                    for item in order.commercial.items:
                        table_data.append({
                            "#": item.line_no,
                            "Product / Description": item.item_name,
                            "Specification / Model": item.spec_model or "-",
                            "Qty": f"{item.quantity:g} {item.unit}",
                            "Unit Price": f"{cur} {item.unit_price:,.2f}".strip(),
                            "Line Subtotal": f"{cur} {item.subtotal:,.2f}".strip()
                        })
                    df_items = pd.DataFrame(table_data)
                    st.dataframe(df_items, use_container_width=True, hide_index=True)
                else:
                    st.info("No individual item lines detected. Displaying order summary.")

                st.markdown("---")
                sum_c1, sum_c2, sum_c3 = st.columns(3)
                sum_c1.metric("Total Items", len(order.commercial.items))
                qty = order.commercial.quantity
                sum_c2.metric("Total Order Qty", f"{qty:,} {order.commercial.unit}" if qty else ("Mixed units" if order.commercial.items else "—"))
                total = order.commercial.total_amount
                sum_c3.metric("Grand Total Amount", f"{cur} {total:,.2f}".strip() if total is not None else "—")

                if order.commercial.healing_note:
                    st.info(f"💡 **Amount Audit**: {order.commercial.healing_note}")

            with tab_header:
                # Reviewed values are what gets pushed to the ERP
                hdr = order.header
                edited_header = {}
                edited_header["customer_name"] = st.text_input("Customer Legal Entity", value=hdr.customer_name or "", key=f"cust_name_{res['run_id']}")
                c1, c2 = st.columns(2)
                edited_header["order_no"] = c1.text_input("Purchase Order / Job No.", value=hdr.order_no or "", key=f"ord_no_{res['run_id']}")
                edited_header["delivery_date"] = c2.text_input("Committed Delivery Date", value=hdr.delivery_date or "", key=f"del_date_{res['run_id']}")
                c3, c4 = st.columns(2)
                edited_header["contact_person"] = c3.text_input("Contact Person", value=hdr.contact_person or "", key=f"cont_per_{res['run_id']}")
                edited_header["contact_phone"] = c4.text_input("Phone Number", value=hdr.contact_phone or "", key=f"cont_ph_{res['run_id']}")
                edited_header["delivery_address"] = st.text_input("Delivery Address / Destination Factory", value=hdr.delivery_address or "", key=f"del_addr_{res['run_id']}")

                if order.special_requirements:
                    st.write("**⚠️ Special Engineering Instructions:**")
                    for req in order.special_requirements:
                        st.info(f"• {req}")

            with tab_audit:
                st.markdown("##### 🛡️ Dual-Channel Legal & Arithmetic Verification")
                if order.commercial.chinese_uppercase_amount:
                    st.text_input("Legal Uppercase Amount (防伪大写金额)", value=order.commercial.chinese_uppercase_amount, key="cn_upper_amt_en")

                if order.commercial.cross_check_verified:
                    st.success("✅ **Dual-Channel Audit Passed**: Arabic numerals match legal uppercase Chinese amount.")
                elif order.commercial.chinese_uppercase_amount:
                    st.warning("⚠️ **Audit not passed**: the numeric and uppercase amounts disagree. Please review manually.")
                else:
                    st.caption("No uppercase (大写) amount found on the document, so the total could not be cross-checked.")
                if order.commercial.healing_note:
                    st.info(order.commercial.healing_note)

                st.text_area("Printing & Finishing Craft", value=order.carton.printing_process or "", height=70)

            with tab_raw:
                st.caption(f"Raw neural network text stream ({len(res['ocr_text'].splitlines())} lines detected)")
                st.text_area("OCR Text Stream", value=res["ocr_text"], height=300)

            with tab_json:
                st.json(order.model_dump())

            st.divider()
            erp_c1, erp_c2 = st.columns([2, 1])
            with erp_c1:
                erp_target = st.selectbox(
                    "Target Production ERP / MES System (simulated — no live connector)",
                    ERP_TARGETS,
                    format_func=lambda t: t["label"]
                )
            with erp_c2:
                st.write("")
                st.write("")
                push_btn = st.button("🚀 Push to ERP (Simulated)", type="primary", use_container_width=True)

            if push_btn:
                reviewed = order.model_copy(deep=True)
                for field, value in edited_header.items():
                    setattr(reviewed.header, field, value.strip() or None)
                result = get_erp_adapter(erp_target["id"]).push(reviewed, operator="streamlit_ui")
                if result.simulated:
                    st.warning(f"🧪 **Simulated push** — bill no. `{result.erp_bill_no}`\n\n{result.message}")
                else:
                    st.success(f"✅ Work order created in **{erp_target['label']}**: `{result.erp_bill_no}`")
        else:
            st.info("👈 Please select a document benchmark on the left or upload an image, then click **'Run AI Vision Extraction & Structuring'**.")

# ==========================================
# WORKSPACE 2: REAL-TIME CHAT WITH LOCAL LLM
# ==========================================
elif workspace_mode == WS_CHAT:
    hardware = gpu_name or "CPU (no NVIDIA GPU detected)"
    st.markdown(f'<div class="main-header">💬 Real-Time Chat with {model_selected}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub-header">Direct conversational session with a local Ollama model on <b>{hardware}</b></div>', unsafe_allow_html=True)

    # Status banner reflects what Ollama actually reports
    if ollama_status["available"]:
        loaded = next((m for m in cached_loaded_models() if m["name"] == model_selected), None)
        vram = f"{loaded['size_vram'] / 1024**3:.1f} GB" if loaded and loaded["size_vram"] else "not loaded yet"
        quant = f" ({loaded['quantization']})" if loaded and loaded["quantization"] else ""
        st.markdown(f"""
        <div style="background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 8px; padding: 10px 16px; margin-bottom: 20px;">
            <span style="color: #15803D; font-weight: 600;">🟢 Ollama Online:</span>
            <span style="color: #374151; font-size: 0.95rem;"> Model: <code>{model_selected}{quant}</code> | Hardware: <code>{hardware}</code> | Model VRAM: <code>{vram}</code> | Endpoint: <code>{OLLAMA_API_BASE}</code></span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.error(f"🔴 Ollama is not reachable at `{OLLAMA_API_BASE}`. Start it with `ollama serve` to chat.")

    # Initialize chat history in session state
    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = [
            {
                "role": "assistant",
                "content": (
                    f"Hello! I am **{model_selected}**, running locally through Ollama.\n\n"
                    "Feel free to ask me anything about **packaging manufacturing** (e.g., FEFCO box styles, corrugated board fluting, BCT burst calculations), "
                    "coding and software architecture, or general conversation!"
                )
            }
        ]

    # Quick prompt shortcuts
    st.markdown("##### 💡 Suggested Questions / Quick Tests")
    qp_cols = st.columns(4)
    quick_prompt = None

    if qp_cols[0].button("📦 0201 vs 0427 箱型区别", use_container_width=True):
        quick_prompt = "请用通俗语言对比瓦楞纸箱的 0201 箱型（标准平口箱）与 0427 箱型（折叠飞机盒）的结构特点、开料成本与适用场景。"
    if qp_cols[1].button("🧱 瓦楞纸板 AB 瓦与 B 瓦", use_container_width=True):
        quick_prompt = "五层 AB 瓦与三层 B 瓦瓦楞纸板在抗压强度、厚度和缓冲性能上有什么核心区别？"
    if qp_cols[2].button("📐 纸箱抗压 BCT 凯里卡特公式", use_container_width=True):
        quick_prompt = "请解释纸箱抗压强度（BCT）计算中著名的麦基（McKee）公式与凯里卡特公式，并说明关键参数。"
    if qp_cols[3].button("🛡️ 为什么制造业需要本地 LLM？", use_container_width=True):
        quick_prompt = "Why is deploying a local LLM on edge GPUs crucial for traditional manufacturing enterprises over public cloud APIs?"

    # Display chat message history
    for msg in st.session_state["chat_messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Function for streaming response from local Ollama
    def generate_ollama_stream(messages):
        url = f"{OLLAMA_API_BASE.rstrip('/')}/chat/completions"
        payload = {
            "model": model_selected or DEFAULT_MODEL,
            "messages": messages,
            "stream": True,
            "temperature": 0.7
        }
        with httpx.stream("POST", url, json=payload, timeout=60.0) as response:
            for line in response.iter_lines():
                if line.startswith("data: "):
                    raw = line[6:].strip()
                    if raw == "[DONE]":
                        break
                    try:
                        chunk = json.loads(raw)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield delta
                    except Exception:
                        continue

    # Input handler (from quick prompt button or user text input)
    user_input = st.chat_input(f"Ask {model_selected} anything...") or quick_prompt

    if user_input:
        # Append user message
        st.session_state["chat_messages"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Generate assistant response
        with st.chat_message("assistant"):
            try:
                # Prepare conversation history for Ollama
                api_messages = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state["chat_messages"]
                ]
                full_response = st.write_stream(generate_ollama_stream(api_messages))
                st.session_state["chat_messages"].append({"role": "assistant", "content": full_response})
            except Exception as e:
                err_msg = f"⚠️ Could not reach local Ollama: {str(e)}. Please ensure `ollama serve` is running."
                st.error(err_msg)
                st.session_state["chat_messages"].append({"role": "assistant", "content": err_msg})

    # Clear chat button
    st.divider()
    if st.button("🗑️ Clear Conversation History"):
        st.session_state["chat_messages"] = [
            {
                "role": "assistant",
                "content": "Conversation cleared. Feel free to start a new chat session!"
            }
        ]
        st.rerun()
