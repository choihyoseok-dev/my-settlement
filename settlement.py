import streamlit as st
import pandas as pd
import json
from fpdf import FPDF
import os
from datetime import datetime
import io

# --------------------------------------------------------------------------
# 1. 설정 및 디자인 (Corporate Style)
# --------------------------------------------------------------------------
st.set_page_config(page_title="COMO CASA 정산 시스템", layout="wide", page_icon="🏢")

st.markdown("""
    <style>
    /* 전체 폰트 및 스타일 */
    body {
        font-family: 'Malgun Gothic', sans-serif;
    }
    
    /* 타이틀 스타일 */
    .main-title {
        font-size: 32px;
        font-weight: 700;
        color: #333;
        border-bottom: 2px solid #333;
        padding-bottom: 10px;
        margin-bottom: 20px;
    }
    
    /* 리포트 화면 스타일 (A4 느낌) */
    .report-container {
        background-color: white;
        padding: 40px;
        border: 1px solid #ddd;
        box-shadow: 0 0 10px rgba(0,0,0,0.05);
        max-width: 900px;
        margin: 0 auto;
    }
    
    /* 테이블 스타일 (HTML 렌더링용) */
    .styled-table {
        width: 100%;
        border-collapse: collapse;
        margin: 25px 0;
        font-size: 14px;
        font-family: sans-serif;
    }
    .styled-table th, .styled-table td {
        border: 1px solid #000; /* 진한 테두리 */
        padding: 8px 10px;
    }
    .styled-table thead tr {
        background-color: #f2f2f2;
        color: #333;
        text-align: center;
        font-weight: bold;
    }
    .styled-table tbody tr {
        border-bottom: 1px solid #dddddd;
    }
    .text-right { text-align: right; }
    .text-center { text-align: center; }
    .text-left { text-align: left; }
    .bold { font-weight: bold; }
    .bg-gray { background-color: #f9f9f9; }
    
    /* 섹션 제목 */
    .section-header {
        font-size: 18px;
        font-weight: bold;
        margin-top: 30px;
        margin-bottom: 10px;
        color: #000;
    }
    
    /* 입력창 스타일 */
    input:focus {
        border-color: #555 !important;
        box-shadow: none !important;
    }
    </style>
""", unsafe_allow_html=True)

# --------------------------------------------------------------------------
# 2. 상수 및 데이터 정의
# --------------------------------------------------------------------------
OTA_LIST = ["아고다", "부킹닷컴", "에어비앤비", "트립닷컴", "야놀자게하", "야놀자펜션", "여기어때", "추가정보(자가운영등)"]

COLS = {
    "OTA": "OTA",
    "D": "체크인건수(D)",
    "E": "숙박일수(E)",
    "F": "총매출액(F)",
    "G": "입금액(G)",
    "H": "플랫폼수수료(H)"
}

EXPENSE_ITEMS = {
    "building_maint": "건물관리비",
    "comm_cost": "통신비",
    "cleaning": "청소비",
    "laundry": "세탁비",
    "repair": "시설보수비",
    "linen": "린넨감가",
    "room_supply": "객실소모품",
    "etc_supply": "기타소모품"
}

# --------------------------------------------------------------------------
# 3. 로직 함수
# --------------------------------------------------------------------------
def init_session_state():
    if 'ota_df' not in st.session_state:
        data = {c: [0]*len(OTA_LIST) if c != "OTA" else OTA_LIST for c in COLS.values()}
        st.session_state.ota_df = pd.DataFrame(data)

    if 'expenses' not in st.session_state:
        st.session_state.expenses = {key: None for key in EXPENSE_ITEMS.keys()}
        # 추가 정보들
        st.session_state.expenses.update({
            'operating_days': 31,     # 정산월 가동일 (예: 1월은 31일)
            'avail_rooms': 1,         # 운영 객실 수 (가동 박수 계산용)
            'room_op_days': 30,       # 해당 호실 가동 일수 (섹션3용)
            'share_rate': 100.0,      # 지분율
            'divisor_days': 35        # 배당 기준 나눗셈 분모 (예: 전체 가동일수 합계)
        })

    if 'expense_notes' not in st.session_state:
        st.session_state.expense_notes = {key: "" for key in EXPENSE_ITEMS.keys()}

    if 'meta_info' not in st.session_state:
        st.session_state.meta_info = {
            "year": datetime.now().year,
            "month": datetime.now().month,
            "issue_date": datetime.now().strftime("%Y년 %m월 %d일"),
            "room_name": "101호",
            "owner_name": "홍길동"
        }

    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'input'

