import streamlit as st
import pandas as pd
import json
from fpdf import FPDF
import os

# --------------------------------------------------------------------------
# 1. 설정 및 스타일 (CSS Injection for Blue Theme)
# --------------------------------------------------------------------------
st.set_page_config(page_title="숙박 위탁 정산 시스템", layout="wide", page_icon="🏨")

# 블루 테마 적용을 위한 커스텀 CSS
st.markdown("""
    <style>
    /* 전체 버튼 스타일 변경 (블루) */
    div.stButton > button:first-child {
        background-color: #007bff;
        color: white;
        border-radius: 5px; 
        border: none;
    }
    div.stButton > button:first-child:hover {
        background-color: #0056b3;
        color: white;
    }
    /* 데이터 에디터 선택 색상 등 */
    [data-testid="stDataFrame"] {
        border: 1px solid #e6e6e6;
    }
    /* 헤더 색상 강조 */
    h1, h2, h3 {
        color: #2c3e50;
    }
    </style>
    """, unsafe_allow_html=True)

# OTA 리스트 (요청사항 반영: "추가정보" 포함)
OTA_LIST = ["아고다", "부킹닷컴", "에어비앤비", "트립닷컴", "야놀자게하", "야놀자펜션", "여기어때", "추가정보(자가운영등)"]

# 컬럼 정의
COLS = {
    "OTA": "OTA",
    "D": "체크인건수(D)",
    "E": "숙박일수(E)",
    "F": "총매출액(F)",
    "G": "입금액(G)",
    "H": "플랫폼수수료(H)"  # 자동 계산 항목
}

# 비용 항목 정의
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
# 2. 로직 및 세션 관리
# --------------------------------------------------------------------------
def init_session_state():
    # 1. 페이지 네비게이션 상태
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'input'

    # 2. OTA 데이터프레임 초기화
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

    # 3. 비용 데이터 초기화
    if 'expenses' not in st.session_state:
        st.session_state.expenses = {key: 0 for key in EXPENSE_ITEMS.keys()}
        st.session_state.expenses['operating_days'] = 0
        
    # 4. 비용 비고란(Note) 초기화
    if 'expense_notes' not in st.session_state:
        st.session_state.expense_notes = {key: "" for key in EXPENSE_ITEMS.keys()}

def calculate_metrics(df, expenses):
    """정산 로직 계산"""
    # 1. 자동 계산 컬럼 업데이트 (H = F - G)
    # 복사본을 만들어 원본 데이터 오염 방지 및 계산 수행
    calc_df = df.copy()
    calc_df[COLS["H"]] = calc_df[COLS["F"]] - calc_df[COLS["G"]]
    
    sums = calc_df.sum(numeric_only=True)
    
    # 주요 합계 변수
    total_revenue_F = sums.get(COLS["F"], 0) # 판매총액
    net_sales_G = sums.get(COLS["G"], 0)     # 순매출액 (입금액)
    total_nights_E = sums.get(COLS["E"], 0)
    total_checkins_D = sums.get(COLS["D"], 0)
    
    # 비용 합계
    total_expense_cost = sum(v for k, v in expenses.items() if k != 'operating_days')
    
    # 순이익 (입금액 - 비용)
    net_profit = net_sales_G - total_expense_cost
    
    # 위탁 수수료 (순이익의 20%)
    commission_fee = int(net_profit * 0.20)
    
    # 배당 대상 순이익 (최종 지급액)
    final_payout = int(net_profit - commission_fee)
    
    # ADR (객단가)
    adr = (total_revenue_F / total_nights_E) if total_nights_E > 0 else 0
    
    # 판매율 (OCC) 등 추가 지표가 필요하면 여기서 계산 (가동일수 활용)
    op_days = expenses.get('operating_days', 0)
    occ = (total_nights_E / op_days * 100) if op_days > 0 else 0

    return {
        "df_calculated": calc_df,
        "F_total": total_revenue_F,
        "G_total": net_sales_G,
        "E_total": total_nights_E,
        "D_total": total_checkins_D,
        "total_expense": total_expense_cost,
        "net_profit": net_profit,
        "commission": commission_fee,
        "final_payout": final_payout,
        "adr": adr,
        "occ": occ,
        "op_days": op_days
    }

