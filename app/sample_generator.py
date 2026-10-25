import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from app.config import SAMPLES_DIR

def get_font(size: int = 16, bold: bool = False):
    """Attempt to load Windows standard Chinese fonts, fallback to default font."""
    font_paths = [
        "C:/Windows/Fonts/msyh.ttc",   # Microsoft YaHei
        "C:/Windows/Fonts/msyhbd.ttc", # Microsoft YaHei Bold
        "C:/Windows/Fonts/simhei.ttf",  # SimHei
        "C:/Windows/Fonts/simsun.ttc",  # SimSun
        "C:/Windows/Fonts/arial.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size=size)
            except Exception:
                continue
    return ImageFont.load_default()

def draw_header_banner(draw: ImageDraw.ImageDraw, title: str, subtitle: str, width: int):
    # Top banner background
    draw.rectangle([(0, 0), (width, 80)], fill="#1E293B")
    title_font = get_font(24, bold=True)
    subtitle_font = get_font(13)
    draw.text((30, 18), title, fill="#FFFFFF", font=title_font)
    draw.text((30, 52), subtitle, fill="#94A3B8", font=subtitle_font)

def create_sample_1_corrugated() -> Path:
    """Sample 1: 出口五层瓦楞纸箱生产任务单"""
    width, height = 900, 1100
    img = Image.new("RGB", (width, height), "#FFFFFF")
    draw = ImageDraw.Draw(img)

    draw_header_banner(draw, "K.P.P. Packaging 昆山华美包装 - 纸箱生产流转通知单", "标准生产指令单 | 编号: KPP-2026-0915-082 | 状态: 已下达", width)

    # Fonts
    lbl_font = get_font(15, bold=True)
    val_font = get_font(15)
    section_font = get_font(17, bold=True)
    note_font = get_font(14)

    # Box layout container
    draw.rectangle([(25, 95), (width - 25, height - 35)], outline="#CBD5E1", width=2)

    # Section 1: Customer & Order Header
    draw.rectangle([(25, 95), (width - 25, 135)], fill="#F1F5F9")
    draw.text((40, 103), "一、 客户与订单基本信息", fill="#0F172A", font=section_font)

    items_sec1 = [
        ("客户名称", "苏州汇川智能电气系统有限公司", 150),
        ("采购单号", "HC-PO-202609-0881", 150),
        ("联 系 人", "王工 / 138-1234-5678", 185),
        ("交货日期", "2026-09-28 (严禁延期)", 185),
        ("送货地址", "江苏省苏州市相城区智能制造产业园B栋3号门", 220),
        ("所属行业", "新能源工业控制装备配套", 220)
    ]
    # Draw 2 columns
    draw.text((40, 150), "客户名称: 苏州汇川智能电气系统有限公司", fill="#334155", font=lbl_font)
    draw.text((500, 150), "采购单号: HC-PO-202609-0881", fill="#334155", font=lbl_font)
    draw.text((40, 185), "联 系 人: 王工 (138-1234-5678)", fill="#334155", font=lbl_font)
    draw.text((500, 185), "承诺交期: 2026-09-28", fill="#B91C1C", font=lbl_font)
    draw.text((40, 220), "送货地址: 江苏省苏州市相城区智能制造产业园B栋3号门仓库", fill="#334155", font=val_font)

    # Section 2: Product & Carton Specifications (CORE PACKAGING ATTRIBUTES)
    draw.rectangle([(25, 265), (width - 25, 305)], fill="#F1F5F9")
    draw.text((40, 273), "二、 纸箱技术规格与材质要求", fill="#0F172A", font=section_font)

    draw.rectangle([(40, 320), (width - 40, 520)], outline="#E2E8F0", fill="#F8FAFC", width=1)
    # Specs
    draw.text((55, 335), "【纸箱尺寸】: 530 × 380 × 420 mm (外径尺寸 / 制造公差 ±2mm)", fill="#0F172A", font=lbl_font)
    draw.text((55, 375), "【箱型结构】: 0201 国标标准平口开槽纸箱 (标准上下摇盖对口)", fill="#334155", font=val_font)
    draw.text((55, 415), "【瓦楞材质】: 五层AB瓦 (特硬牛卡配纸: K=A, 强化防潮芯)", fill="#1E40AF", font=lbl_font)
    draw.text((55, 455), "【配纸克重】: 175g牛卡面纸 / 140g高强芯 / 140g高强瓦 / 140g里纸", fill="#334155", font=val_font)
    draw.text((55, 488), "【接缝工艺】: 优质镀锌双钉打钉 (钉距45-50mm, 剪刀差<=3mm)", fill="#334155", font=val_font)

    # Section 3: Printing & Finishing
    draw.rectangle([(25, 540), (width - 25, 580)], fill="#F1F5F9")
    draw.text((40, 548), "三、 印刷与工艺细节", fill="#0F172A", font=section_font)

    draw.text((40, 595), "印刷工艺: 正面+侧面双色水墨环保印刷 (黑色Logo + 绿色环保麦头)", fill="#334155", font=lbl_font)
    draw.text((40, 630), "唛头要求: 按照客户图纸第3版要求，标注UP向上标示、防潮及重心配重线", fill="#334155", font=val_font)
    draw.text((40, 665), "手挽开孔: 左右两侧各冲切一个防划手塑胶扣手把孔 (间距中心对称)", fill="#334155", font=val_font)

    # Section 4: Commercial & Volume
    draw.rectangle([(25, 715), (width - 25, 755)], fill="#F1F5F9")
    draw.text((40, 723), "四、 生产数量与商务核算", fill="#0F172A", font=section_font)

    # Draw table
    draw.rectangle([(40, 770), (width - 40, 850)], outline="#94A3B8", width=1)
    draw.line([(40, 810), (width - 40, 810)], fill="#94A3B8", width=1)
    draw.line([(220, 770), (220, 850)], fill="#94A3B8", width=1)
    draw.line([(400, 770), (400, 850)], fill="#94A3B8", width=1)
    draw.line([(600, 770), (600, 850)], fill="#94A3B8", width=1)

    th_font = get_font(14, bold=True)
    draw.text((70, 782), "订购品名", fill="#475569", font=th_font)
    draw.text((260, 782), "计划生产数量", fill="#475569", font=th_font)
    draw.text((450, 782), "含税单价(元)", fill="#475569", font=th_font)
    draw.text((680, 782), "合计金额", fill="#475569", font=th_font)

    draw.text((60, 822), "五层重型变频器外箱", fill="#0F172A", font=val_font)
    draw.text((280, 822), "3,500 个", fill="#0F172A", font=lbl_font)
    draw.text((475, 822), "¥ 6.80", fill="#0F172A", font=val_font)
    draw.text((670, 822), "¥ 23,800.00", fill="#B91C1C", font=lbl_font)

    # Section 5: Quality & Delivery instructions
    draw.rectangle([(25, 875), (width - 25, 915)], fill="#F1F5F9")
    draw.text((40, 883), "五、 仓储与品质检验特别要求", fill="#0F172A", font=section_font)

    draw.text((40, 930), "1. 打托要求: 1100×1100mm 熏蒸九脚木托盘，每托350只，十字交错堆叠并双层缠绕膜防护。", fill="#475569", font=note_font)
    draw.text((40, 960), "2. 物性要求: 耐破强度需 >= 1450 kPa，边压强度 >= 7.8 kN/m，空箱抗压 >= 4500 N。", fill="#475569", font=note_font)
    draw.text((40, 990), "3. 随货同行: 附具出厂合格证及第三方SGS有害物质检测报告一份。", fill="#475569", font=note_font)

    # Simulated stamp
    draw.ellipse([(width - 210, height - 160), (width - 70, height - 40)], outline="#DC2626", width=3)
    stamp_font = get_font(13, bold=True)
    draw.text((width - 195, height - 120), "生产计划部专用章", fill="#DC2626", font=stamp_font)
    draw.text((width - 180, height - 95), "2026-09-15 批准", fill="#DC2626", font=stamp_font)

    out_path = SAMPLES_DIR / "sample_1_corrugated_box.png"
    img.save(out_path, "PNG")
    return out_path

def create_sample_2_giftbox() -> Path:
    """Sample 2: 电子穿戴精品彩盒定制规格单"""
    width, height = 900, 1050
    img = Image.new("RGB", (width, height), "#FFFFFF")
    draw = ImageDraw.Draw(img)

    draw_header_banner(draw, "K.P.P. Packaging - 消费类电子精品盒定制生产工单", "工单编号: KPP-OEM-2026-9941A | 产线: 精品精品车间2号线", width)

    lbl_font = get_font(15, bold=True)
    val_font = get_font(15)
    section_font = get_font(17, bold=True)
    note_font = get_font(14)

    draw.rectangle([(25, 95), (width - 25, height - 35)], outline="#CBD5E1", width=2)

    # Section 1
    draw.rectangle([(25, 95), (width - 25, 135)], fill="#EFF6FF")
    draw.text((40, 103), "客户商务信息", fill="#1E3A8A", font=section_font)

    draw.text((40, 150), "客户名称: 深圳市灵犀数码穿戴科技有限公司", fill="#334155", font=lbl_font)
    draw.text((520, 150), "采购编号: LX-PO-2026-9941A", fill="#334155", font=lbl_font)
    draw.text((40, 185), "联系人员: 陈主管 (139-8765-4321)", fill="#334155", font=lbl_font)
    draw.text((520, 185), "交货日期: 2026-09-22 (急件)", fill="#DC2626", font=lbl_font)
    draw.text((40, 220), "送达车间: 深圳市宝安区福永凤凰第三工业区C栋3楼组装车间", fill="#334155", font=val_font)

    # Section 2
    draw.rectangle([(25, 260), (width - 25, 300)], fill="#EFF6FF")
    draw.text((40, 268), "盒型结构与材质工艺", fill="#1E3A8A", font=section_font)

    draw.rectangle([(40, 315), (width - 40, 505)], outline="#BFDBFE", fill="#F8FAFC", width=1)
    draw.text((55, 330), "【成品尺寸】: 185 × 120 × 55 mm (盒体内径尺寸)", fill="#1E40AF", font=lbl_font)
    draw.text((55, 368), "【盒型分类】: 天地盖精品盒 (上下盖全扣合 + 内藏式强磁吸合结构)", fill="#0F172A", font=lbl_font)
    draw.text((55, 403), "【芯板基材】: 三层E瓦 (高密度微楞强化防震硬芯) 复合 1200g灰板", fill="#334155", font=val_font)
    draw.text((55, 438), "【面纸材质】: 350g 进口单铜高白卡纸 (白度>=92%)", fill="#334155", font=val_font)
    draw.text((55, 473), "【成型方式】: 环保全自动流水线白胶裱贴，严禁起泡和溢胶", fill="#334155", font=val_font)

    # Section 3
    draw.rectangle([(25, 525), (width - 25, 565)], fill="#EFF6FF")
    draw.text((40, 533), "印刷及表面整饰", fill="#1E3A8A", font=section_font)

    draw.text((40, 580), "印刷颜色: 4色CMYK胶印 + 专色Pantone 286C 品牌蓝", fill="#334155", font=lbl_font)
    draw.text((40, 615), "表面效果: 满版触感哑膜 + 盒盖Logo局部3D立体UV上光 + 烫哑银工艺", fill="#334155", font=val_font)
    draw.text((40, 650), "内托配件: 黑色高密度EVA内衬开槽，精准贴合智能手表与充电器底座", fill="#334155", font=val_font)

    # Section 4: Commercial
    draw.rectangle([(25, 700), (width - 25, 740)], fill="#EFF6FF")
    draw.text((40, 708), "商务价格与计划量", fill="#1E3A8A", font=section_font)

    draw.rectangle([(40, 755), (width - 40, 835)], outline="#94A3B8", width=1)
    draw.line([(40, 795), (width - 40, 795)], fill="#94A3B8", width=1)
    draw.line([(250, 755), (250, 835)], fill="#94A3B8", width=1)
    draw.line([(450, 755), (450, 835)], fill="#94A3B8", width=1)
    draw.line([(650, 755), (650, 835)], fill="#94A3B8", width=1)

    th_font = get_font(14, bold=True)
    draw.text((70, 767), "产品名称", fill="#475569", font=th_font)
    draw.text((290, 767), "订购套数", fill="#475569", font=th_font)
    draw.text((490, 767), "含税单价(元)", fill="#475569", font=th_font)
    draw.text((710, 767), "总金额", fill="#475569", font=th_font)

    draw.text((60, 807), "智能穿戴包装彩盒", fill="#0F172A", font=val_font)
    draw.text((310, 807), "10,000 套", fill="#0F172A", font=lbl_font)
    draw.text((520, 807), "¥ 4.20", fill="#0F172A", font=val_font)
    draw.text((700, 807), "¥ 42,000.00", fill="#DC2626", font=lbl_font)

    draw.text((40, 860), "备注条款: 严格执行RoHS与REACH无毒无铅检测标准；每箱独立套防尘袋包装入中箱。", fill="#64748B", font=note_font)

    # Simulated stamp
    draw.ellipse([(width - 210, height - 160), (width - 70, height - 40)], outline="#DC2626", width=3)
    stamp_font = get_font(13, bold=True)
    draw.text((width - 195, height - 120), "外协工程审定章", fill="#DC2626", font=stamp_font)
    draw.text((width - 180, height - 95), "2026-09-14 核准", fill="#DC2626", font=stamp_font)

    out_path = SAMPLES_DIR / "sample_2_gift_box.png"
    img.save(out_path, "PNG")
    return out_path

def create_sample_3_ecommerce() -> Path:
    """Sample 3: 电商飞机盒急单出货凭证"""
    width, height = 900, 1000
    img = Image.new("RGB", (width, height), "#FFFFFF")
    draw = ImageDraw.Draw(img)

    draw_header_banner(draw, "K.P.P. Packaging 快包达联运 - 电商飞机盒发货与生产凭单", "电商供应链现货派单 | 编号: KPP-EC-2026-019", width)

    lbl_font = get_font(15, bold=True)
    val_font = get_font(15)
    section_font = get_font(17, bold=True)
    note_font = get_font(14)

    draw.rectangle([(25, 95), (width - 25, height - 35)], outline="#CBD5E1", width=2)

    # Section 1
    draw.rectangle([(25, 95), (width - 25, 135)], fill="#FEF3C7")
    draw.text((40, 103), "订购与收件信息", fill="#92400E", font=section_font)

    draw.text((40, 150), "买方客户: 杭州云朵家纺供应链有限公司", fill="#334155", font=lbl_font)
    draw.text((520, 150), "销售单号: YD-202609-019", fill="#334155", font=lbl_font)
    draw.text((40, 185), "业务代表: 李经理 (137-0000-1122)", fill="#334155", font=lbl_font)
    draw.text((520, 185), "交割日期: 2026-09-19 (紧急)", fill="#DC2626", font=lbl_font)
    draw.text((40, 220), "收货地址: 浙江省杭州市萧山区瓜沥镇仓储物流中心8号分拣库", fill="#334155", font=val_font)

    # Section 2
    draw.rectangle([(25, 260), (width - 25, 300)], fill="#FEF3C7")
    draw.text((40, 268), "包装箱型与结构说明", fill="#92400E", font=section_font)

    draw.rectangle([(40, 315), (width - 40, 485)], outline="#FDE68A", fill="#FFFBEB", width=1)
    draw.text((55, 330), "【箱体规格】: 320 × 220 × 100 mm (成型外尺寸)", fill="#0F172A", font=lbl_font)
    draw.text((55, 368), "【箱型款式】: 0427 模切折叠飞机盒 (自锁卡扣，免胶成型)", fill="#334155", font=lbl_font)
    draw.text((55, 403), "【材质楞型】: 三层B瓦 (T=T 强化耐折型高韧度牛皮瓦楞板)", fill="#B45309", font=lbl_font)
    draw.text((55, 438), "【模切刀版】: 激光刀模号: DM-0427-322210，全冲压成型，无毛边", fill="#334155", font=val_font)

    # Section 3
    draw.rectangle([(25, 505), (width - 25, 545)], fill="#FEF3C7")
    draw.text((40, 513), "印字与数量", fill="#92400E", font=section_font)

    draw.text((40, 560), "印刷内容: 单色黑色环保水墨柔印 (盒盖印: 云朵家纺 伴您好梦 / 侧边条形码)", fill="#334155", font=val_font)
    draw.text((40, 595), "接头工艺: 一体成型折叠盒，无需打钉、无需粘胶", fill="#334155", font=val_font)

    # Commercial
    draw.rectangle([(40, 640), (width - 40, 720)], outline="#94A3B8", width=1)
    draw.line([(40, 680), (width - 40, 680)], fill="#94A3B8", width=1)
    draw.line([(250, 640), (250, 720)], fill="#94A3B8", width=1)
    draw.line([(450, 640), (450, 720)], fill="#94A3B8", width=1)
    draw.line([(650, 640), (650, 720)], fill="#94A3B8", width=1)

    th_font = get_font(14, bold=True)
    draw.text((70, 652), "规格项目", fill="#475569", font=th_font)
    draw.text((290, 652), "交付数量", fill="#475569", font=th_font)
    draw.text((490, 652), "单价 (元)", fill="#475569", font=th_font)
    draw.text((710, 652), "价税合计", fill="#475569", font=th_font)

    draw.text((60, 692), "0427自锁飞机盒", fill="#0F172A", font=val_font)
    draw.text((310, 692), "8,000 个", fill="#0F172A", font=lbl_font)
    draw.text((520, 692), "¥ 1.85", fill="#0F172A", font=val_font)
    draw.text((700, 692), "¥ 14,800.00", fill="#DC2626", font=lbl_font)

    draw.text((40, 750), "发运要求: 每捆50个打包带捆扎，整托盘缠膜装运，9月19日上午10点前必须入库。", fill="#64748B", font=note_font)

    # Simulated stamp
    draw.ellipse([(width - 210, height - 160), (width - 70, height - 40)], outline="#DC2626", width=3)
    stamp_font = get_font(13, bold=True)
    draw.text((width - 195, height - 120), "供应链调度专用", fill="#DC2626", font=stamp_font)
    draw.text((width - 180, height - 95), "2026-09-16 调度", fill="#DC2626", font=stamp_font)

    out_path = SAMPLES_DIR / "sample_3_ecommerce_mailer.png"
    img.save(out_path, "PNG")
    return out_path

def generate_all_samples():
    """Generates all 3 sample documents if not already existing."""
    s1 = create_sample_1_corrugated()
    s2 = create_sample_2_giftbox()
    s3 = create_sample_3_ecommerce()
    return [s1, s2, s3]

if __name__ == "__main__":
    paths = generate_all_samples()
    print(f"Generated samples successfully: {[p.name for p in paths]}")
