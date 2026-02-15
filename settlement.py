import streamlit as st
import pandas as pd
import json
from fpdf import FPDF
import os
from datetime import datetime

# --------------------------------------------------------------------------
# 1. 설정 및 디자인 (CSS)
# --------------------------------------------------------------------------
st.set_page_config(page_title="COMO CASA 정산 시스템", layout="wide", page_icon="🏢")

st.markdown("""
    <style>
    /* 폰트 및 기본 스타일 */
    body { font-family: 'Malgun Gothic', sans-serif; }
    
    /* 타이틀 스타일 */
    .main-title {
        font-size: 32px; font-weight: 800; color: #1E3A8A;
        border-bottom: 3px solid #1E3A8A; padding-bottom: 10px; margin-bottom: 20px;
    }
    
    /* 입력창 스타일 */
    div.stTextInput > div > div > input {
        text-align: right; /* 숫자 입력처럼 우측 정렬 */
    }
    
    /* 정산서 리포트 (HTML) 스타일 */
    .report-wrapper {
        background-color: white;
        padding: 40px;
        border: 1px solid #ccc;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.1);
        font-family: 'Malgun Gothic', sans-serif;
        color: #000;
    }
    .report-title {
        text-align: center; font-size: 26px; font-weight: bold;
        border-bottom: 2px solid #000; padding-bottom: 15px; margin-bottom: 30px;
    }
    .section-header {
        font-size: 16px; font-weight: bold; margin-top: 30px; margin-bottom: 10px;
        color: #1E3A8A;
    }
    .styled-table {
        width: 100%; border-collapse: collapse; font-size: 13px;
    }
    .styled-table th {
        border: 1px solid #000; background-color: #f2f2f2; padding: 8px; text-align: center;
    }
    .styled-table td {
        border: 1px solid #000; padding: 8px;
    }
    .text-right { text-align: right; }
    .text-center { text-align: center; }
    .bold { font-weight: bold; }
    .bg-gray { background-color: #f9f9f9; }
    </style>
""", unsafe_allow_html=True)

# --------------------------------------------------------------------------
# 2. 데이터 구조 및 유틸리티 함수
# --------------------------------------------------------------------------
OTA_LIST = ["아고다", "부킹닷컴", "에어비앤비", "트립닷컴", "야놀자게하", "야놀자펜션", "여기어때", "추가정보(자가운영등)"]

COLS = {
    "OTA": "OTA", "D": "체크인건수(D)", "E": "숙박일수(E)",
    "F": "총매출액(F)", "G": "입금액(G)", "H": "플랫폼수수료(H)"
}

EXPENSE_ITEMS = {
    "building_maint": "건물관리비", "comm_cost": "통신비", "cleaning": "청소비",
    "laundry": "세탁비", "repair": "시설보수비", "linen": "린넨감가",
    "room_supply": "객실소모품", "etc_supply": "기타소모품"
}

def parse_comma_int(value_str):
    """콤마가 포함된 문자열을 정수로 변환"""
    if value_str is None: return 0
    if isinstance(value_str, (int, float)): return int(value_str)
    try:
        return int(str(value_str).replace(',', '').strip())
    except:
        return 0

def format_comma(value):
    """숫자를 콤마가 포함된 문자열로 변환"""
    if value is None: return ""
    try:
        return f"{int(value):,}"
    except:
        return str(value)

def get_safe_value(value):
    return parse_comma_int(value)

# --------------------------------------------------------------------------
# 3. 로직 및 상태 초기화
# --------------------------------------------------------------------------
def init_session_state():
    if 'ota_df' not in st.session_state:
        data = {c: [0]*len(OTA_LIST) if c != "OTA" else OTA_LIST for c in COLS.values()}
        st.session_state.ota_df = pd.DataFrame(data)

    if 'expenses' not in st.session_state:
        st.session_state.expenses = {key: 0 for key in EXPENSE_ITEMS.keys()}
        st.session_state.expenses.update({
            'operating_days': 31, 'avail_rooms': 1, 'room_op_days': 30,
            'share_rate': 100, 'divisor_days': 35
        })

    if 'expense_notes' not in st.session_state:
        st.session_state.expense_notes = {key: "" for key in EXPENSE_ITEMS.keys()}

    if 'meta_info' not in st.session_state:
        st.session_state.meta_info = {
            "year": datetime.now().year, "month": datetime.now().month,
            "issue_date": datetime.now().strftime("%Y년 %m월 %d일"),
            "room_name": "101호", "owner_name": "홍길동"
        }
    
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'input'