# PDF 생성 함수 (기존 유지 + 업데이트)
def create_pdf(metrics, expenses_dict, expense_notes):
    pdf = FPDF()
    pdf.add_page()
    
    font_path = "NanumGothic.ttf"
    is_korean = False
    if os.path.exists(font_path):
        pdf.add_font("NanumGothic", "", font_path, uni=True)
        pdf.set_font("NanumGothic", size=11)
        is_korean = True
    else:
        pdf.set_font("Arial", size=11)
        
    def write_row(label, val1, val2=""):
        pdf.cell(90, 8, label, border=1)
        pdf.cell(50, 8, val1, border=1, align='R')
        pdf.cell(50, 8, val2, border=1, align='R')
        pdf.ln()

    # 제목
    pdf.set_font(size=16)
    title = "Monthly Settlement Report" if not is_korean else "숙박 위탁 정산 보고서"
    pdf.cell(0, 15, title, ln=True, align='C')
    pdf.set_font(size=11)
    
    # 1. 판매 현황
    pdf.cell(0, 10, "1. 판매 현황", ln=True)
    write_row("구분", "값", "비고")
    write_row("판매총액", f"{metrics['F_total']:,} KRW")
    write_row("순매출액", f"{metrics['G_total']:,} KRW")
    write_row("ADR (객단가)", f"{metrics['adr']:,.0f} KRW")
    
    pdf.ln(5)
    
    # 2. 정산 상세
    pdf.cell(0, 10, "2. 정산 세부 내역", ln=True)
    write_row("항목", "금액", "매출대비 %")
    
    # 매출 기준 (순매출액 G 기준)
    base = metrics['G_total'] if metrics['G_total'] > 0 else 1
    
    write_row("순매출액", f"{metrics['G_total']:,}", "100.0%")
    write_row("총비용", f"{metrics['total_expense']:,}", f"{metrics['total_expense']/base*100:.1f}%")
    
    # 개별 비용
    for key, label in EXPENSE_ITEMS.items():
        amt = expenses_dict[key]
        if amt > 0:
            note = expense_notes.get(key, "")
            ratio = f"{amt/base*100:.1f}%"
            # PDF에는 칸 문제로 비고는 생략하거나 짧게
            write_row(f"- {label}", f"{amt:,}", ratio)
            
    write_row("순이익 (차감전)", f"{metrics['net_profit']:,}", f"{metrics['net_profit']/base*100:.1f}%")
    write_row("위탁수수료 (20%)", f"{metrics['commission']:,}", f"{metrics['commission']/base*100:.1f}%")
    
    pdf.set_font(style='B')
    write_row("최종 배당금", f"{metrics['final_payout']:,}", f"{metrics['final_payout']/base*100:.1f}%")

    return pdf.output(dest='S').encode('latin-1')

# --------------------------------------------------------------------------
# 3. 메인 화면 구성
# --------------------------------------------------------------------------
def main():
    init_session_state()

    # 페이지 분기 처리
    if st.session_state.current_page == 'input':
        render_input_page()
    else:
        render_report_page()

