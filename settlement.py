import streamlit as st
import pandas as pd
import json
from fpdf import FPDF
import os

# --------------------------------------------------------------------------
# 1. 설정 및 CSS (강제 블루 테마 적용)
# --------------------------------------------------------------------------
st.set_page_config(page_title="숙박 위탁 정산 시스템", layout="wide", page_icon="🏨")

# CSS: 버튼 및 주요 요소를 파란색으로 강제 변경 (!important 사용)
st.markdown("""
    <style>
    /* 기본 버튼 (Secondary) 스타일 */
    button[kind="secondary"] {
        background-color: white !important;
        color: #007bff !important;
        border: 1px solid #007bff !important;
    }
    button[kind="secondary"]:hover {
        background-color: #e7f1ff !important;
    }
    
    /* 주요 버튼 (Primary) 스타일 */
    button[kind="primary"] {
        background-color: #007bff !important;
        color: white !important;
        border: none !important;
    }
    button[kind="primary"]:hover {
        background-color: #0056b3 !important;
    }

    /* 데이터 에디터 선택 셀 테두리 */
    .stDataFrame {
        border: 1px solid #cce5ff;
    }
    </style>
    """, unsafe_allow_html=True)

# --------------------------------------------------------------------------
# 2. 상수 및 초기 설정
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
# 3. 로직 함수 (계산 및 상태 관리)
# --------------------------------------------------------------------------
def init_session_state():
    # 데이터프레임 초기화 (최초 1회만 실행)
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

    # 비용 데이터 초기화 (None으로 초기화하여 빈 칸 표시)
    if 'expenses' not in st.session_state:
        st.session_state.expenses = {key: None for key in EXPENSE_ITEMS.keys()}
        st.session_state.expenses['operating_days'] = None # 가동일수도 빈칸

    # 비용 비고란 초기화
    if 'expense_notes' not in st.session_state:
        st.session_state.expense_notes = {key: "" for key in EXPENSE_ITEMS.keys()}

    # 페이지 네비게이션
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'input'

def get_safe_value(value):
    """None이면 0을 반환, 아니면 원래 값 반환 (계산용)"""
    return value if value is not None else 0

def calculate_metrics(df, expenses):
    """정산 로직 계산"""
    # 1. 데이터프레임 계산 (H = F - G)
    # 원본 세션 데이터를 복사해서 계산에 사용
    calc_df = df.copy()
    calc_df[COLS["H"]] = calc_df[COLS["F"]] - calc_df[COLS["G"]]
    
    sums = calc_df.sum(numeric_only=True)
    
    total_revenue_F = sums.get(COLS["F"], 0)
    net_sales_G = sums.get(COLS["G"], 0)
    total_nights_E = sums.get(COLS["E"], 0)
    
    # 2. 비용 계산 (None -> 0 변환 처리)
    total_expense_cost = sum(get_safe_value(v) for k, v in expenses.items() if k != 'operating_days')
    
    # 3. 이익 및 수수료 계산
    net_profit = net_sales_G - total_expense_cost
    commission_fee = int(net_profit * 0.20)
    final_payout = int(net_profit - commission_fee)
    
    # 4. KPI
    adr = (total_revenue_F / total_nights_E) if total_nights_E > 0 else 0
    op_days = get_safe_value(expenses.get('operating_days'))
    
    return {
        "F_total": total_revenue_F,
        "G_total": net_sales_G,
        "total_expense": total_expense_cost,
        "net_profit": net_profit,
        "commission": commission_fee,
        "final_payout": final_payout,
        "adr": adr,
        "op_days": op_days
    }