def get_safe_value(value):
    return value if value is not None else 0

def calculate_metrics(df, expenses):
    # 1. OTA Data
    calc_df = df.copy()
    calc_df[COLS["H"]] = calc_df[COLS["F"]] - calc_df[COLS["G"]]
    sums = calc_df.sum(numeric_only=True)
    
    F_total = sums.get(COLS["F"], 0) # 판매총액
    G_total = sums.get(COLS["G"], 0) # 순매출액
    E_total = sums.get(COLS["E"], 0) # 판매 박수 (Booked)
    D_total = sums.get(COLS["D"], 0) # 체크인 건수
    
    # 2. Expenses
    total_expense = sum(get_safe_value(expenses[k]) for k in EXPENSE_ITEMS.keys())
    
    # 3. Main Profit
    net_profit = G_total - total_expense
    commission = int(net_profit * 0.20)
    distributable_profit = int(net_profit - commission) # 배당 대상 순이익
    
    # 4. KPIs
    days_in_month = get_safe_value(expenses.get('operating_days', 30))
    avail_rooms = get_safe_value(expenses.get('avail_rooms', 1))
    
    avail_nights = days_in_month * avail_rooms # 가동 박수 (Available)
    
    adr = (F_total / E_total) if E_total > 0 else 0
    occ = (E_total / avail_nights * 100) if avail_nights > 0 else 0
    alos = (E_total / D_total) if D_total > 0 else 0
    
    # 5. Owner Distribution (Section 3)
    room_op_days = get_safe_value(expenses.get('room_op_days', 0))
    divisor_days = get_safe_value(expenses.get('divisor_days', 1)) # 배당 기준 일액 계산용 분모
    
    # 배당 기준 일액 (샘플 로직 추정: 배당대상순이익 / 전체가동일수합계?)
    # 사용자가 분모를 입력하게 함
    daily_base = distributable_profit / divisor_days if divisor_days > 0 else 0
    
    # 최종 배당금 = 배당 기준 일액 * 호실 가동일수 * 지분율?
    # 샘플에는 (배당대상순이익 39,283,126)이 있고 (호실가동일수 30), (배당기준일액 1,122,375)
    # 39,283,126 / 35 = 1,122,375. 따라서 divisor_days는 35로 추정됨.
    # 하지만 최종 배당금이 빈칸인 경우도 있고 계산되는 경우도 있음.
    # 여기서는 단순하게: 배당 대상 순이익 그 자체를 보여주거나, 지분율을 곱함.
    # 샘플의 "최종 배당 순이익" 칸이 비어있으므로, 로직은 유연하게 둡니다.
    # 여기서는 [배당 대상 순이익]을 최종으로 봅니다 (단독 소유 가정 시).
    
    final_payout = distributable_profit # 기본값
    
    return {
        "F_total": F_total, "G_total": G_total, "E_total": E_total, "D_total": D_total,
        "total_expense": total_expense, "net_profit": net_profit, 
        "commission": commission, "distributable": distributable_profit,
        "days_in_month": days_in_month, "avail_nights": avail_nights,
        "adr": adr, "occ": occ, "alos": alos,
        "room_op_days": room_op_days, "divisor_days": divisor_days, "daily_base": daily_base
    }