def calculate_metrics(df, expenses):
    # 1. OTA 계산
    calc_df = df.copy()
    calc_df[COLS["H"]] = calc_df[COLS["F"]] - calc_df[COLS["G"]]
    sums = calc_df.sum(numeric_only=True)
    
    metrics = {}
    metrics['F_total'] = sums.get(COLS["F"], 0)
    metrics['G_total'] = sums.get(COLS["G"], 0)
    metrics['E_total'] = sums.get(COLS["E"], 0)
    metrics['D_total'] = sums.get(COLS["D"], 0)
    
    # 2. 비용 계산
    metrics['total_expense'] = sum(get_safe_value(expenses[k]) for k in EXPENSE_ITEMS.keys())
    
    # 3. 이익 계산
    metrics['net_profit'] = metrics['G_total'] - metrics['total_expense']
    metrics['commission'] = int(metrics['net_profit'] * 0.20)
    metrics['distributable'] = int(metrics['net_profit'] - metrics['commission'])
    
    # 4. KPI
    op_days = get_safe_value(expenses.get('operating_days', 30))
    metrics['days_in_month'] = op_days
    metrics['avail_nights'] = op_days * get_safe_value(expenses.get('avail_rooms', 1))
    
    metrics['adr'] = (metrics['F_total'] / metrics['E_total']) if metrics['E_total'] > 0 else 0
    metrics['occ'] = (metrics['E_total'] / metrics['avail_nights'] * 100) if metrics['avail_nights'] > 0 else 0
    metrics['alos'] = (metrics['E_total'] / metrics['D_total']) if metrics['D_total'] > 0 else 0
    
    # 5. 소유주 정산
    metrics['room_op_days'] = get_safe_value(expenses.get('room_op_days', 0))
    divisor = get_safe_value(expenses.get('divisor_days', 1))
    metrics['daily_base'] = metrics['distributable'] / divisor if divisor > 0 else 0
    metrics['share_rate'] = get_safe_value(expenses.get('share_rate', 100))
    
    # 최종 배당 (지분율 반영 or 단독) -> 여기서는 단순 배당대상액 표시
    metrics['final_payout'] = metrics['distributable'] 
    
    return metrics

# --------------------------------------------------------------------------
# 4. PDF 생성 (인코딩 해결)
# --------------------------------------------------------------------------
class PDFReport(FPDF):
    def footer(self):
        self.set_y(-40)
        self.set_font("NanumGothic", size=9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, "● 상기 금액은 부가세가 포함되어 있는 금액입니다.", ln=True)
        self.cell(0, 5, "● 문의: ceo@comocasa.kr / 010-1234-5678", ln=True)
        self.ln(5)
        self.set_font("NanumGothic", style='B', size=11)
        self.set_text_color(0, 0, 0)
        self.cell(0, 6, "주식회사 꼬모까사", ln=True)
        self.cell(0, 6, "대표이사 최 효 석", ln=True)