def create_pdf(metrics, expenses_dict, expense_notes):
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

    # 헬퍼 함수: 행 출력
    def write_row(col1, col2, col3, col4=""):
        pdf.cell(60, 8, col1, border=1)
        pdf.cell(40, 8, col2, border=1, align='R')
        pdf.cell(30, 8, col3, border=1, align='R')
        pdf.cell(60, 8, col4, border=1)
        pdf.ln()

    # 제목
    pdf.set_font(size=16)
    title = "Monthly Settlement Report" if not is_korean else "숙박 위탁 정산 보고서"
    pdf.cell(0, 15, title, ln=True, align='C')
    pdf.set_font(size=10)

    # 섹션 1
    pdf.cell(0, 10, "1. 요약 정보", ln=True)
    pdf.cell(0, 8, f"판매총액: {metrics['F_total']:,} KRW / 순매출액: {metrics['G_total']:,} KRW", ln=True)
    pdf.cell(0, 8, f"객단가(ADR): {metrics['adr']:,.0f} KRW / 가동일수: {metrics['op_days']} 일", ln=True)
    pdf.ln(5)

    # 섹션 2 (표)
    pdf.cell(0, 10, "2. 정산 세부 내역", ln=True)
    
    # 헤더
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(60, 8, "구분", border=1, fill=True, align='C')
    pdf.cell(40, 8, "금액 (원)", border=1, fill=True, align='C')
    pdf.cell(30, 8, "매출대비", border=1, fill=True, align='C')
    pdf.cell(60, 8, "비고", border=1, fill=True, align='C')
    pdf.ln()

    # 데이터
    base = metrics['G_total'] if metrics['G_total'] > 0 else 1
    
    write_row("순매출액", f"{metrics['G_total']:,}", "100.0%")
    write_row("총비용", f"{metrics['total_expense']:,}", f"{metrics['total_expense']/base*100:.1f}%")
    
    for key, label in EXPENSE_ITEMS.items():
        val = get_safe_value(expenses_dict[key])
        if val > 0 or expense_notes.get(key, ""):
            note = expense_notes.get(key, "")
            ratio = f"{val/base*100:.1f}%"
            write_row(f"  - {label}", f"{val:,}", ratio, note)
            
    write_row("순이익 (차감전)", f"{metrics['net_profit']:,}", f"{metrics['net_profit']/base*100:.1f}%")
    write_row("위탁수수료 (20%)", f"{metrics['commission']:,}", f"{metrics['commission']/base*100:.1f}%")
    
    pdf.set_font(style='B')
    write_row("최종 배당금", f"{metrics['final_payout']:,}", f"{metrics['final_payout']/base*100:.1f}%")

    return pdf.output(dest='S').encode('latin-1')

# --------------------------------------------------------------------------
# 4. 메인 애플리케이션 (UI)
# --------------------------------------------------------------------------
def main():
    init_session_state()

    # 페이지 라우팅
    if st.session_state.current_page == 'input':
        input_page()
    else:
        report_page()

def input_page():
    st.title("📝 정산 데이터 입력")

    # [1] OTA 매출 입력
    st.subheader("1. 플랫폼(OTA)별 매출 입력")
    
    # --- 버그 수정 핵심 로직: H 컬럼 선행 계산 ---
    # 사용자가 보게 될 데이터프레임에 미리 계산 로직 반영
    display_df = st.session_state.ota_df.copy()
    display_df[COLS["H"]] = display_df[COLS["F"]] - display_df[COLS["G"]]

    # (A) 상단 합계 (Total) - 계산된 display_df 기준
    st.markdown("**▼ 전체 합계 (자동 계산)**")
    totals = display_df.sum(numeric_only=True)
    total_data = {
        COLS["OTA"]: ["합 계"],
        COLS["D"]: [totals[COLS["D"]]],
        COLS["E"]: [totals[COLS["E"]]],
        COLS["F"]: [totals[COLS["F"]]],
        COLS["G"]: [totals[COLS["G"]]],
        COLS["H"]: [totals[COLS["H"]]]
    }
    st.dataframe(pd.DataFrame(total_data), use_container_width=True, hide_index=True)

    # (B) 데이터 에디터 (수정 가능)
    # 주의: H컬럼은 disabled 처리
    edited_df = st.data_editor(
        display_df,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            COLS["OTA"]: st.column_config.TextColumn("플랫폼", disabled=True),
            COLS["D"]: st.column_config.NumberColumn("체크인(D)", format="%d", min_value=0),
            COLS["E"]: st.column_config.NumberColumn("숙박일수(E)", format="%d", min_value=0),
            COLS["F"]: st.column_config.NumberColumn("총매출액(F)", format="%d", step=1000),
            COLS["G"]: st.column_config.NumberColumn("입금액(G)", format="%d", step=1000),
            COLS["H"]: st.column_config.NumberColumn("플랫폼수수료(H)", format="%d", disabled=True),
        }
    )

    # --- 버그 수정 핵심 로직: 상태 즉시 동기화 ---
    # 에디터에서 반환된 값을 세션 상태에 저장. 
    # 단, H컬럼은 계산식이므로 제외하고 저장해도 되고 포함해도 되지만,
    # 다음에 불러올 때를 위해 전체를 저장하되, H는 어차피 위에서 다시 계산됨.
    # 변경 사항이 있을 때만 업데이트하는 조건문 제거 -> 항상 최신 상태 유지
    st.session_state.ota_df = edited_df

    st.divider()

    # [2] 비용 입력 (빈 칸 처리)
    st.subheader("2. 월 운영 비용 및 정보")
    
    col1, col2, col3 = st.columns(3)
    cols = [col1, col2, col3]
    
    for i, (key, label) in enumerate(EXPENSE_ITEMS.items()):
        with cols[i % 3]:
            # value=None으로 설정하여 화면에 빈 칸으로 표시
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
            
            # 상태 업데이트
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

    # 저장 버튼 (블루)
    if st.button("💾 입력 내용 저장 및 리포트 보기", type="primary", use_container_width=True):
        st.session_state.current_page = 'report'
        st.rerun()