# --------------------------------------------------------------------------
# 4. PDF 생성 (FPDF Class 상속으로 커스텀)
# --------------------------------------------------------------------------
class PDFReport(FPDF):
    def header(self):
        pass # 헤더 없음 (본문에서 처리)

    def footer(self):
        # 하단 회사 정보 (샘플 참조)
        self.set_y(-40)
        self.set_font("NanumGothic", size=9)
        self.set_text_color(80, 80, 80)
        
        # 안내 문구
        self.cell(0, 5, "● 상기 금액은 부가세가 포함되어 있는 금액입니다.", ln=True)
        self.cell(0, 5, "● 정산 내역에 대한 문의사항은 ceo@comocasa.kr 또는 010-1234-5678 으로 연락 주시기 바랍니다.", ln=True)
        self.ln(5)
        
        # 회사명 및 대표이사
        self.set_font("NanumGothic", style='B', size=11)
        self.set_text_color(0, 0, 0)
        self.cell(0, 6, "주식회사 꼬모까사", ln=True)
        self.cell(0, 6, "대표이사 최 효 석", ln=True)

def create_pdf(metrics, expenses_dict, expense_notes, meta, stamp_image=None):
    pdf = PDFReport()
    pdf.add_page()
    
    # 폰트 로드
    font_path = "NanumGothic.ttf"
    if os.path.exists(font_path):
        pdf.add_font("NanumGothic", "", font_path, uni=True)
        pdf.add_font("NanumGothic", "B", font_path, uni=True)
    else:
        st.error("NanumGothic.ttf 폰트 파일이 필요합니다.")
        return None

    # 1. 타이틀 영역
    pdf.set_font("NanumGothic", "B", 22)
    pdf.cell(0, 15, f"꼬모까사 숙박 운영 정산서 : {meta['year']%100}년 {meta['month']}월", ln=True, align='C')
    # 밑줄 선
    pdf.set_line_width(0.5)
    pdf.line(10, 30, 200, 30)
    pdf.ln(10)

    # 발행 정보
    pdf.set_font("NanumGothic", "", 10)
    pdf.cell(0, 5, f"발행일: {meta['issue_date']}", ln=True)
    pdf.cell(0, 5, f"호실명/소유주: [{meta['room_name']}] / [{meta['owner_name']}]", ln=True)
    pdf.ln(8)

    # 공통 테이블 그리기 함수
    def draw_row(c1, c2, c3, c4, h=8, fill=False, bold_col1=False):
        pdf.set_font("NanumGothic", "B" if bold_col1 else "", 10)
        if fill: pdf.set_fill_color(240, 240, 240) # 연한 회색
        
        # Widths: [구분 50, 값 50, 단위 30, 비고 60] -> Total 190
        w = [50, 50, 30, 60]
        
        # Alignments
        a = ['L', 'R', 'C', 'L']
        
        pdf.cell(w[0], h, str(c1), 1, 0, 'C' if fill else 'L', fill) # 구분은 헤더일때 C, 아니면 L
        pdf.cell(w[1], h, str(c2), 1, 0, 'C' if fill else 'R', fill)
        pdf.cell(w[2], h, str(c3), 1, 0, 'C', fill)
        pdf.cell(w[3], h, str(c4), 1, 1, 'C' if fill else 'L', fill)

    # ----------------------------------------------------
    # 2. Section 1: Sales Status
    # ----------------------------------------------------
    pdf.set_font("NanumGothic", "B", 12)
    pdf.cell(0, 10, "1. 판매 현황 (Sales Status)", ln=True)
    
    # Header
    draw_row("구분", "금액/수치", "단위", "비고", fill=True, bold_col1=True)
    
    # Data
    def fmt(x): return f"{x:,}"
    
    draw_row("판매총액 (부가세 포함)", fmt(metrics['F_total']), "원", "")
    draw_row("순매출액", fmt(metrics['G_total']), "원", "")
    draw_row("정산월 가동일", str(metrics['days_in_month']), "일", "")
    draw_row("가동 박수 (Available)", fmt(metrics['avail_nights']), "일", "")
    draw_row("판매 박수 (Booked)", fmt(metrics['E_total']), "일", "")
    draw_row("체크인 건수", fmt(metrics['D_total']), "건", "")
    draw_row("체크인당 평균 박수", f"{metrics['alos']:.2f}", "일", "")
    draw_row("ADR (객단가)", fmt(int(metrics['adr'])), "원", "순매출액 / 판매 박수")
    draw_row("OCC (가동률)", f"{metrics['occ']:.1f}", "%", "판매 박수 / 가동 박수")
    pdf.ln(8)

    # ----------------------------------------------------
    # 3. Section 2: Detail
    # ----------------------------------------------------
    pdf.set_font("NanumGothic", "B", 12)
    pdf.cell(0, 10, "2. 정산 세부 내역 (Detailed Settlement Breakdown)", ln=True)
    
    # Header: 구분 | 금액 | 매출 대비(%) | 비고
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("NanumGothic", "B", 10)
    pdf.cell(50, 8, "구분", 1, 0, 'C', True)
    pdf.cell(50, 8, "금액", 1, 0, 'C', True)
    pdf.cell(30, 8, "매출 대비 (%)", 1, 0, 'C', True)
    pdf.cell(60, 8, "비고", 1, 1, 'C', True)
    
    base = metrics['G_total'] if metrics['G_total'] > 0 else 1
    
    # Rows
    def draw_detail_row(c1, c2, c3, c4, bold=False):
        pdf.set_font("NanumGothic", "B" if bold else "", 10)
        pdf.cell(50, 8, c1, 1, 0, 'L')
        pdf.cell(50, 8, c2, 1, 0, 'R')
        pdf.cell(30, 8, c3, 1, 0, 'R')
        pdf.cell(60, 8, c4, 1, 1, 'L')

    draw_detail_row("순매출액", fmt(metrics['G_total']), "100.0%", "", True)
    draw_detail_row("총 비용", fmt(metrics['total_expense']), f"{metrics['total_expense']/base*100:.1f}%", "", True)
    
    for key, label in EXPENSE_ITEMS.items():
        val = get_safe_value(expenses_dict[key])
        note = expense_notes.get(key, "")
        if val > 0 or note:
            draw_detail_row(label, fmt(val), f"{val/base*100:.1f}%", note)
            
    draw_detail_row("순이익 (총매출 - 총비용)", fmt(metrics['net_profit']), f"{metrics['net_profit']/base*100:.1f}%", "", True)
    draw_detail_row("위탁 수수료", fmt(metrics['commission']), f"{metrics['commission']/base*100:.1f}%", "순이익의 20%", True)
    draw_detail_row("배당 대상 순이익", fmt(metrics['distributable']), f"{metrics['distributable']/base*100:.1f}%", "[순이익] - [수수료]", True)
    pdf.ln(8)

    # ----------------------------------------------------
    # 4. Section 3: Owner Distribution
    # ----------------------------------------------------
    pdf.set_font("NanumGothic", "B", 12)
    pdf.cell(0, 10, "3. 소유주 정산 (Owner Distribution Settlement)", ln=True)
    
    draw_row("구분", "내용", "단위", "", fill=True, bold_col1=True)
    draw_row("배당 대상 순이익", fmt(metrics['distributable']), "원", "")
    draw_row("호실 가동 일수", str(metrics['room_op_days']), "일", "")
    draw_row("배당 기준 일액", fmt(int(metrics['daily_base'])), "원", "")
    draw_row("배당률 (소유주 지분율)", f"{get_safe_value(st.session_state.expenses.get('share_rate', 100))}%", "%", "")
    draw_row("최종 배당 순이익", "", "원", "") # 값은 비워둠 (샘플처럼)

    # ----------------------------------------------------
    # 5. 도장 이미지 삽입
    # ----------------------------------------------------
    # 도장 위치: 하단 대표이사 이름 옆 (x=80, y=265 정도)
    if stamp_image is not None:
        # 이미지를 임시 파일로 저장하거나 바이너리 스트림 사용
        # FPDF image는 파일 경로 혹은 PIL 이미지를 원함.
        # Streamlit UploadedFile -> temp file logic
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(stamp_image.getvalue())
            tmp_path = tmp.name
        
        # 도장 찍기 (크기 15x15 정도)
        # 위치 조정을 위해 y좌표 계산 (footer가 -40부터 시작)
        # 대표이사 이름 옆: x=65, y=약 265 (A4 높이 297)
        pdf.image(tmp_path, x=65, y=268, w=15) 
        os.unlink(tmp_path) # 임시 파일 삭제

    return bytes(pdf.output())