def create_pdf(metrics, expenses, notes, meta, stamp_file=None):
    pdf = PDFReport()
    pdf.add_page()
    
    font_path = "NanumGothic.ttf"
    if os.path.exists(font_path):
        pdf.add_font("NanumGothic", "", font_path, uni=True)
        pdf.add_font("NanumGothic", "B", font_path, uni=True)
    else:
        return None # 폰트 없음

    # 타이틀
    pdf.set_font("NanumGothic", "B", 22)
    pdf.cell(0, 15, f"꼬모까사 숙박 운영 정산서 : {meta['year']%100}년 {meta['month']}월", ln=True, align='C')
    pdf.set_line_width(0.5)
    pdf.line(10, 30, 200, 30)
    pdf.ln(10)
    
    # 정보
    pdf.set_font("NanumGothic", "", 10)
    pdf.cell(0, 5, f"발행일: {meta['issue_date']}", ln=True)
    pdf.cell(0, 5, f"호실명/소유주: [{meta['room_name']}] / [{meta['owner_name']}]", ln=True)
    pdf.ln(8)
    
    # 테이블 그리기 함수
    def draw_row(c1, c2, c3, c4, fill=False, bold=False):
        pdf.set_font("NanumGothic", "B" if bold else "", 10)
        if fill: pdf.set_fill_color(240, 240, 240)
        pdf.cell(50, 8, str(c1), 1, 0, 'C' if fill else 'L', fill)
        pdf.cell(50, 8, str(c2), 1, 0, 'C' if fill else 'R', fill)
        pdf.cell(30, 8, str(c3), 1, 0, 'C', fill)
        pdf.cell(60, 8, str(c4), 1, 1, 'C' if fill else 'L', fill)

    def fmt(x): return f"{x:,.0f}" if isinstance(x, (int, float)) else x
    def pct(x): return f"{x:.1f}%"

    # 1. Sales
    pdf.set_font("NanumGothic", "B", 12)
    pdf.cell(0, 10, "1. 판매 현황 (Sales Status)", ln=True)
    draw_row("구분", "금액/수치", "단위", "비고", True, True)
    draw_row("판매총액 (VAT포함)", fmt(metrics['F_total']), "원", "")
    draw_row("순매출액", fmt(metrics['G_total']), "원", "")
    draw_row("정산월 가동일", metrics['days_in_month'], "일", "")
    draw_row("가동 박수", fmt(metrics['avail_nights']), "일", "")
    draw_row("판매 박수", fmt(metrics['E_total']), "일", "")
    draw_row("체크인 건수", fmt(metrics['D_total']), "건", "")
    draw_row("ADR (객단가)", fmt(int(metrics['adr'])), "원", "")
    draw_row("OCC (가동률)", f"{metrics['occ']:.1f}", "%", "")
    pdf.ln(5)

    # 2. Detail
    pdf.set_font("NanumGothic", "B", 12)
    pdf.cell(0, 10, "2. 정산 세부 내역", ln=True)
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("NanumGothic", "B", 10)
    pdf.cell(50, 8, "구분", 1, 0, 'C', True)
    pdf.cell(50, 8, "금액", 1, 0, 'C', True)
    pdf.cell(30, 8, "매출 대비", 1, 0, 'C', True)
    pdf.cell(60, 8, "비고", 1, 1, 'C', True)
    
    base = metrics['G_total'] if metrics['G_total'] > 0 else 1
    
    def detail_row(l, v, r, n, bold=False):
        pdf.set_font("NanumGothic", "B" if bold else "", 10)
        pdf.cell(50, 8, l, 1, 0, 'L')
        pdf.cell(50, 8, v, 1, 0, 'R')
        pdf.cell(30, 8, r, 1, 0, 'R')
        pdf.cell(60, 8, n, 1, 1, 'L')

    detail_row("순매출액", fmt(metrics['G_total']), "100.0%", "", True)
    detail_row("총 비용", fmt(metrics['total_expense']), pct(metrics['total_expense']/base*100), "", True)
    
    for k, label in EXPENSE_ITEMS.items():
        val = get_safe_value(expenses[k])
        note = notes.get(k, "")
        if val > 0 or note:
            detail_row(f"  - {label}", fmt(val), pct(val/base*100), note)

    detail_row("순이익", fmt(metrics['net_profit']), pct(metrics['net_profit']/base*100), "차감전", True)
    detail_row("위탁 수수료", fmt(metrics['commission']), pct(metrics['commission']/base*100), "20%", True)
    detail_row("배당 대상 순이익", fmt(metrics['distributable']), pct(metrics['distributable']/base*100), "", True)
    pdf.ln(5)

    # 3. Owner
    pdf.set_font("NanumGothic", "B", 12)
    pdf.cell(0, 10, "3. 소유주 정산", ln=True)
    draw_row("구분", "내용", "단위", "", True, True)
    draw_row("배당 대상 순이익", fmt(metrics['distributable']), "원", "")
    draw_row("호실 가동 일수", metrics['room_op_days'], "일", "")
    draw_row("배당 기준 일액", fmt(int(metrics['daily_base'])), "원", "")
    draw_row("지분율", f"{metrics['share_rate']}%", "%", "")
    
    # 도장
    if stamp_file:
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(stamp_file.getvalue())
            tmp_path = tmp.name
        pdf.image(tmp_path, x=75, y=265, w=15)
        os.unlink(tmp_path)
        
    return bytes(pdf.output())

