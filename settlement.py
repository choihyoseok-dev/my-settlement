import streamlit as st
import pandas as pd
import json
from fpdf import FPDF
import os
from datetime import datetime

# --------------------------------------------------------------------------
# 1. 설정 및 스타일 (CSS) - 블루 테마 및 콤마 적용 스타일
# --------------------------------------------------------------------------
st.set_page_config(page_title="COMO CASA 정산 시스템", layout="wide", page_icon="🏢")

st.markdown("""
    <style>
    /* 타이틀 스타일 */
    .main-title { font-size: 32px; font-weight: 800; color: #1E3A8A; border-bottom: 3px solid #1E3A8A; padding-bottom: 10px; margin-bottom: 20px; }
    .sub-title { font-size: 20px; font-weight: 700; color: #1E3A8A; margin-top: 20px; margin-bottom: 10px; border-bottom: 1px solid #ddd; }
    
    /* 입력창 콤마 표시 스타일 (Text Input) */
    div[data-testid="stTextInput"] input { text-align: right; }
    
    /* 리포트 테이블 스타일 (Streamlit DataFrame용) */
    .stDataFrame table { width: 100%; }
    .stDataFrame th { background-color: #f2f2f2 !important; color: #333 !important; }
    .bg-gray { background-color: #f9f9f9 !important; }
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

def str_to_int(val):
    """콤마가 포함된 문자열 또는 None을 정수로 변환"""
    if val is None or val == "": return 0
    if isinstance(val, (int, float)): return int(val)
    try:
        return int(str(val).replace(',', '').strip())
    except:
        return 0

def int_to_str(val):
    """정수를 콤마가 있는 문자열로 변환 (표시용)"""
    try:
        return f"{int(val):,}"
    except:
        return "0"

# --------------------------------------------------------------------------
# 3. 상태 초기화 및 계산 로직 (변경 없음)
# --------------------------------------------------------------------------
def init_session_state():
    if 'ota_df' not in st.session_state:
        data = {c: [0]*len(OTA_LIST) if c != "OTA" else OTA_LIST for c in COLS.values()}
        st.session_state.ota_df = pd.DataFrame(data)

    if 'expenses' not in st.session_state:
        st.session_state.expenses = {key: 0 for key in EXPENSE_ITEMS.keys()} # 기본값을 0으로 설정
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
    # 숫자형 데이터로 계산 (이 로직은 이전과 동일하게 유지)
    calc_df = df.copy()
    calc_df[COLS["H"]] = calc_df[COLS["F"]] - calc_df[COLS["G"]]
    sums = calc_df.sum(numeric_only=True)
    
    metrics = {}
    metrics['F_total'] = sums.get(COLS["F"], 0)
    metrics['G_total'] = sums.get(COLS["G"], 0)
    metrics['E_total'] = sums.get(COLS["E"], 0)
    metrics['D_total'] = sums.get(COLS["D"], 0)
    
    metrics['total_expense'] = sum(expenses[k] for k in EXPENSE_ITEMS.keys())
    
    metrics['net_profit'] = metrics['G_total'] - metrics['total_expense']
    metrics['commission'] = int(metrics['net_profit'] * 0.20)
    metrics['distributable'] = int(metrics['net_profit'] - metrics['commission'])
    
    op_days = expenses.get('operating_days', 30)
    metrics['days_in_month'] = op_days
    metrics['avail_nights'] = op_days * expenses.get('avail_rooms', 1)
    
    metrics['adr'] = (metrics['F_total'] / metrics['E_total']) if metrics['E_total'] > 0 else 0
    metrics['occ'] = (metrics['E_total'] / metrics['avail_nights'] * 100) if metrics['avail_nights'] > 0 else 0
    metrics['alos'] = (metrics['E_total'] / metrics['D_total']) if metrics['D_total'] > 0 else 0
    
    metrics['room_op_days'] = expenses.get('room_op_days', 0)
    divisor = expenses.get('divisor_days', 1)
    metrics['daily_base'] = metrics['distributable'] / divisor if divisor > 0 else 0
    metrics['share_rate'] = expenses.get('share_rate', 100)
    metrics['final_payout'] = metrics['distributable'] 
    
    return metrics

# --------------------------------------------------------------------------
# 6. PDF 생성 함수 (변경 없음)
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
        font_family = "NanumGothic"
    else:
        font_family = "Arial"

    pdf.set_font(font_family, "B", 22)
    pdf.cell(0, 15, f"꼬모까사 숙박 운영 정산서 : {meta['year']%100}년 {meta['month']}월", ln=True, align='C')
    pdf.set_line_width(0.5)
    pdf.line(10, 30, 200, 30)
    pdf.ln(10)
    
    pdf.set_font(font_family, "", 10)
    pdf.cell(0, 5, f"발행일: {meta['issue_date']}", ln=True)
    pdf.cell(0, 5, f"호실명/소유주: [{meta['room_name']}] / [{meta['owner_name']}]", ln=True)
    pdf.ln(8)
    
    def draw_row(c1, c2, c3, c4, fill=False, bold=False):
        pdf.set_font("NanumGothic", "B" if bold else "", 10)
        if fill: pdf.set_fill_color(240, 240, 240)
        pdf.cell(50, 8, c1, 1, 0, 'C' if fill else 'L', fill)
        pdf.cell(50, 8, c2, 1, 0, 'C' if fill else 'R', fill)
        pdf.cell(30, 8, c3, 1, 0, 'C', fill)
        pdf.cell(60, 8, c4, 1, 1, 'C' if fill else 'L', fill)

    def fmt(x): return f"{x:,.0f}" if isinstance(x, (int, float)) else x
    def pct(x): return f"{x:.1f}%"

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
        val = expenses[k]
        note = notes.get(k, "")
        if val > 0 or note:
            detail_row(f"  - {label}", fmt(val), pct(val/base*100), note)

    detail_row("순이익", fmt(metrics['net_profit']), pct(metrics['net_profit']/base*100), "차감전", True)
    detail_row("위탁 수수료", fmt(metrics['commission']), pct(metrics['commission']/base*100), "20%", True)
    detail_row("배당 대상 순이익", fmt(metrics['distributable']), pct(metrics['distributable']/base*100), "", True)
    pdf.ln(5)

    pdf.set_font("NanumGothic", "B", 12)
    pdf.cell(0, 10, "3. 소유주 정산", ln=True)
    draw_row("구분", "내용", "단위", "", True, True)
    draw_row("배당 대상 순이익", fmt(metrics['distributable']), "원", "")
    draw_row("호실 가동 일수", metrics['room_op_days'], "일", "")
    draw_row("배당 기준 일액", fmt(int(metrics['daily_base'])), "원", "")
    draw_row("지분율", f"{metrics['share_rate']}%", "%", "")
    
    if stamp_file:
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(stamp_file.getvalue())
            tmp_path = tmp.name
        pdf.image(tmp_path, x=75, y=265, w=15)
        os.unlink(tmp_path)
        
    return bytes(pdf.output())

# --------------------------------------------------------------------------
# 6. 메인 UI 렌더링 함수
# --------------------------------------------------------------------------
def main():
    init_session_state()
    if st.session_state.current_page == 'input':
        render_input_page()
    else:
        render_report_page()

def render_input_page():
    st.markdown('<div class="main-title">COMO CASA 정산 시스템 (Admin)</div>', unsafe_allow_html=True)
    
    with st.expander("📝 기본 정보 (발행일, 소유주)", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        st.session_state.meta_info['year'] = c1.number_input("년도", value=st.session_state.meta_info['year'])
        st.session_state.meta_info['month'] = c2.number_input("월", value=st.session_state.meta_info['month'])
        st.session_state.meta_info['room_name'] = c3.text_input("호실명", value=st.session_state.meta_info['room_name'])
        st.session_state.meta_info['owner_name'] = c4.text_input("소유주", value=st.session_state.meta_info['owner_name'])
        
        c5, c6 = st.columns(2)
        st.session_state.meta_info['issue_date'] = c5.text_input("발행일", value=st.session_state.meta_info['issue_date'])
        st.session_state['stamp_file'] = c6.file_uploader("직인 이미지", type=['png'])

    st.markdown('<div class="sub-title">1. OTA 매출 입력</div>', unsafe_allow_html=True)
    
    # **실시간 계산 및 콤마 적용 로직**
    current_df = st.session_state.ota_df.copy()
    
    # H열 계산 (숫자 상태에서)
    current_df[COLS["H"]] = current_df[COLS["F"]] - current_df[COLS["G"]]
    sums = current_df.sum(numeric_only=True)
    
    # 합계 표시용 DF (문자열 콤마 적용)
    total_data = pd.DataFrame([{
        COLS["OTA"]: "합 계",
        COLS["D"]: int_to_str(sums[COLS['D']]),
        COLS["E"]: int_to_str(sums[COLS['E']]),
        COLS["F"]: int_to_str(sums[COLS['F']]),
        COLS["G"]: int_to_str(sums[COLS['G']]),
        COLS["H"]: int_to_str(sums[COLS['H']])
    }])
    
    st.markdown('<div class="total-table-container">▼ 전체 합계 (자동 계산)</div>', unsafe_allow_html=True)
    st.dataframe(total_data, use_container_width=True, hide_index=True)

    # 에디터 표시용 DF (문자열로 변환)
    display_df = current_df.copy()
    for col in [COLS["D"], COLS["E"], COLS["F"], COLS["G"], COLS["H"]]:
        display_df[col] = display_df[col].apply(int_to_str)

    # 데이터 에디터 (가장 중요: on_change 제거, key 사용, TextColumn)
    edited_df_str = st.data_editor(
        display_df,
        key="ota_editor_final", 
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            COLS["OTA"]: st.column_config.TextColumn("플랫폼", disabled=True),
            COLS["D"]: st.column_config.TextColumn("체크인", width="small"),
            COLS["E"]: st.column_config.TextColumn("숙박일수", width="small"),
            COLS["F"]: st.column_config.TextColumn("총매출액", width="medium"),
            COLS["G"]: st.column_config.TextColumn("입금액", width="medium"),
            COLS["H"]: st.column_config.TextColumn("수수료(자동)", width="medium", disabled=True),
        }
    )
    
    # 변경 감지 및 세션 업데이트 (가장 강력한 버그 해결 방법)
    if not display_df.equals(edited_df_str):
        new_data = {}
        for col in numeric_df.columns:
            if col == COLS["OTA"]:
                new_data[col] = edited_df_str[col]
            else:
                new_data[col] = edited_df_str[col].apply(str_to_int)
        
        st.session_state.ota_df = pd.DataFrame(new_data)
        st.rerun()

    st.markdown('<div class="sub-title">2. 비용 및 운영 정보 (콤마 자동 적용)</div>', unsafe_allow_html=True)
    
    # 비용 입력 (세로 배치 & 콤마 처리)
    for key, label in EXPENSE_ITEMS.items():
        c1, c2 = st.columns([1, 2])
        curr_val = st.session_state.expenses[key]
        disp_val = int_to_str(curr_val) if curr_val != 0 else ""
        
        new_val_str = c1.text_input(f"{label} (금액)", value=disp_val, key=f"in_{key}", placeholder="0")
        st.session_state.expenses[key] = str_to_int(new_val_str)
        
        note = c2.text_input(f"{label} 비고", value=st.session_state.expense_notes.get(key, ""), key=f"nt_{key}")
        st.session_state.expense_notes[key] = note
    
    st.markdown("#### ⚙️ 추가 운영 지표")
    col_a, col_b, col_c = st.columns(3)
    
    # 콤마 필드 함수 재사용 (width 조정)
    def input_comma_field(label, key, col):
        val = st.session_state.expenses.get(key, 0)
        disp = int_to_str(val) if val != 0 else ""
        new_s = col.text_input(label, value=disp, key=f"k_{key}")
        st.session_state.expenses[key] = str_to_int(new_s)

    input_comma_field("정산월 일수", 'operating_days', col_a)
    input_comma_field("운영 객실 수", 'avail_rooms', col_b)
    input_comma_field("호실 가동일", 'room_op_days', col_c)
    
    col_d, col_e = st.columns(2)
    input_comma_field("배당 분모", 'divisor_days', col_d)
    input_comma_field("지분율 (%)", 'share_rate', col_e)

    st.divider()
    if st.button("📊 정산서 생성", type="primary", use_container_width=True):
        st.session_state.current_page = 'report'
        st.rerun()

def render_report_page():
    if st.button("⬅ 수정 화면", type="secondary"):
        st.session_state.current_page = 'input'
        st.rerun()
        
    metrics = calculate_metrics(st.session_state.ota_df, st.session_state.expenses)
    meta = st.session_state.meta_info
    
    # -------------------------------------------------------------
    # Streamlit 네이티브 방식 (HTML 대신)으로 리포트 구성
    # -------------------------------------------------------------
    
    # 1. 메인 타이틀 (Streamlit 기본 위젯 사용)
    st.markdown('<div class="main-title">꼬모까사 숙박 운영 정산서 : 26년 2월</div>', unsafe_allow_html=True)
    
    st.markdown(f"""
        <div style="font-size: 14px; margin-bottom: 20px;">
            <b>발행일:</b> {meta['issue_date']}<br>
            <b>호실명/소유주:</b> [{meta['room_name']}] / [{meta['owner_name']}]
        </div>
    """, unsafe_allow_html=True)
    
    # 2. KPI
    st.markdown('<div class="sub-title">1. 판매 현황 (Sales Status)</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("판매총액", f"{metrics['F_total']:,} 원")
    c2.metric("순매출액", f"{metrics['G_total']:,} 원")
    c3.metric("가동일수", f"{metrics['days_in_month']} 일")
    c4.metric("ADR", f"{metrics['adr']:,.0f} 원")

    st.markdown("<br>", unsafe_allow_html=True)

    # 3. 상세 내역 테이블 (Streamlit DataFrame 사용)
    st.markdown('<div class="sub-title">2. 정산 세부 내역 (Detail)</div>', unsafe_allow_html=True)
    
    base = metrics['G_total'] if metrics['G_total'] > 0 else 1
    rows = []
    
    def fmt(x): return f"{x:,.0f}" if isinstance(x, (int, float)) else x
    def pct(x): return f"{x:.1f}%"
    
    rows.append(["순매출액", fmt(metrics['G_total']), "100.0%", ""])
    rows.append(["총 비용", fmt(metrics['total_expense']), pct(metrics['total_expense']/base*100), ""])
    
    for key, label in EXPENSE_ITEMS.items():
        val = st.session_state.expenses[key]
        note = st.session_state.expense_notes.get(key, "")
        if val > 0 or note:
            rows.append([f"  - {label}", fmt(val), pct(val/base*100), note])
            
    rows.append(["순이익 (차감전)", fmt(metrics['net_profit']), pct(metrics['net_profit']/base*100), ""])
    rows.append(["위탁 수수료", fmt(metrics['commission']), pct(metrics['commission']/base*100), "20%"])
    rows.append(["배당 대상 순이익", fmt(metrics['distributable']), pct(metrics['distributable']/base*100), ""])

    df_res = pd.DataFrame(rows, columns=["구분", "금액", "비율", "비고"])
    
    # 테이블 표시 (스타일링 클래스 적용)
    st.dataframe(
        df_res,
        use_container_width=True,
        hide_index=True,
        column_config={
            "구분": st.column_config.TextColumn("구분"),
            "금액": st.column_config.TextColumn("금액", width="small"),
            "비율": st.column_config.TextColumn("비율", width="small"),
            "비고": st.column_config.TextColumn("비고"),
        }
    )

    st.markdown("<br>", unsafe_allow_html=True)
    st.info(f"### 💰 최종 배당금: {metrics['final_payout']:,} 원")
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 4. 다운로드 (PDF 출력 로직 유지)
    st.markdown('<div class="sub-title">3. 리포트 다운로드</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    
    with c1:
        save_data = {
            "ota": st.session_state.ota_df.to_dict('records'),
            "exp": st.session_state.expenses,
            "notes": st.session_state.expense_notes
        }
        st.download_button("💾 데이터 백업 (.json)", json.dumps(save_data, default=str), "comocasa_data.json")
        
    with c2:
        try:
            stamp_img = st.session_state.get('stamp_file')
            pdf_bytes = create_pdf(metrics, st.session_state.expenses, st.session_state.expense_notes, meta, stamp_img)
            if pdf_bytes:
                st.download_button("📄 PDF 정산서 다운로드", pdf_bytes, "comocasa_report.pdf", "application/pdf", type="primary")
        except Exception as e:
            st.error(f"PDF 생성 오류: {e}")

if __name__ == "__main__":
    main()