# --------------------------------------------------------------------------
# 5. 메인 화면 렌더링
# --------------------------------------------------------------------------
def main():
    init_session_state()

    # 페이지 분기
    if st.session_state.current_page == 'input':
        render_input_page()
    else:
        render_report_page()

def render_input_page():
    st.markdown('<div class="main-title">COMO CASA 정산 시스템 (Admin)</div>', unsafe_allow_html=True)
    
    # 1. 메타 정보 입력
    with st.expander("📝 기본 정보 설정 (발행일, 소유주 등)", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        st.session_state.meta_info['year'] = c1.number_input("정산 년도", value=st.session_state.meta_info['year'])
        st.session_state.meta_info['month'] = c2.number_input("정산 월", value=st.session_state.meta_info['month'])
        st.session_state.meta_info['room_name'] = c3.text_input("호실명", value=st.session_state.meta_info['room_name'])
        st.session_state.meta_info['owner_name'] = c4.text_input("소유주 성함", value=st.session_state.meta_info['owner_name'])
        
        c5, c6 = st.columns(2)
        st.session_state.meta_info['issue_date'] = c5.text_input("발행일 (문자열)", value=st.session_state.meta_info['issue_date'])
        
        # 도장 이미지 업로드
        st.session_state['stamp_file'] = c6.file_uploader("직인(도장) 이미지 업로드 (PNG 권장)", type=['png', 'jpg'])

    st.divider()

    # 2. OTA 매출
    st.subheader("1. 플랫폼(OTA) 매출 입력")
    # (기존 로직 유지: 자동계산 및 에디터)
    current_df = st.session_state.ota_df.copy()
    current_df[COLS["H"]] = current_df[COLS["F"]] - current_df[COLS["G"]]
    totals = current_df.sum(numeric_only=True)
    
    # 합계 보여주기
    st.info(f"💰 전체 매출 합계: {totals[COLS['F']]:,.0f}원 / 입금 합계: {totals[COLS['G']]:,.0f}원")
    
    edited_df = st.data_editor(
        current_df,
        key="ota_editor_v2", 
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            COLS["OTA"]: st.column_config.TextColumn("플랫폼", disabled=True),
            COLS["D"]: st.column_config.NumberColumn("체크인", format="%.0f"),
            COLS["E"]: st.column_config.NumberColumn("판매박수", format="%.0f"),
            COLS["F"]: st.column_config.NumberColumn("총매출액", format="%.0f"),
            COLS["G"]: st.column_config.NumberColumn("입금액", format="%.0f"),
            COLS["H"]: st.column_config.NumberColumn("수수료(자동)", format="%.0f", disabled=True),
        }
    )
    
    st.divider()

    # 3. 비용 및 추가 정보
    st.subheader("2. 비용 및 운영 데이터 입력")
    
    # 비용 (세로 배치)
    for key, label in EXPENSE_ITEMS.items():
        c1, c2 = st.columns([1, 2])
        val = c1.number_input(f"{label}", value=st.session_state.expenses[key], step=10000, key=f"in_{key}")
        note = c2.text_input(f"{label} 비고", value=st.session_state.expense_notes.get(key, ""), key=f"nt_{key}")
        st.session_state.expenses[key] = val
        st.session_state.expense_notes[key] = note
    
    st.markdown("#### ⚙️ 추가 운영 지표 (섹션 1, 3 계산용)")
    col_a, col_b, col_c = st.columns(3)
    st.session_state.expenses['operating_days'] = col_a.number_input("정산월 일수 (예: 31)", value=st.session_state.expenses['operating_days'])
    st.session_state.expenses['avail_rooms'] = col_b.number_input("운영 객실 수", value=st.session_state.expenses['avail_rooms'])
    st.session_state.expenses['room_op_days'] = col_c.number_input("해당 호실 가동일수", value=st.session_state.expenses['room_op_days'])
    
    col_d, col_e = st.columns(2)
    st.session_state.expenses['divisor_days'] = col_d.number_input("배당 기준 나눗셈 분모 (예: 전체 가동일)", value=st.session_state.expenses['divisor_days'])
    st.session_state.expenses['share_rate'] = col_e.number_input("지분율 (%)", value=st.session_state.expenses['share_rate'])

    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("📊 정산서 미리보기 및 출력", type="primary", use_container_width=True):
        st.session_state.ota_df = edited_df
        st.session_state.current_page = 'report'
        st.rerun()