# --------------------------------------------------------------------------
# 5. 메인 UI
# --------------------------------------------------------------------------
def main():
    init_session_state()
    
    if st.session_state.current_page == 'input':
        render_input_page()
    else:
        render_report_page()

def render_input_page():
    st.markdown('<div class="main-title">COMO CASA 정산 시스템 (Admin)</div>', unsafe_allow_html=True)
    
    # 메타 정보
    with st.expander("📝 기본 정보 (발행일, 소유주)", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        st.session_state.meta_info['year'] = c1.number_input("년도", value=st.session_state.meta_info['year'])
        st.session_state.meta_info['month'] = c2.number_input("월", value=st.session_state.meta_info['month'])
        st.session_state.meta_info['room_name'] = c3.text_input("호실명", value=st.session_state.meta_info['room_name'])
        st.session_state.meta_info['owner_name'] = c4.text_input("소유주", value=st.session_state.meta_info['owner_name'])
        
        c5, c6 = st.columns(2)
        st.session_state.meta_info['issue_date'] = c5.text_input("발행일", value=st.session_state.meta_info['issue_date'])
        st.session_state['stamp_file'] = c6.file_uploader("직인 이미지", type=['png'])

    st.markdown("### 1. OTA 매출 입력")
    # 합계 미리보기
    curr = st.session_state.ota_df.copy()
    curr[COLS["H"]] = curr[COLS["F"]] - curr[COLS["G"]]
    sums = curr.sum(numeric_only=True)
    st.info(f"💰 매출 합계: {sums[COLS['F']]:,.0f}원  |  입금 합계: {sums[COLS['G']]:,.0f}원")
    
    edited = st.data_editor(
        curr, 
        use_container_width=True, 
        hide_index=True,
        num_rows="fixed",
        column_config={
            COLS["OTA"]: st.column_config.TextColumn("플랫폼", disabled=True),
            COLS["D"]: st.column_config.NumberColumn("체크인", format="%.0f"),
            COLS["E"]: st.column_config.NumberColumn("숙박일수", format="%.0f"),
            COLS["F"]: st.column_config.NumberColumn("총매출", format="%.0f"),
            COLS["G"]: st.column_config.NumberColumn("입금액", format="%.0f"),
            COLS["H"]: st.column_config.NumberColumn("수수료(자동)", format="%.0f", disabled=True),
        }
    )
    
    st.divider()
    st.markdown("### 2. 비용 및 운영 정보 (콤마 자동 적용)")
    
    # [핵심 수정] 비용 입력란: text_input 사용 + 콤마 포맷팅
    for key, label in EXPENSE_ITEMS.items():
        c1, c2 = st.columns([1, 2])
        
        # 1. 현재 저장된 정수값을 "10,000" 문자열로 변환하여 표시
        current_val = st.session_state.expenses[key]
        display_val = format_comma(current_val) if current_val != 0 else ""
        
        # 2. 텍스트 입력 (입력 시에는 문자열)
        new_val_str = c1.text_input(
            f"{label} (금액)", 
            value=display_val, 
            key=f"in_{key}",
            placeholder="0"
        )
        
        # 3. 입력된 문자열에서 콤마 제거 후 정수로 변환하여 저장
        st.session_state.expenses[key] = parse_comma_int(new_val_str)
        
        # 4. 비고란
        note = c2.text_input(f"{label} 비고", value=st.session_state.expense_notes.get(key, ""), key=f"nt_{key}")
        st.session_state.expense_notes[key] = note
    
    st.markdown("#### ⚙️ 추가 운영 지표")
    col_a, col_b, col_c = st.columns(3)
    # 여기도 콤마 적용 가능하지만, 일수/비율 등은 그냥 숫자가 편할 수 있어 number_input 유지하되 텍스트로 변경 가능
    # 요청사항은 "입력 박스" 전반이므로 여기도 적용하는 것이 좋음.
    
    def input_comma(label, key):
        val = st.session_state.expenses.get(key, 0)
        disp = format_comma(val) if val != 0 else ""
        new_s = st.text_input(label, value=disp, key=f"k_{key}")
        st.session_state.expenses[key] = parse_comma_int(new_s)

    with col_a: input_comma("정산월 일수", 'operating_days')
    with col_b: input_comma("운영 객실 수", 'avail_rooms')
    with col_c: input_comma("해당 호실 가동일", 'room_op_days')
    
    col_d, col_e = st.columns(2)
    with col_d: input_comma("배당 분모 (전체 가동일)", 'divisor_days')
    with col_e: input_comma("지분율 (%)", 'share_rate')

    st.divider()
    if st.button("📊 정산서 생성", type="primary", use_container_width=True):
        st.session_state.ota_df = edited
        st.session_state.current_page = 'report'
        st.rerun()

def render_report_page():
    if st.button("⬅ 수정 화면", type="secondary"):
        st.session_state.current_page = 'input'
        st.rerun()
        
    metrics = calculate_metrics(st.session_state.ota_df, st.session_state.expenses)
    meta = st.session_state.meta_info
    
    # -------------------------------------------------------------
    # [핵심 수정] HTML 리포트 생성 (하나의 문자열로 완벽하게 조립)
    # -------------------------------------------------------------
    def fmt(x): return f"{x:,.0f}" if isinstance(x, (int, float)) else x
    def pct(x): return f"{x:.1f}%"
    base = metrics['G_total'] if metrics['G_total'] > 0 else 1

    # HTML 조립 시작 (f-string 하나로 묶거나, 리스트 join 사용)
    # 여기서는 가독성을 위해 리스트에 담고 join 합니다.
    html_parts = []
    
    # 1. 헤더
    html_parts.append(f"""
    <div class="report-wrapper">
        <div class="report-title">
            꼬모까사 숙박 운영 정산서 : {meta['year']%100}년 {meta['month']}월
        </div>
        <div style="font-size: 14px; margin-bottom: 20px;">
            <b>발행일:</b> {meta['issue_date']}<br>
            <b>호실명/소유주:</b> [{meta['room_name']}] / [{meta['owner_name']}]
        </div>
    """)
    
    # 2. 판매 현황 테이블
    html_parts.append(f"""
        <div class="section-header">1. 판매 현황 (Sales Status)</div>
        <table class="styled-table">
            <thead>
                <tr>
                    <th width="30%">구분</th> <th width="30%">금액/수치</th> <th width="15%">단위</th> <th width="25%">비고</th>
                </tr>
            </thead>
            <tbody>
                <tr><td>판매총액 (VAT포함)</td> <td class="text-right">{fmt(metrics['F_total'])}</td> <td class="text-center">원</td> <td></td></tr>
                <tr><td>순매출액</td> <td class="text-right">{fmt(metrics['G_total'])}</td> <td class="text-center">원</td> <td></td></tr>
                <tr><td>정산월 가동일</td> <td class="text-right">{metrics['days_in_month']}</td> <td class="text-center">일</td> <td></td></tr>
                <tr><td>가동 박수 (Avail)</td> <td class="text-right">{fmt(metrics['avail_nights'])}</td> <td class="text-center">일</td> <td></td></tr>
                <tr><td>판매 박수 (Booked)</td> <td class="text-right">{fmt(metrics['E_total'])}</td> <td class="text-center">일</td> <td></td></tr>
                <tr><td>체크인 건수</td> <td class="text-right">{fmt(metrics['D_total'])}</td> <td class="text-center">건</td> <td></td></tr>
                <tr><td>ADR (객단가)</td> <td class="text-right">{fmt(metrics['adr'])}</td> <td class="text-center">원</td> <td></td></tr>
                <tr><td>OCC (가동률)</td> <td class="text-right">{metrics['occ']:.1f}</td> <td class="text-center">%</td> <td></td></tr>
            </tbody>
        </table>
    """)
    
    # 3. 상세 내역 테이블
    html_parts.append(f"""
        <div class="section-header">2. 정산 세부 내역 (Detail)</div>
        <table class="styled-table">
            <thead>
                <tr>
                    <th>구분</th> <th>금액</th> <th>매출 대비</th> <th>비고</th>
                </tr>
            </thead>
            <tbody>
                <tr><td class="bold">순매출액</td> <td class="text-right bold">{fmt(metrics['G_total'])}</td> <td class="text-right">100.0%</td> <td></td></tr>
                <tr><td class="bold">총 비용</td> <td class="text-right bold">{fmt(metrics['total_expense'])}</td> <td class="text-right">{pct(metrics['total_expense']/base*100)}</td> <td></td></tr>
    """)
    
    # 비용 항목 루프
    for key, label in EXPENSE_ITEMS.items():
        val = get_safe_value(st.session_state.expenses[key])
        note = st.session_state.expense_notes.get(key, "")
        if val > 0 or note:
            html_parts.append(f"""
                <tr><td>{label}</td> <td class="text-right">{fmt(val)}</td> <td class="text-right">{pct(val/base*100)}</td> <td>{note}</td></tr>
            """)
            
    # 이익 및 수수료
    html_parts.append(f"""
                <tr><td class="bold bg-gray">순이익 (차감전)</td> <td class="text-right bold bg-gray">{fmt(metrics['net_profit'])}</td> <td class="text-right bg-gray">{pct(metrics['net_profit']/base*100)}</td> <td class="bg-gray"></td></tr>
                <tr><td class="bold">위탁 수수료</td> <td class="text-right bold">{fmt(metrics['commission'])}</td> <td class="text-right">{pct(metrics['commission']/base*100)}</td> <td>20%</td></tr>
                <tr><td class="bold bg-gray">배당 대상 순이익</td> <td class="text-right bold bg-gray">{fmt(metrics['distributable'])}</td> <td class="text-right bg-gray">{pct(metrics['distributable']/base*100)}</td> <td class="bg-gray"></td></tr>
            </tbody>
        </table>
    """)
    
    # 4. 소유주 정산
    html_parts.append(f"""
        <div class="section-header">3. 소유주 정산 (Owner Distribution)</div>
        <table class="styled-table">
            <thead>
                <tr><th>구분</th> <th>내용</th> <th>단위</th></tr>
            </thead>
            <tbody>
                <tr><td>배당 대상 순이익</td> <td class="text-right">{fmt(metrics['distributable'])}</td> <td class="text-center">원</td></tr>
                <tr><td>호실 가동 일수</td> <td class="text-right">{metrics['room_op_days']}</td> <td class="text-center">일</td></tr>
                <tr><td>배당 기준 일액</td> <td class="text-right">{fmt(int(metrics['daily_base']))}</td> <td class="text-center">원</td></tr>
                <tr><td>지분율</td> <td class="text-right">{metrics['share_rate']}%</td> <td class="text-center">%</td></tr>
                <tr><td class="bold">최종 배당금</td> <td class="text-right bold"></td> <td class="text-center">원</td></tr>
            </tbody>
        </table>
        
        <div style="margin-top: 30px; font-size: 13px; color: #555;">
            ● 상기 금액은 부가세가 포함된 금액입니다.<br>
            ● 문의사항: ceo@comocasa.kr
        </div>
        <div style="margin-top: 30px; font-weight: bold; font-size: 16px;">
            주식회사 꼬모까사<br>대표이사 최 효 석 (인)
        </div>
    </div>
    """)
    
    # 최종 렌더링 (단 한 번의 호출)
    full_html = "\n".join(html_parts)
    st.markdown(full_html, unsafe_allow_html=True)
    
    # PDF 다운로드
    st.divider()
    stamp_img = st.session_state.get('stamp_file')
    try:
        pdf_bytes = create_pdf(metrics, st.session_state.expenses, st.session_state.expense_notes, meta, stamp_img)
        if pdf_bytes:
            st.download_button("📄 PDF 정산서 다운로드", pdf_bytes, "report.pdf", "application/pdf", type="primary")
    except Exception as e:
        st.error(f"PDF 생성 오류: {e}")

if __name__ == "__main__":
    main()
