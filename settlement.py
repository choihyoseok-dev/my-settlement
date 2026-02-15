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
    /* 1. 타이틀 스타일 */
    .main-title {
        font-size: 40px;
        font-weight: 800;
        color: #1E3A8A; /* 짙은 블루 */
        margin-bottom: 10px;
    }
    .report-title {
        font-size: 32px;
        font-weight: 700;
        color: #333333;
        text-align: center;
        margin-top: 20px;
        margin-bottom: 20px;
        text-decoration: underline;
        text-underline-offset: 8px;
    }

    /* 2. 버튼 스타일 (블루 테마) */
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

    /* 3. A4 용지 느낌의 리포트 컨테이너 */
    .a4-container {
        background-color: white;
        padding: 40px;
        margin: auto;
        border: 1px solid #ddd;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        max-width: 210mm; /* A4 폭 */
        min-height: 297mm; /* A4 높이 */
    }

    /* 4. 입력창 포커스 색상 */
    input:focus {
        border-color: #2563EB !important;
        box-shadow: 0 0 0 1px #2563EB !important;
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
    # 계산용 복사본
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
    
    # 한글 폰트 설정
    font_path = "NanumGothic.ttf"
    if os.path.exists(font_path):
        pdf.add_font("NanumGothic", "", font_path, uni=True)
        font_family = "NanumGothic"
    else:
        font_family = "Arial"

    pdf.set_font(font_family, size=10)

    # 행 출력 헬퍼
    def write_row(c1, c2, c3, c4=""):
        pdf.cell(70, 8, c1, border=1)
        pdf.cell(35, 8, c2, border=1, align='R')
        pdf.cell(25, 8, c3, border=1, align='R')
        pdf.cell(60, 8, c4, border=1)
        pdf.ln()

    # 타이틀
    pdf.set_font(font_family, style='B', size=20)
    pdf.cell(0, 15, "꼬모까사 위탁숙박 정산서", ln=True, align='C')
    pdf.ln(10)

    # 1. 요약
    pdf.set_font(font_family, style='B', size=12)
    pdf.cell(0, 10, "1. 판매 현황 (Summary)", ln=True)
    pdf.set_font(font_family, size=10)
    
    pdf.cell(95, 8, f"판매총액: {metrics['F_total']:,} 원", border=1)
    pdf.cell(95, 8, f"순매출액: {metrics['G_total']:,} 원", border=1)
    pdf.ln()
    pdf.cell(95, 8, f"객단가(ADR): {metrics['adr']:,.0f} 원", border=1)
    pdf.cell(95, 8, f"가동일수: {metrics['op_days']} 일", border=1)
    pdf.ln(10)

    # 2. 상세 내역
    pdf.set_font(font_family, style='B', size=12)
    pdf.cell(0, 10, "2. 정산 세부 내역 (Detail)", ln=True)
    
    # 헤더
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font(font_family, size=10)
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
    pdf.set_fill_color(230, 240, 255) # 연한 블루
    pdf.cell(70, 10, "최종 배당금", 1, 0, 'L', True)
    pdf.cell(35, 10, f"{metrics['final_payout']:,}", 1, 0, 'R', True)
    pdf.cell(25, 10, f"{metrics['final_payout']/base*100:.1f}%", 1, 0, 'R', True)
    pdf.cell(60, 10, "최종 지급액", 1, 1, 'L', True)

    return pdf.output(dest='S').encode('latin-1')

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
    # 1. OTA 매출 입력 (포커스 유지 & 네비게이션 해결)
    # ---------------------------------------------------------
    st.subheader("1. 플랫폼(OTA)별 매출 입력")
    st.caption("※ 팁: 엔터(Enter)나 방향키를 사용해 연속으로 입력하세요. 합계는 '저장' 시 갱신됩니다.")

    # 편집용 데이터프레임
    # session state와 바인딩하되, 키 입력시 자동 rerun을 막기 위해 
    # form이나 별도 처리를 하지 않고 data_editor 자체 기능 활용
    
    # 합계 미리보기 (현재 세션 상태 기준)
    display_df = st.session_state.ota_df.copy()
    display_df[COLS["H"]] = display_df[COLS["F"]] - display_df[COLS["G"]]
    totals = display_df.sum(numeric_only=True)
    
    # 합계 테이블 생성 (문자열로 변환하여 콤마 적용)
    total_row = {
        COLS["OTA"]: "합 계",
        COLS["D"]: f"{totals[COLS['D']]:,.0f}",
        COLS["E"]: f"{totals[COLS['E']]:,.0f}",
        COLS["F"]: f"{totals[COLS['F']]:,.0f}",
        COLS["G"]: f"{totals[COLS['G']]:,.0f}",
        COLS["H"]: f"{totals[COLS['H']]:,.0f}"
    }
    
    st.markdown("**▼ 전체 합계 (입력 후 '저장'을 누르면 갱신됩니다)**")
    st.dataframe(pd.DataFrame([total_row]), use_container_width=True, hide_index=True)

    # 데이터 에디터
    # [중요] num_rows="fixed"로 하고, key를 부여하여 상태 유지
    # [중요] on_change를 제거하여 엔터 시 리런 방지 -> 포커스 유지
    edited_df = st.data_editor(
        st.session_state.ota_df,
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
    # 2. 비용 입력 (세로 배치 & 콤마 표시)
    # ---------------------------------------------------------
    st.subheader("2. 월 운영 비용 및 정보")
    
    # 1줄에 1개씩 세로 배치
    for key, label in EXPENSE_ITEMS.items():
        # 레이아웃: [비용이름/입력창] --- [비고 입력창]
        c1, c2 = st.columns([1, 2])
        
        with c1:
            val = st.number_input(
                f"{label} (금액)",
                value=st.session_state.expenses[key],
                step=10000,
                format="%d", # 입력 중에는 콤마 어려움, 표시는 정수로
                key=f"input_{key}",
                help="금액을 입력하세요"
            )
        with c2:
            note = st.text_input(
                f"{label} 비고",
                value=st.session_state.expense_notes.get(key, ""),
                placeholder="내용 입력",
                key=f"note_{key}",
                label_visibility="visible"
            )
            
        # 상태 임시 저장 (화면 리런 시 유지용)
        st.session_state.expenses[key] = val
        st.session_state.expense_notes[key] = note
        
    st.markdown("---")
    
    # 가동일수 (너비 조정)
    col_small, col_rest = st.columns([1, 4]) # 1:4 비율로 작게 만듦
    with col_small:
        op_days = st.number_input(
            "이번 달 총 가동일수 (일)",
            value=st.session_state.expenses['operating_days'],
            min_value=0, max_value=31,
            key="op_days_input"
        )
        st.session_state.expenses['operating_days'] = op_days

    st.divider()

    # [저장 버튼]
    if st.button("💾 입력 내용 저장 및 리포트 보기", type="primary", use_container_width=True):
        # 에디터의 최신 상태를 세션에 반영
        st.session_state.ota_df = edited_df
        st.session_state.current_page = 'report'
        st.rerun()

def render_report_page():
    # 상단 네비게이션
    if st.button("⬅ 수정하러 돌아가기", type="secondary"):
        st.session_state.current_page = 'input'
        st.rerun()
    
    # 계산 실행
    data = calculate_metrics(st.session_state.ota_df, st.session_state.expenses)
    
    # ------------------------------------------------------------------
    # A4 용지 스타일 컨테이너 시작
    # ------------------------------------------------------------------
    # Streamlit 컨테이너 사용하지만 CSS로 .a4-container 적용이 어려우므로
    # 중앙 정렬된 컬럼을 사용하여 시각적 효과 구현
    
    _, col_a4, _ = st.columns([1, 6, 1]) # 중앙 집중 레이아웃
    
    with col_a4:
        st.markdown('<div class="report-title">꼬모까사 위탁숙박 정산서</div>', unsafe_allow_html=True)
        
        st.divider()

        # 1. KPI (콤마 적용)
        st.subheader("1. 판매 현황 (Summary)")
        
        k1, k2 = st.columns(2)
        k1.metric("판매총액", f"{data['F_total']:,} 원")
        k2.metric("순매출액", f"{data['G_total']:,} 원")
        
        k3, k4 = st.columns(2)
        k3.metric("객단가 (ADR)", f"{data['adr']:,.0f} 원")
        k4.metric("가동일수", f"{data['op_days']} 일")

        st.markdown("---")

        # 2. 상세 내역 테이블
        st.subheader("2. 정산 세부 내역 (Detail)")
        
        base = data['G_total'] if data['G_total'] > 0 else 1
        rows = []
        
        # 포맷팅 헬퍼
        def fmt_money(x): return f"{x:,}"
        def fmt_pct(x): return f"{x:.1f}%"
        
        rows.append(["순매출액", fmt_money(data['G_total']), "100.0%", ""])
        rows.append(["총비용 (지출)", fmt_money(data['total_expense']), fmt_pct(data['total_expense']/base*100), ""])
        
        for key, label in EXPENSE_ITEMS.items():
            val = get_safe_value(st.session_state.expenses[key])
            note = st.session_state.expense_notes.get(key, "")
            if val > 0 or note:
                rows.append([f"  └ {label}", fmt_money(val), fmt_pct(val/base*100), note])
                
        rows.append(["순이익 (차감전)", fmt_money(data['net_profit']), fmt_pct(data['net_profit']/base*100), "입금액 - 비용"])
        rows.append(["위탁수수료 (20%)", fmt_money(data['commission']), fmt_pct(data['commission']/base*100), "순이익의 20%"])
        
        # 결과 데이터프레임
        df_res = pd.DataFrame(rows, columns=["구분", "금액", "비율", "비고"])
        
        # 테이블 표시
        st.dataframe(
            df_res,
            use_container_width=True,
            hide_index=True,
            column_config={
                "구분": st.column_config.TextColumn("구분", width="medium"),
                "금액": st.column_config.TextColumn("금액", width="small"), # 문자열이므로 TextColumn
                "비율": st.column_config.TextColumn("비율", width="small"),
                "비고": st.column_config.TextColumn("비고", width="large"),
            }
        )

        st.divider()
        
        # 최종 배당금 강조 박스
        st.info(f"""
        ### 💰 최종 배당금: {data['final_payout']:,} 원
        """)

        st.markdown("<br><br>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # 하단 다운로드 버튼 (컨테이너 밖)
    # ------------------------------------------------------------------
    c_down1, c_down2 = st.columns(2)
    
    with c_down1:
        # JSON 백업
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
        
    with c_down2:
        # PDF 다운로드
        try:
            pdf_bytes = create_pdf(data, st.session_state.expenses, st.session_state.expense_notes)
            st.download_button(
                "📄 PDF 정산서 다운로드 (A4)", 
                pdf_bytes, 
                "comocasa_report.pdf", 
                type="primary",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"PDF 생성 오류: {e}")

if __name__ == "__main__":
    main()