def render_input_page():
    st.title("📝 정산 데이터 입력")

    # [1] OTA 매출 입력
    st.subheader("1. 플랫폼(OTA)별 매출 입력")
    
    # (A) 상단 합계 행 (Bold 표시 효과를 위해 별도 데이터프레임으로 표시)
    st.markdown("**▼ 전체 합계 (자동 계산)**")
    
    # 현재 세션 데이터로 합계 계산
    current_df = st.session_state.ota_df
    # 플랫폼수수료(H)는 입력값이 아니라 결과값이므로 여기서 임시 계산해서 합계를 보여줌
    temp_h = current_df[COLS["F"]] - current_df[COLS["G"]]
    
    totals = {
        COLS["OTA"]: ["합 계 (Total)"],
        COLS["D"]: [current_df[COLS["D"]].sum()],
        COLS["E"]: [current_df[COLS["E"]].sum()],
        COLS["F"]: [current_df[COLS["F"]].sum()],
        COLS["G"]: [current_df[COLS["G"]].sum()],
        COLS["H"]: [temp_h.sum()] 
    }
    total_df = pd.DataFrame(totals)
    
    # 합계 테이블 스타일링 (배경색 등으로 강조)
    st.dataframe(
        total_df, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            COLS["D"]: st.column_config.NumberColumn(format="%d건"),
            COLS["E"]: st.column_config.NumberColumn(format="%d박"),
            COLS["F"]: st.column_config.NumberColumn(format="%d원"),
            COLS["G"]: st.column_config.NumberColumn(format="%d원"),
            COLS["H"]: st.column_config.NumberColumn(format="%d원"),
        }
    )

    # (B) 입력 에디터
    # 중요: 사용자가 H열(수수료)을 수정하지 못하게 disabled 처리
    # 중요: 입력 버그 방지를 위해 session_state 데이터를 직접 바인딩
    edited_df = st.data_editor(
        st.session_state.ota_df,
        key="ota_editor_widget", # 키를 지정하여 상태 유지
        use_container_width=True,
        num_rows="fixed",
        hide_index=True,
        column_config={
            COLS["OTA"]: st.column_config.TextColumn("플랫폼", disabled=True),
            COLS["D"]: st.column_config.NumberColumn("체크인(D)", format="%d", min_value=0),
            COLS["E"]: st.column_config.NumberColumn("숙박일수(E)", format="%d", min_value=0),
            COLS["F"]: st.column_config.NumberColumn("총매출액(F)", format="%d", step=1000),
            COLS["G"]: st.column_config.NumberColumn("입금액(G)", format="%d", step=1000),
            COLS["H"]: st.column_config.NumberColumn("플랫폼수수료(H)", format="%d원", disabled=True, help="자동계산: F - G"),
        }
    )
    
    # 변경 사항 즉시 반영 (버그 해결 핵심)
    st.session_state.ota_df = edited_df

    st.divider()

    # [2] 운영 비용 입력
    st.subheader("2. 월 운영 비용 및 정보")
    
    # 입력 폼 레이아웃
    col1, col2, col3 = st.columns(3)
    cols_list = [col1, col2, col3]
    
    i = 0
    for key, label in EXPENSE_ITEMS.items():
        with cols_list[i % 3]:
            # 금액 입력
            val = st.number_input(
                f"{label} (금액)", 
                value=st.session_state.expenses[key], 
                step=10000, 
                format="%d",
                key=f"exp_val_{key}"
            )
            # 비고 입력 (예: 1회 9,000원 등)
            note = st.text_input(
                f"{label} (비고)",
                value=st.session_state.expense_notes.get(key, ""),
                placeholder="예: 단가 1.5만 * 5회",
                key=f"exp_note_{key}"
            )
            
            # 상태 업데이트
            st.session_state.expenses[key] = val
            st.session_state.expense_notes[key] = note
            st.markdown("---")
        i += 1

    # 가동일수 별도 입력
    st.subheader("📅 운영 정보 확인")
    st.session_state.expenses['operating_days'] = st.number_input(
        "이번 달 총 가동일수 (일)",
        value=st.session_state.expenses['operating_days'],
        min_value=0, max_value=31
    )

    st.divider()
    
    # [3] 저장 버튼 -> 리포트 페이지로 이동
    if st.button("💾 입력 내용 저장 및 리포트 보기", type="primary", use_container_width=True):
        st.session_state.current_page = 'report'
        st.rerun()