def render_report_page():
    if st.button("⬅ 수정 화면으로", type="secondary"):
        st.session_state.current_page = 'input'
        st.rerun()
        
    metrics = calculate_metrics(st.session_state.ota_df, st.session_state.expenses)
    meta = st.session_state.meta_info
    
    # -------------------------------------------------------------
    # HTML 리포트 생성 (PDF와 100% 싱크로율 목표)
    # -------------------------------------------------------------
    
    # 헬퍼: 금액 포맷
    def fmt(x): return f"{x:,.0f}" if isinstance(x, (int, float)) else x
    def pct(x): return f"{x:.1f}%"
    
    # 1. 헤더 HTML
    html_header = f"""
    <div class="report-container">
        <div style="text-align: center; font-size: 28px; font-weight: bold; border-bottom: 2px solid #000; padding-bottom: 15px; margin-bottom: 20px;">
            꼬모까사 숙박 운영 정산서 : {meta['year']%100}년 {meta['month']}월
        </div>
        <div style="font-size: 14px; line-height: 1.6;">
            발행일: {meta['issue_date']}<br>
            호실명/소유주: [{meta['room_name']}] / [{meta['owner_name']}]
        </div>
        
        <div class="section-header">1. 판매 현황 (Sales Status)</div>
        <table class="styled-table">
            <thead>
                <tr>
                    <th width="30%">구분</th> <th width="30%">금액/수치</th> <th width="15%">단위</th> <th width="25%">비고</th>
                </tr>
            </thead>
            <tbody>
                <tr><td>판매총액 (부가세 포함)</td> <td class="text-right">{fmt(metrics['F_total'])}</td> <td class="text-center">원</td> <td></td></tr>
                <tr><td>순매출액</td> <td class="text-right">{fmt(metrics['G_total'])}</td> <td class="text-center">원</td> <td></td></tr>
                <tr><td>정산월 가동일</td> <td class="text-right">{metrics['days_in_month']}</td> <td class="text-center">일</td> <td></td></tr>
                <tr><td>가동 박수 (Available)</td> <td class="text-right">{fmt(metrics['avail_nights'])}</td> <td class="text-center">일</td> <td></td></tr>
                <tr><td>판매 박수 (Booked)</td> <td class="text-right">{fmt(metrics['E_total'])}</td> <td class="text-center">일</td> <td></td></tr>
                <tr><td>체크인 건수</td> <td class="text-right">{fmt(metrics['D_total'])}</td> <td class="text-center">건</td> <td></td></tr>
                <tr><td>체크인당 평균 박수</td> <td class="text-right">{metrics['alos']:.2f}</td> <td class="text-center">일</td> <td></td></tr>
                <tr><td>ADR (객단가)</td> <td class="text-right">{fmt(metrics['adr'])}</td> <td class="text-center">원</td> <td>순매출액 / 판매박수</td></tr>
                <tr><td>OCC (가동률)</td> <td class="text-right">{metrics['occ']:.1f}</td> <td class="text-center">%</td> <td>판매박수 / 가동박수</td></tr>
            </tbody>
        </table>
        
        <div class="section-header">2. 정산 세부 내역 (Detailed Settlement Breakdown)</div>
        <table class="styled-table">
            <thead>
                <tr>
                    <th>구분</th> <th>금액</th> <th>매출 대비 (%)</th> <th>비고</th>
                </tr>
            </thead>
            <tbody>
    """
    
    # 2. 상세내역 Body
    base = metrics['G_total'] if metrics['G_total'] > 0 else 1
    
    # 순매출
    html_header += f"""
        <tr><td class="bold">순매출액</td> <td class="text-right bold">{fmt(metrics['G_total'])}</td> <td class="text-right">100.0%</td> <td></td></tr>
        <tr><td class="bold">총 비용</td> <td class="text-right bold">{fmt(metrics['total_expense'])}</td> <td class="text-right">{pct(metrics['total_expense']/base*100)}</td> <td></td></tr>
    """
    
    # 비용 루프
    for key, label in EXPENSE_ITEMS.items():
        val = get_safe_value(st.session_state.expenses[key])
        note = st.session_state.expense_notes.get(key, "")
        if val > 0 or note:
            html_header += f"""
                <tr><td>{label}</td> <td class="text-right">{fmt(val)}</td> <td class="text-right">{pct(val/base*100)}</td> <td>{note}</td></tr>
            """
            
    # 이익 및 수수료
    html_header += f"""
        <tr><td class="bold bg-gray">순이익 (총매출 - 총비용)</td> <td class="text-right bold bg-gray">{fmt(metrics['net_profit'])}</td> <td class="text-right bg-gray">{pct(metrics['net_profit']/base*100)}</td> <td class="bg-gray"></td></tr>
        <tr><td class="bold">위탁 수수료</td> <td class="text-right bold">{fmt(metrics['commission'])}</td> <td class="text-right">{pct(metrics['commission']/base*100)}</td> <td>순이익의 20%</td></tr>
        <tr><td class="bold bg-gray">배당 대상 순이익</td> <td class="text-right bold bg-gray">{fmt(metrics['distributable'])}</td> <td class="text-right bg-gray">{pct(metrics['distributable']/base*100)}</td> <td class="bg-gray">[순이익] - [수수료]</td></tr>
    </tbody>
    </table>
    """
    
    # 3. 소유주 정산 HTML
    share = get_safe_value(st.session_state.expenses.get('share_rate', 100))
    html_header += f"""
        <div class="section-header">3. 소유주 정산 (Owner Distribution Settlement)</div>
        <table class="styled-table">
            <thead>
                <tr><th>구분</th> <th>내용</th> <th>단위</th></tr>
            </thead>
            <tbody>
                <tr><td>배당 대상 순이익</td> <td class="text-right">{fmt(metrics['distributable'])}</td> <td class="text-center">원</td></tr>
                <tr><td>호실 가동 일수</td> <td class="text-right">{metrics['room_op_days']}</td> <td class="text-center">일</td></tr>
                <tr><td>배당 기준 일액</td> <td class="text-right">{fmt(int(metrics['daily_base']))}</td> <td class="text-center">원</td></tr>
                <tr><td>배당률 (소유주 지분율)</td> <td class="text-right">{share}%</td> <td class="text-center">%</td></tr>
                <tr><td class="bold">최종 배당 순이익</td> <td class="text-right bold"></td> <td class="text-center">원</td></tr>
            </tbody>
        </table>
        
        <div style="margin-top: 40px; font-size: 13px; color: #555;">
            ● 상기 금액은 부가세가 포함되어 있는 금액입니다.<br>
            ● 정산 내역에 대한 문의사항은 ceo@comocasa.kr 또는 010-1234-5678 으로 연락 주시기 바랍니다.
        </div>
        
        <div style="margin-top: 40px; font-weight: bold; font-size: 16px;">
            주식회사 꼬모까사<br>
            대표이사 최 효 석 (인)
        </div>
    </div>
    """
    
    # 화면 출력
    st.markdown(html_header, unsafe_allow_html=True)
    
    # -------------------------------------------------------------
    # PDF 다운로드
    # -------------------------------------------------------------
    st.divider()
    
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        stamp_img = st.session_state.get('stamp_file')
        try:
            pdf_bytes = create_pdf(metrics, st.session_state.expenses, st.session_state.expense_notes, meta, stamp_img)
            if pdf_bytes:
                st.download_button(
                    "📄 PDF 정산서 다운로드",
                    pdf_bytes,
                    f"정산서_{meta['room_name']}_{meta['owner_name']}.pdf",
                    "application/pdf",
                    type="primary",
                    use_container_width=True
                )
        except Exception as e:
            st.error(f"PDF 생성 실패: {e}")
            st.warning("폰트 파일(NanumGothic.ttf)이 있는지 확인해주세요.")

if __name__ == "__main__":
    main()
