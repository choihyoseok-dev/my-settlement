import streamlit as st
import pandas as pd
import json
from fpdf import FPDF
import os

# --------------------------------------------------------------------------
# 1. 디자인 및 설정 (Blue Theme 강제 적용)
# --------------------------------------------------------------------------
st.set_page_config(page_title="숙박 위탁 정산 시스템", layout="wide", page_icon="🏨")

# [디자인] CSS 주입: 버튼, 입력창, 데이터프레임 등을 강제로 파란색 계열로 변경
st.markdown("""
    <style>
    /* Primary Button (저장 등 주요 버튼) */
    div.stButton > button[kind="primary"] {
        background-color: #007bff !important;
        border-color: #007bff !important;
        color: white !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #0056b3 !important;
        border-color: #0056b3 !important;
    }
    
    /* Secondary Button (일반 버튼) */
    div.stButton > button[kind="secondary"] {
        background-color: white !important;
        border: 1px solid #007bff !important;
        color: #007bff !important;
    }
    div.stButton > button[kind="secondary"]:hover {
        background-color: #e7f1ff !important;
    }

    /* 데이터 에디터 헤더 및 테이블 스타일 */
    [data-testid="stDataFrame"] {
        border: 1px solid #cce5ff;
    }
    
    /* 숫자 입력창 (Number Input) 포커스 색상 */
    input[type="number"]:focus {
        border-color: #007bff !important;
        box-shadow: 0 0 0 1px #007bff !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --------------------------------------------------------------------------
# 2. 상수 및 데이터 구조 정의
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
# 3. 로직 함수 (State 관리 & 계산)
# --------------------------------------------------------------------------
def init_session_state():
    """세션 상태 초기화: 데이터가 없을 때만 생성"""
    if 'ota_df' not in st.session_state:
        # 초기 데이터 생성
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
        # 빈 칸(None)으로 초기화
        st.session_state.expenses = {key: None for key in EXPENSE_ITEMS.keys()}
        st.session_state.expenses['operating_days'] = None

    if 'expense_notes' not in st.session_state:
        st.session_state.expense_notes = {key: "" for key in EXPENSE_ITEMS.keys()}
        
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'input'

def get_safe_value(value):
    """None(빈칸)이면 0으로 변환하여 계산"""
    return value if value is not None else 0

def calculate_metrics(df, expenses):
    """최종 정산 데이터 계산"""
    # 1. DataFrame 계산 (H = F - G)
    # 원본 세션 데이터를 오염시키지 않기 위해 복사본 사용
    calc_df = df.copy()
    calc_df[COLS["H"]] = calc_df[COLS["F"]] - calc_df[COLS["G"]]
    
    sums = calc_df.sum(numeric_only=True)
    
    F_total = sums.get(COLS["F"], 0)
    G_total = sums.get(COLS["G"], 0)
    E_total = sums.get(COLS["E"], 0)
    
    # 2. 비용 합계 계산
    total_expense = sum(get_safe_value(v) for k, v in expenses.items() if k != 'operating_days')
    
    # 3. 이익 및 수수료
    net_profit = G_total - total_expense
    commission = int(net_profit * 0.20)
    final_payout = int(net_profit - commission)
    
    # 4. ADR (객단가)
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
    """PDF 생성 함수"""
    pdf = FPDF()
    pdf.add_page()
    
    font_path = "NanumGothic.ttf"
    is_korean = False
    if os.path.exists(font_path):
        pdf.add_font("NanumGothic", "", font_path, uni=True)
        pdf.set_font("NanumGothic", size=10)
        is_korean = True
    else:
        pdf.set_font("Arial", size=10)

    # 행 출력 헬퍼
    def write_row(c1, c2, c3, c4=""):
        pdf.cell(60, 8, c1, border=1)
        pdf.cell(40, 8, c2, border=1, align='R')
        pdf.cell(30, 8, c3, border=1, align='R')
        pdf.cell(60, 8, c4, border=1)
        pdf.ln()

    # 타이틀
    pdf.set_font(size=16)
    title = "Monthly Settlement Report" if not is_korean else "숙박 위탁 정산 보고서"
    pdf.cell(0, 15, title, ln=True, align='C')
    
    # 본문
    pdf.set_font(size=10)
    pdf.cell(0, 10, "[1. 요약 정보]", ln=True)
    pdf.cell(0, 8, f"판매총액: {metrics['F_total']:,} KRW  /  순매출액: {metrics['G_total']:,} KRW", ln=True)
    pdf.cell(0, 8, f"객단가(ADR): {metrics['adr']:,.0f} KRW  /  가동일수: {metrics['op_days']} 일", ln=True)
    pdf.ln(5)

    pdf.cell(0, 10, "[2. 정산 세부 내역]", ln=True)
    # 헤더
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(60, 8, "구분", 1, 0, 'C', True)
    pdf.cell(40, 8, "금액 (원)", 1, 0, 'C', True)
    pdf.cell(30, 8, "매출대비", 1, 0, 'C', True)
    pdf.cell(60, 8, "비고", 1, 1, 'C', True)

    base = metrics['G_total'] if metrics['G_total'] > 0 else 1
    
    write_row("순매출액", f"{metrics['G_total']:,}", "100.0%")
    write_row("총비용", f"{metrics['total_expense']:,}", f"{metrics['total_expense']/base*100:.1f}%")
    
    for key, label in EXPENSE_ITEMS.items():
        val = get_safe_value(expenses_dict[key])
        note = expense_notes.get(key, "")
        if val > 0 or note:
            write_row(f"  - {label}", f"{val:,}", f"{val/base*100:.1f}%", note)
            
    write_row("순이익 (차감전)", f"{metrics['net_profit']:,}", f"{metrics['net_profit']/base*100:.1f}%", "입금액 - 비용")
    write_row("위탁수수료 (20%)", f"{metrics['commission']:,}", f"{metrics['commission']/base*100:.1f}%", "순이익의 20%")
    
    pdf.set_font(style='B')
    write_row("최종 배당금", f"{metrics['final_payout']:,}", f"{metrics['final_payout']/base*100:.1f}%", "지급액")

    return pdf.output(dest='S').encode('latin-1')

# --------------------------------------------------------------------------
# 4. 메인 화면 구성
# --------------------------------------------------------------------------
def main():
    init_session_state()

    # 페이지 라우팅
    if st.session_state.current_page == 'input':
        render_input_page()
    else:
        render_report_page()

def render_input_page():
    st.title("📝 정산 데이터 입력")

    # ---------------------------------------------------------
    # [1] OTA 매출 입력 (버그 해결의 핵심 부분)
    # ---------------------------------------------------------
    st.subheader("1. 플랫폼(OTA)별 매출 입력")
    
    # 1. 세션에 저장된 현재 데이터를 가져옵니다.
    current_df = st.session_state.ota_df

    # 2. 보여주기 전에 '합계'와 'H열(수수료)'을 미리 계산합니다.
    #    (사용자가 보게 될 화면용 DF를 만듭니다)
    display_df = current_df.copy()
    display_df[COLS["H"]] = display_df[COLS["F"]] - display_df[COLS["G"]]
    
    # 3. 합계 표시 (Total)
    totals = display_df.sum(numeric_only=True)
    st.markdown("**▼ 전체 합계 (자동 계산)**")
    
    total_data = pd.DataFrame([{
        COLS["OTA"]: "합 계",
        COLS["D"]: totals[COLS["D"]],
        COLS["E"]: totals[COLS["E"]],
        COLS["F"]: totals[COLS["F"]],
        COLS["G"]: totals[COLS["G"]],
        COLS["H"]: totals[COLS["H"]]
    }])
    
    st.dataframe(
        total_data, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            COLS["D"]: st.column_config.NumberColumn(format="%d건"),
            COLS["E"]: st.column_config.NumberColumn(format="%d박"),
            COLS["F"]: st.column_config.NumberColumn(format="%d원"),
            COLS["G"]: st.column_config.NumberColumn(format="%d원"),
            COLS["H"]: st.column_config.NumberColumn(format="%d원")
        }
    )

    # 4. 데이터 에디터 (Data Editor)
    # [해결책]: key를 사용하지 않고, 리턴값을 바로 session_state에 덮어씌웁니다.
    # 이렇게 하면 Streamlit이 rerun할 때 최신 데이터를 유지합니다.
    edited_df = st.data_editor(
        current_df,  # 항상 현재 저장된 최신 상태를 불러옴
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            COLS["OTA"]: st.column_config.TextColumn("플랫폼", disabled=True),
            COLS["D"]: st.column_config.NumberColumn("체크인(D)", format="%d", min_value=0),
            COLS["E"]: st.column_config.NumberColumn("숙박일수(E)", format="%d", min_value=0),
            COLS["F"]: st.column_config.NumberColumn("총매출액(F)", format="%d", step=1000),
            COLS["G"]: st.column_config.NumberColumn("입금액(G)", format="%d", step=1000),
            # H열은 자동계산이므로 에디터에서는 보여주되 수정 불가하게 하거나,
            # 데이터 무결성을 위해 여기서는 숨기고 위 합계에서만 확인하게 할 수도 있습니다.
            # 요청에 따라 수정 불가 상태로 표시합니다. (단, 입력용 DF엔 H열 데이터가 없으므로 표시 안됨)
            # 팁: 계산된 H열을 에디터에 보여주려면 display_df를 넣어야 하는데,
            # 그러면 H열 값이 입력값으로 들어와서 꼬일 수 있습니다.
            # 깔끔하게: 입력 에디터에는 F, G만 입력받고 H는 위의 '합계' 표나 리포트에서 확인하는 것이 가장 안전합니다.
        }
    )

    # [중요] 변경사항 즉시 반영
    # 에디터의 결과물이 이전 상태와 다르다면 저장합니다.
    if not edited_df.equals(st.session_state.ota_df):
        st.session_state.ota_df = edited_df
        st.rerun() # 즉시 재실행하여 합계표를 업데이트

    st.divider()

    # ---------------------------------------------------------
    # [2] 비용 입력 (빈 칸 처리 적용)
    # ---------------------------------------------------------
    st.subheader("2. 월 운영 비용 및 정보")
    
    col1, col2, col3 = st.columns(3)
    cols = [col1, col2, col3]
    
    for i, (key, label) in enumerate(EXPENSE_ITEMS.items()):
        with cols[i % 3]:
            # [해결책] value=None 설정으로 화면에 '0' 대신 빈 칸 표시
            val = st.number_input(
                f"{label} (금액)",
                value=st.session_state.expenses[key],
                placeholder="입력하세요",
                step=10000,
                format="%d",
                key=f"input_{key}"
            )
            note = st.text_input(
                f"{label} (비고)",
                value=st.session_state.expense_notes.get(key, ""),
                placeholder="내용 입력",
                key=f"note_{key}"
            )
            
            # 값 저장
            st.session_state.expenses[key] = val
            st.session_state.expense_notes[key] = note
            st.markdown("---")

    st.subheader("📅 운영 정보")
    st.session_state.expenses['operating_days'] = st.number_input(
        "이번 달 총 가동일수 (일)",
        value=st.session_state.expenses['operating_days'],
        placeholder="일수 입력",
        min_value=0, max_value=31
    )

    st.divider()

    # 저장 버튼 (Primary - Blue)
    if st.button("💾 입력 내용 저장 및 리포트 보기", type="primary", use_container_width=True):
        st.session_state.current_page = 'report'
        st.rerun()

def render_report_page():
    st.title("📊 숙박 위탁 운영 정산서")
    
    # 돌아가기 버튼 (Secondary - Blue text)
    if st.button("⬅ 수정하러 돌아가기", type="secondary"):
        st.session_state.current_page = 'input'
        st.rerun()
    
    st.divider()

    # 계산 실행
    data = calculate_metrics(st.session_state.ota_df, st.session_state.expenses)
    
    # 1. KPI
    st.subheader("1. 판매 현황 (부가세 포함)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("판매총액", f"{data['F_total']:,}")
    c2.metric("순매출액", f"{data['G_total']:,}")
    c3.metric("가동일수", f"{data['op_days']}일")
    c4.metric("ADR", f"{data['adr']:,.0f}원")

    st.divider()

    # 2. 결과
    st.subheader("2. 정산서 (배당금)")
    st.success(f"### 💰 배당 대상 순이익: {data['final_payout']:,} 원")
    st.caption(f"*계산식: (순매출액 {data['G_total']:,} - 총비용 {data['total_expense']:,}) x 80%")

    st.divider()

    # 3. 상세 테이블
    st.subheader("3. 정산 세부 내역")
    
    base = data['G_total'] if data['G_total'] > 0 else 1
    rows = []
    
    rows.append(["순매출액", data['G_total'], "100.0%", ""])
    rows.append(["총비용", data['total_expense'], f"{data['total_expense']/base*100:.1f}%", ""])
    
    for key, label in EXPENSE_ITEMS.items():
        val = get_safe_value(st.session_state.expenses[key])
        note = st.session_state.expense_notes.get(key, "")
        if val > 0 or note:
            rows.append([f"  └ {label}", val, f"{val/base*100:.1f}%", note])
            
    rows.append(["순이익 (차감전)", data['net_profit'], f"{data['net_profit']/base*100:.1f}%", "입금액-비용"])
    rows.append(["위탁수수료 (20%)", data['commission'], f"{data['commission']/base*100:.1f}%", "순이익의 20%"])
    rows.append(["배당 대상 순이익", data['final_payout'], f"{data['final_payout']/base*100:.1f}%", "최종 지급액"])
    
    df_res = pd.DataFrame(rows, columns=["구분", "금액", "매출대비", "비고"])
    
    st.dataframe(
        df_res,
        use_container_width=True,
        hide_index=True,
        column_config={
            "금액": st.column_config.NumberColumn(format="%d원"),
        }
    )

    # 4. 다운로드
    st.subheader("📥 다운로드")
    c1, c2 = st.columns(2)
    with c1:
        # JSON 저장
        save_data = {
            "ota": st.session_state.ota_df.to_dict('records'),
            "exp": st.session_state.expenses,
            "notes": st.session_state.expense_notes
        }
        # JSON 저장 시 None값 처리 (JSON 표준은 null)
        st.download_button(
            "💾 데이터 저장 (.json)", 
            json.dumps(save_data, default=str), 
            "settlement_data.json"
        )
    with c2:
        # PDF 저장
        try:
            pdf_bytes = create_pdf(data, st.session_state.expenses, st.session_state.expense_notes)
            st.download_button(
                "📄 PDF 리포트 다운로드", 
                pdf_bytes, 
                "settlement_report.pdf", 
                type="primary"
            )
        except Exception as e:
            st.error(f"PDF 오류: {e}")

if __name__ == "__main__":
    main()