def report_page():
    st.title("📊 숙박 위탁 운영 정산서")
    
    if st.button("⬅ 수정하러 돌아가기", type="secondary"):
        st.session_state.current_page = 'input'
        st.rerun()
    
    st.divider()

    # 계산 (None값 처리 포함)
    data = calculate_metrics(st.session_state.ota_df, st.session_state.expenses)
    
    # 1. KPI
    st.subheader("1. 판매 현황 (부가세 포함)")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("판매총액", f"{data['F_total']:,}")
    k2.metric("순매출액", f"{data['G_total']:,}")
    k3.metric("가동일수", f"{data['op_days']}일")
    k4.metric("ADR", f"{data['adr']:,.0f}원")

    st.divider()

    # 2. 정산 결과
    st.subheader("2. 정산서 (배당금)")
    st.success(f"### 💰 배당 대상 순이익: {data['final_payout']:,} 원")
    st.caption(f"*계산식: (순매출액 {data['G_total']:,} - 총비용 {data['total_expense']:,}) x 80%")

    st.divider()

    # 3. 상세 내역 테이블
    st.subheader("3. 정산 세부 내역")
    
    base = data['G_total'] if data['G_total'] > 0 else 1
    rows = []
    
    # 3-1. 기본 정보
    rows.append(["순매출액", data['G_total'], "100.0%", ""])
    rows.append(["총비용", data['total_expense'], f"{data['total_expense']/base*100:.1f}%", ""])
    
    # 3-2. 비용 상세 (입력된 것만 표시)
    for key, label in EXPENSE_ITEMS.items():
        val = get_safe_value(st.session_state.expenses[key])
        note = st.session_state.expense_notes.get(key, "")
        if val > 0 or note:
            rows.append([f"  └ {label}", val, f"{val/base*100:.1f}%", note])
            
    # 3-3. 결과
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
        # JSON
        save_data = {
            "ota": st.session_state.ota_df.to_dict('records'),
            # expenses에서 None값을 0으로 바꿔서 저장하거나 그대로 저장 (여기선 그대로)
            "exp": st.session_state.expenses,
            "notes": st.session_state.expense_notes
        }
        st.download_button("💾 데이터 파일 저장 (.json)", json.dumps(save_data, default=str), "data.json")
        
    with c2:
        # PDF
        try:
            pdf_bytes = create_pdf(data, st.session_state.expenses, st.session_state.expense_notes)
            st.download_button("📄 PDF 리포트 다운로드", pdf_bytes, "report.pdf", type="primary")
        except Exception as e:
            st.error(f"PDF 오류: {e}")

if __name__ == "__main__":
    main()
