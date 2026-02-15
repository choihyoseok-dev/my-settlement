import streamlit as st
import pandas as pd
import json
from fpdf import FPDF
import os

# --------------------------------------------------------------------------
# 1. 설정 및 디자인 (CSS)
# --------------------------------------------------------------------------
st.set_page_config(page_title="COMO CASA 정산 시스템", layout="wide", page_icon="🏠")

st.markdown("""
    <style>
    /* 1. 메인 타이틀 (파란색, 볼드, 이모지 제거) */
    .main-title {
        font-family: 'Malgun Gothic', sans-serif;
        font-size: 36px;
        font-weight: 800;
        color: #1E3A8A; /* 짙은 네이비 블루 */
        margin-bottom: 5px;
    }
    .sub-title {
        font-family: 'Malgun Gothic', sans-serif;
        font-size: 24px;
        font-weight: 700;
        color: #1E3A8A;
        margin-top: 20px;
        margin-bottom: 10px;
        border-bottom: 2px solid #1E3A8A;
        padding-bottom: 5px;
    }

    /* 2. 합계 테이블 배경색 (회색) */
    .total-table-container {
        background-color: #F3F4F6;
        padding: 10px;
        border-radius: 5px;
        border: 1px solid #D1D5DB;
        margin-bottom: 15px;
        font-weight: bold;
    }

    /* 3. 버튼 스타일 */
    div.stButton > button[kind="primary"] {
        background-color: #2563EB !important;
        border-color: #2563EB !important;
        color: white !important;
        font-weight: bold;
    }
    div.stButton > button[kind="secondary"] {
        background-color: white !important;
        border: 1px solid #2563EB !important;
        color: #2563EB !important;
    }

    /* 4. 입력창 포커스 및 테이블 */
    input:focus {
        border-color: #2563EB !important;
        box-shadow: 0 0 0 1px #2563EB !important;
    }
    
    /* 5. A4 미리보기 컨테이너 */
    .a4-preview {
        border: 1px solid #ddd;
        padding: 40px;
        background-color: white;
        margin-bottom: 20px;
    }
    
    /* 6. 상세내역 테이블 (스크롤 제거용 스타일) */
    table {
        width: 100%;
    }
    th {
        background-color: #F3F4F6 !important;
        color: #333 !important;
        font-weight: bold !important;
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
        data = {
            COLS["OTA"]: OTA_LIST,
            COLS["D"]: [0] * len(OTA_LIST),
            COLS["E"]: [0] * len(OTA_LIST),
            COLS["F"]: [0] * len(OTA_LIST),
            COLS["G"]: [0] * len(OTA_LIST),
            COLS["H"]: [0] * len(OTA_LIST)
        }
        st.session_state.ota_df = pd.DataFrame(data)

    if 'expenses' not in st.session_state:
        st.session_state.expenses = {key: None for key in EXPENSE_ITEMS.keys()}
        st.session_state.expenses['operating_days'] = None

    if 'expense_notes' not in st.session_state:
        st.session_state.expense_notes = {key: "" for key in EXPENSE_ITEMS.keys()}

    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'input'

def get_safe_value(value):
    return value if value is not None else 0

def calculate_metrics(df, expenses):
    # 계산용 복사본 (H = F - G 자동 계산)
    calc_df = df.copy()
    calc_df[COLS["H"]] = calc_df[COLS["F"]] - calc_df[COLS["G"]]
    
    sums = calc_df.sum(numeric_only=True)
    
    F_total = sums.get(COLS["F"], 0)
    G_total = sums.get(COLS["G"], 0)
    E_total = sums.get(COLS["E"], 0)
    
    total_expense = sum(get_safe_value(v) for k, v in expenses.items() if k != 'operating_days')
    
    net_profit = G_total - total_expense
    commission = int(net_profit * 0.20)
    final_payout = int(net_profit - commission)
    
    adr = (F_total / E_total) if E_total > 0 else 0
    op_days = get_safe_value(expenses.get('operating_days'))
    
    return {
        "F_total": F_total,
        "G_total": G_total,
        "total_expense": total_expense,
        "net_profit": net_profit,
        "commission": commission,
        "final_payout": final_payout,
        "adr": adr,
        "op_days": op_days
    }

def create_pdf(metrics, expenses_dict, expense_notes):
    pdf = FPDF()
    pdf.add_page()
    
    # [필수] 한글 폰트 설정 (없으면 경고 없이 깨질 수 있음)
    font_path = "NanumGothic.ttf"
    if os.path.exists(font_path):
        pdf.add_font("NanumGothic", "", font_path, uni=True)
        font_family = "NanumGothic"
    else:
        font_family = "Arial" # 한글 깨짐

    # 타이틀
    pdf.set_font(font_family, style='B', size=20)
    pdf.set_text_color(30, 58, 138) # #1E3A8A (Blue)
    pdf.cell(0, 15, "꼬모까사 위탁숙박 정산서", ln=True, align='C')
    pdf.ln(10)

    pdf.set_text_color(0, 0, 0) # Black reset

    # 헬퍼 함수
    def write_section_title(title):
        pdf.set_font(font_family, style='B', size=12)
        pdf.set_text_color(30, 58, 138)
        pdf.cell(0, 10, title, ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font(font_family, size=10)

    def write_row(c1, c2, c3, c4=""):
        pdf.cell(70, 8, c1, border=1)
        pdf.cell(35, 8, c2, border=1, align='R')
        pdf.cell(25, 8, c3, border=1, align='R')
        pdf.cell(60, 8, c4, border=1)
        pdf.ln()

    # 1. Summary
    write_section_title("1. 판매 현황 (Summary)")
    
    pdf.cell(95, 8, f"판매총액: {metrics['F_total']:,} 원", border=1)
    pdf.cell(95, 8, f"순매출액: {metrics['G_total']:,} 원", border=1)
    pdf.ln()
    pdf.cell(95, 8, f"객단가(ADR): {metrics['adr']:,.0f} 원", border=1)
    pdf.cell(95, 8, f"가동일수: {metrics['op_days']} 일", border=1)
    pdf.ln(10)

    # 2. Detail
    write_section_title("2. 정산 세부 내역 (Detail)")
    
    # 헤더
    pdf.set_fill_color(243, 244, 246) # Gray background
    pdf.cell(70, 8, "구분", 1, 0, 'C', True)
    pdf.cell(35, 8, "금액", 1, 0, 'C', True)
    pdf.cell(25, 8, "비율", 1, 0, 'C', True)
    pdf.cell(60, 8, "비고", 1, 1, 'C', True)

    base = metrics['G_total'] if metrics['G_total'] > 0 else 1
    
    # 내용
    write_row("순매출액", f"{metrics['G_total']:,}", "100.0%")
    write_row("총비용 (지출)", f"{metrics['total_expense']:,}", f"{metrics['total_expense']/base*100:.1f}%")
    
    for key, label in EXPENSE_ITEMS.items():
        val = get_safe_value(expenses_dict[key])
        note = expense_notes.get(key, "")
        if val > 0 or note:
            write_row(f"  - {label}", f"{val:,}", f"{val/base*100:.1f}%", note)
            
    write_row("순이익 (차감전)", f"{metrics['net_profit']:,}", f"{metrics['net_profit']/base*100:.1f}%", "입금액 - 비용")
    write_row("위탁수수료 (20%)", f"{metrics['commission']:,}", f"{metrics['commission']/base*100:.1f}%", "순이익의 20%")
    
    pdf.set_font(font_family, style='B', size=11)
    pdf.set_fill_color(230, 240, 255) # Blue tint
    pdf.cell(70, 10, "최종 배당금", 1, 0, 'L', True)
    pdf.cell(35, 10, f"{metrics['final_payout']:,}", 1, 0, 'R', True)
    pdf.cell(25, 10, f"{metrics['final_payout']/base*100:.1f}%", 1, 0, 'R', True)
    pdf.cell(60, 10, "최종 지급액", 1, 1, 'L', True)

    # [중요] PDF 인코딩 오류 수정: bytearray를 직접 리턴
    return bytes(pdf.output())

# --------------------------------------------------------------------------
# 4. 메인 화면
# --------------------------------------------------------------------------
def main():
    init_session_state()

    if st.session_state.current_page == 'input':
        render_input_page()
    else:
        render_report_page()

def render_input_page():
    # [타이틀]
    st.markdown('<div class="main-title">COMO CASA 정산 시스템</div>', unsafe_allow_html=True)

    # ---------------------------------------------------------
    # 1. OTA 매출 입력
    # ---------------------------------------------------------
    st.markdown('<div class="sub-title">1. 플랫폼(OTA)별 매출 입력</div>', unsafe_allow_html=True)
    st.caption("※ F(총매출액)와 G(입금액)를 입력하면 H(플랫폼수수료)가 자동 계산됩니다.")

    # [자동 계산 로직]
    # 사용자가 입력한 데이터(st.session_state.ota_df)를 바탕으로
    # H열을 계산한 뒤, 이 display_df를 에디터에 보여줍니다.
    # 사용자가 F, G를 수정하면 다음 rerun 때 H가 업데이트되어 보입니다.
    current_df = st.session_state.ota_df.copy()
    current_df[COLS["H"]] = current_df[COLS["F"]] - current_df[COLS["G"]]
    
    # 합계 계산
    totals = current_df.sum(numeric_only=True)
    
    # [합계 테이블 - 회색 배경 적용]
    st.markdown('<div class="total-table-container">▼ 전체 합계 (자동 계산)</div>', unsafe_allow_html=True)
    
    total_data = pd.DataFrame([{
        COLS["OTA"]: "합 계",
        COLS["D"]: totals[COLS["D"]],
        COLS["E"]: totals[COLS["E"]],
        COLS["F"]: totals[COLS["F"]],
        COLS["G"]: totals[COLS["G"]],
        COLS["H"]: totals[COLS["H"]]
    }])
    
    # Pandas Styler를 사용하여 배경색(회색) 적용
    st.dataframe(
        total_data.style.format("{:,.0f}", subset=[COLS["D"], COLS["E"], COLS["F"], COLS["G"], COLS["H"]])
                         .set_properties(**{'background-color': '#F3F4F6', 'font-weight': 'bold'}),
        use_container_width=True,
        hide_index=True
    )

    # [데이터 에디터]
    # 계산된 H값이 포함된 current_df를 보여주되, H열은 disabled 처리
    edited_df = st.data_editor(
        current_df,
        key="ota_editor", 
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            COLS["OTA"]: st.column_config.TextColumn("플랫폼", disabled=True),
            COLS["D"]: st.column_config.NumberColumn("체크인(D)", format="%.0f", min_value=0),
            COLS["E"]: st.column_config.NumberColumn("숙박일수(E)", format="%.0f", min_value=0),
            COLS["F"]: st.column_config.NumberColumn("총매출액(F)", format="%.0f", step=1000),
            COLS["G"]: st.column_config.NumberColumn("입금액(G)", format="%.0f", step=1000),
            COLS["H"]: st.column_config.NumberColumn("플랫폼수수료(H)", format="%.0f", disabled=True),
        }
    )

    st.divider()

    # ---------------------------------------------------------
    # 2. 비용 입력
    # ---------------------------------------------------------
    st.markdown('<div class="sub-title">2. 월 운영 비용 및 정보</div>', unsafe_allow_html=True)
    
    # 1줄에 1개씩 세로 배치
    for key, label in EXPENSE_ITEMS.items():
        c1, c2 = st.columns([1, 3])
        
        with c1:
            val = st.number_input(
                f"{label} (금액)",
                value=st.session_state.expenses[key],
                step=10000,
                format="%d",
                key=f"input_{key}"
            )
        with c2:
            note = st.text_input(
                f"{label} 비고",
                value=st.session_state.expense_notes.get(key, ""),
                placeholder="내용 입력",
                key=f"note_{key}",
                label_visibility="visible"
            )
            
        st.session_state.expenses[key] = val
        st.session_state.expense_notes[key] = note
        
    st.markdown("---")
    
    col_small, _ = st.columns([1, 5])
    with col_small:
        op_days = st.number_input(
            "총 가동일수",
            value=st.session_state.expenses['operating_days'],
            min_value=0, max_value=31,
            key="op_days_input"
        )
        st.session_state.expenses['operating_days'] = op_days

    st.markdown("<br>", unsafe_allow_html=True)

    # [저장 버튼]
    if st.button("💾 입력 내용 저장 및 정산서 보기", type="primary", use_container_width=True):
        # H열을 제외한 사용자 입력값(D,E,F,G)만 세션에 업데이트
        # (H는 어차피 계산되는 값이므로 저장할 때 무시하거나, 다음 렌더링 때 다시 계산됨)
        # 여기서는 edited_df 전체를 저장합니다.
        st.session_state.ota_df = edited_df
        st.session_state.current_page = 'report'
        st.rerun()

def render_report_page():
    # 상단 네비게이션
    if st.button("⬅ 수정하러 돌아가기", type="secondary"):
        st.session_state.current_page = 'input'
        st.rerun()
    
    data = calculate_metrics(st.session_state.ota_df, st.session_state.expenses)
    
    # ------------------------------------------------------------------
    # A4 미리보기 영역
    # ------------------------------------------------------------------
    st.markdown('<div class="a4-preview">', unsafe_allow_html=True)
    
    st.markdown('<div class="main-title" style="text-align: center;">꼬모까사 위탁숙박 정산서</div>', unsafe_allow_html=True)
    st.divider()

    # 1. KPI
    st.markdown('<div class="sub-title">1. 판매 현황 (Summary)</div>', unsafe_allow_html=True)
    
    k1, k2 = st.columns(2)
    k1.metric("판매총액", f"{data['F_total']:,} 원")
    k2.metric("순매출액", f"{data['G_total']:,} 원")
    
    k3, k4 = st.columns(2)
    k3.metric("객단가 (ADR)", f"{data['adr']:,.0f} 원")
    k4.metric("가동일수", f"{data['op_days']} 일")

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. 상세 내역 (스크롤 없는 st.table 사용)
    st.markdown('<div class="sub-title">2. 정산 세부 내역 (Detail)</div>', unsafe_allow_html=True)
    
    base = data['G_total'] if data['G_total'] > 0 else 1
    rows = []
    
    def fmt(x): return f"{x:,}"
    def pct(x): return f"{x:.1f}%"
    
    rows.append(["순매출액", fmt(data['G_total']), "100.0%", ""])
    rows.append(["총비용 (지출)", fmt(data['total_expense']), pct(data['total_expense']/base*100), ""])
    
    for key, label in EXPENSE_ITEMS.items():
        val = get_safe_value(st.session_state.expenses[key])
        note = st.session_state.expense_notes.get(key, "")
        if val > 0 or note:
            rows.append([f"  └ {label}", fmt(val), pct(val/base*100), note])
            
    rows.append(["순이익 (차감전)", fmt(data['net_profit']), pct(data['net_profit']/base*100), "입금액 - 비용"])
    rows.append(["위탁수수료 (20%)", fmt(data['commission']), pct(data['commission']/base*100), "순이익의 20%"])
    
    # 최종 결과용 별도 행
    final_row = ["최종 배당금", fmt(data['final_payout']), pct(data['final_payout']/base*100), "최종 지급액"]

    # 데이터프레임 생성
    df_detail = pd.DataFrame(rows, columns=["구분", "금액", "비율", "비고"])
    
    # [중요] 스크롤바 없는 전체 테이블 표시를 위해 st.table 사용
    st.table(df_detail)

    # 최종 배당금 강조 (블루 박스)
    st.info(f"### 💰 최종 배당금: {data['final_payout']:,} 원")

    st.markdown('</div>', unsafe_allow_html=True) # End of a4-preview

    # ------------------------------------------------------------------
    # 하단 다운로드 버튼
    # ------------------------------------------------------------------
    c1, c2 = st.columns(2)
    
    with c1:
        # JSON 백업 (보조)
        save_data = {
            "ota": st.session_state.ota_df.to_dict('records'),
            "exp": st.session_state.expenses,
            "notes": st.session_state.expense_notes
        }
        st.download_button(
            "💾 데이터 백업 (.json)", 
            json.dumps(save_data, default=str), 
            "comocasa_data.json"
        )
        
    with c2:
        # PDF 다운로드
        try:
            pdf_bytes = create_pdf(data, st.session_state.expenses, st.session_state.expense_notes)
            st.download_button(
                "📄 정산서 PDF 다운로드", 
                pdf_bytes, 
                "comocasa_report.pdf", 
                type="primary",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"PDF 생성 오류: {e}")

if __name__ == "__main__":
    main()