def render_report_page():
    st.title("📊 숙박 위탁 운영 정산서")
    
    if st.button("⬅ 입력 화면으로 돌아가기"):
        st.session_state.current_page = 'input'
        st.rerun()
    
    st.divider()

    # 계산 수행
    data = calculate_metrics(st.session_state.ota_df, st.session_state.expenses)
    
    # ---------------------------------------------------------
    # 1. 판매 현황 (상단 요약)
    # ---------------------------------------------------------
    st.subheader("1. 판매 현황 (부가세 포함)")
    
    # 보기 좋게 4열 배치
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("판매총액", f"{data['F_total']:,} 원")
    kpi2.metric("순매출액 (입금액)", f"{data['G_total']:,} 원")
    kpi3.metric("총 가동일수", f"{data['op_days']} 일")
    kpi4.metric("ADR (객단가)", f"{data['adr']:,.0f} 원")

    st.divider()

    # ---------------------------------------------------------
    # 2. 정산서 (핵심 결과)
    # ---------------------------------------------------------
    st.subheader("2. 정산서 (배당금)")
    
    # 강조 박스 (블루 톤)
    st.info(f"""
    ### 💰 배당 대상 순이익: {data['final_payout']:,} 원
    * 순이익({data['net_profit']:,}원)에서 위탁수수료 20%({data['commission']:,}원)를 제외한 금액입니다.
    """)

    st.divider()

    # ---------------------------------------------------------
    # 3. 정산 세부 내역 (요청하신 이미지 포맷 구현)
    # ---------------------------------------------------------
    st.subheader("3. 정산 세부 내역")
    
    # 표 데이터 생성
    # 컬럼: [항목, 금액, 매출대비, 비고]
    # 매출 기준은 순매출액(G_total)으로 잡습니다 (이미지의 100% 기준)
    base_revenue = data['G_total'] if data['G_total'] > 0 else 1
    
    rows = []
    
    # 3-1. 매출 및 비용 총계
    rows.append({
        "구분": "순매출액", 
        "금액": data['G_total'], 
        "매출대비": 1.0, 
        "비고": ""
    })
    rows.append({
        "구분": "총비용 (지출)", 
        "금액": data['total_expense'], 
        "매출대비": data['total_expense'] / base_revenue, 
        "비고": ""
    })
    
    # 3-2. 개별 비용 항목 추가
    for key, label in EXPENSE_ITEMS.items():
        cost = st.session_state.expenses[key]
        note = st.session_state.expense_notes.get(key, "")
        if cost != 0 or note != "": # 금액이 있거나 비고가 있으면 출력
            rows.append({
                "구분": f"  └ {label}", # 들여쓰기 느낌
                "금액": cost,
                "매출대비": cost / base_revenue,
                "비고": note
            })
            
    # 3-3. 이익 및 수수료
    rows.append({
        "구분": "순이익 (차감전)", 
        "금액": data['net_profit'], 
        "매출대비": data['net_profit'] / base_revenue, 
        "비고": "입금액 - 총비용"
    })
    rows.append({
        "구분": "위탁수수료", 
        "금액": data['commission'], 
        "매출대비": data['commission'] / base_revenue, 
        "비고": "순이익의 20%"
    })
    rows.append({
        "구분": "배당 대상 순이익", 
        "금액": data['final_payout'], 
        "매출대비": data['final_payout'] / base_revenue, 
        "비고": "최종 지급액"
    })

    df_detail = pd.DataFrame(rows)
    
    # 데이터프레임 스타일링 및 표시
    st.dataframe(
        df_detail,
        use_container_width=True,
        hide_index=True,
        column_config={
            "구분": st.column_config.TextColumn("구분"),
            "금액": st.column_config.NumberColumn("금액", format="%d원"),
            "매출대비": st.column_config.NumberColumn("매출대비", format="%.1f%%"),
            "비고": st.column_config.TextColumn("비고"),
        }
    )

    # ---------------------------------------------------------
    # 4. 파일 다운로드 (PDF / JSON)
    # ---------------------------------------------------------
    st.subheader("📥 데이터 및 리포트 다운로드")
    
    c1, c2 = st.columns(2)
    
    with c1:
        # JSON 저장
        save_data = {
            "ota_data": st.session_state.ota_df.to_dict(orient='records'),
            "expenses": st.session_state.expenses,
            "expense_notes": st.session_state.expense_notes
        }
        json_str = json.dumps(save_data, ensure_ascii=False, indent=4)
        st.download_button(
            "💾 현재 데이터 저장 (JSON)",
            data=json_str,
            file_name="settlement_data.json",
            mime="application/json"
        )
        
    with c2:
        # PDF 다운로드
        try:
            pdf_data = create_pdf(data, st.session_state.expenses, st.session_state.expense_notes)
            st.download_button(
                "📄 PDF 리포트 다운로드",
                data=pdf_data,
                file_name="settlement_report.pdf",
                mime="application/pdf",
                type="primary"
            )
            if not os.path.exists("NanumGothic.ttf"):
                st.caption("※ 한글 폰트(NanumGothic.ttf)가 없으면 PDF 글자가 깨질 수 있습니다.")
        except Exception as e:
            st.error(f"PDF 생성 오류: {e}")

if __name__ == "__main__":
    main()
