import streamlit as st
import pandas as pd
from datetime import datetime

# --------------------------------------------------------------------------
# 1. 설정 및 상수 정의 (Configuration)
# --------------------------------------------------------------------------
st.set_page_config(page_title="숙박 위탁 정산 시스템", layout="wide", page_icon="🏨")

# OTA 리스트 및 컬럼 정의
OTA_LIST = ["아고다", "부킹닷컴", "에어비앤비", "트립닷컴", "야놀자게하", "야놀자펜션", "여기어때"]
COLS = {
    "D": "체크인건수(D)",
    "E": "숙박일수(E)",
    "F": "총매출액(F)",
    "G": "입금액(G)",
    "H": "플랫폼수수료(H)"
}

# 비용 항목 정의 (키: 라벨)
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
# 2. 로직 처리 함수 (Business Logic)
# --------------------------------------------------------------------------
def init_session_state():
    """세션 상태 초기화"""
    if 'ota_df' not in st.session_state:
        # 빈 데이터프레임 생성
        data = {"OTA": OTA_LIST}
        for col in COLS.values():
            data[col] = [0] * len(OTA_LIST)
        st.session_state.ota_df = pd.DataFrame(data)

    if 'expenses' not in st.session_state:
        # 비용 초기화 (모든 항목 0)
        st.session_state.expenses = {key: 0 for key in EXPENSE_ITEMS.keys()}
        st.session_state.expenses['operating_days'] = 0  # 가동일수는 별도 관리

def calculate_settlement(df, expenses):
    """
    정산 요약 데이터를 계산하여 딕셔너리로 반환
    요청 공식: ADR = F0 / E0, 위탁수수료 = 순이익 * 20%
    """
    # 1. OTA 합계 계산
    sums = df.sum(numeric_only=True)
    D0 = sums.get(COLS["D"], 0) # 총 체크인
    E0 = sums.get(COLS["E"], 0) # 총 숙박일수
    F0 = sums.get(COLS["F"], 0) # 총 매출액
    G0 = sums.get(COLS["G"], 0) # 총 입금액 (플랫폼 정산액)

    # 2. 비용 합계 계산 (가동일수 제외)
    total_cost = sum(v for k, v in expenses.items() if k != 'operating_days')
    
    # 3. 핵심 지표 계산
    # ADR (객단가) 계산: 숙박일수가 0이면 0으로 처리 (ZeroDivisionError 방지)
    adr = (F0 / E0) if E0 > 0 else 0
    
    # 순이익 (Net Profit) = 입금액 - 총운영비용
    net_profit = G0 - total_cost
    
    # 위탁 수수료 (순이익의 20%)
    commission_fee = net_profit * 0.2
    
    # 호스트 최종 정산금
    final_payout = net_profit - commission_fee

    return {
        "checkins": D0,
        "nights": E0,
        "gross_revenue": F0,
        "net_revenue": G0,
        "operating_days": expenses.get('operating_days', 0),
        "total_cost": total_cost,
        "adr": adr,
        "net_profit": net_profit,
        "commission_fee": commission_fee,
        "final_payout": final_payout
    }

# --------------------------------------------------------------------------
# 3. 메인 애플리케이션 (UI)
# --------------------------------------------------------------------------
def main():
    init_session_state()

    # 페이지 네비게이션 (사이드바 활용 권장)
    with st.sidebar:
        st.header("📌 메뉴")
        page = st.radio("이동할 페이지를 선택하세요", ["데이터 입력", "정산 보고서"])

    # --- 페이지 1: 데이터 입력 ---
    if page == "데이터 입력":
        st.title("📝 정산 데이터 입력")
        
        st.subheader("1. 플랫폼(OTA)별 매출 입력")
        st.caption("각 플랫폼의 관리자 페이지 내용을 아래 표에 입력해주세요.")
        
        # 데이터 에디터: 사용자가 직접 수정 가능
        edited_df = st.data_editor(
            st.session_state.ota_df,
            use_container_width=True,
            num_rows="fixed",
            hide_index=True,
            column_config={
                COLS["F"]: st.column_config.NumberColumn(format="%d원"),
                COLS["G"]: st.column_config.NumberColumn(format="%d원"),
            }
        )
        st.session_state.ota_df = edited_df

        st.divider()

        st.subheader("2. 월 운영 비용 입력")
        
        # 입력 폼을 4열로 깔끔하게 배치
        with st.container():
            col1, col2, col3, col4 = st.columns(4)
            cols = [col1, col2, col3, col4]
            
            # 비용 항목 반복문으로 생성 (DRY 원칙)
            for i, (key, label) in enumerate(EXPENSE_ITEMS.items()):
                with cols[i % 4]:
                    st.session_state.expenses[key] = st.number_input(
                        label, 
                        value=st.session_state.expenses[key],
                        step=10000,
                        format="%d"
                    )
            
            # 가동일수는 비용이 아니므로 별도 배치
            st.divider()
            st.session_state.expenses['operating_days'] = st.number_input(
                "📅 총 가동일수 (일)", 
                value=st.session_state.expenses['operating_days'],
                min_value=0, max_value=31
            )

        # 저장 버튼 (사실 session_state에 실시간 반영되지만, UX상 확인 절차 제공)
        if st.button("💾 입력 내용 저장 및 리포트 보기", type="primary", use_container_width=True):
            st.success("데이터가 저장되었습니다! 리포트 탭으로 이동합니다.")
            # 실제 페이지 이동은 사용자가 사이드바를 눌러야 하지만, 알림을 줌

    # --- 페이지 2: 정산 보고서 ---
    elif page == "정산 보고서":
        st.title("📊 월간 정산 보고서")
        
        # 계산 실행
        metrics = calculate_settlement(st.session_state.ota_df, st.session_state.expenses)

        # 1. 상단 핵심 지표 (Metrics)
        st.subheader("1. 핵심 요약")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("총 매출액 (Gross)", f"{metrics['gross_revenue']:,.0f} 원")
        m2.metric("객단가 (ADR)", f"{metrics['adr']:,.0f} 원", help="총매출액 / 숙박일수")
        m3.metric("총 비용 합계", f"{metrics['total_cost']:,.0f} 원")
        m4.metric("최종 정산금", f"{metrics['final_payout']:,.0f} 원", delta="순수익")

        st.divider()

        # 2. 상세 내역
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.subheader("2. 매출 상세")
            st.write(f"• 판매 총액 (F0): **{metrics['gross_revenue']:,.0f} 원**")
            st.write(f"• 입금 총액 (G0): **{metrics['net_revenue']:,.0f} 원**")
            st.write(f"• 총 숙박일수: {metrics['nights']} 박")
            st.write(f"• 총 가동일수: {metrics['operating_days']} 일")
            
        with col_right:
            st.subheader("3. 정산 상세")
            st.write(f"• 차감 전 순이익: **{metrics['net_profit']:,.0f} 원** (입금액 - 비용)")
            st.write(f"• 위탁 수수료 (20%): **{metrics['commission_fee']:,.0f} 원**")
            st.success(f"👉 **최종 배당금: {metrics['final_payout']:,.0f} 원**")

        st.info("💡 위 데이터는 입력된 값을 바탕으로 자동 계산되었습니다.")

        # 다운로드 기능 (단순 텍스트 리포트)
        report_text = f"""
        [숙박 위탁 정산 보고서]
        작성일: {datetime.now().strftime('%Y-%m-%d')}
        
        1. 매출 정보
        - 총 매출액: {metrics['gross_revenue']:,} 원
        - 총 입금액: {metrics['net_revenue']:,} 원
        - ADR: {metrics['adr']:,.0f} 원
        
        2. 비용 및 정산
        - 총 지출 비용: {metrics['total_cost']:,} 원
        - 위탁 수수료: {metrics['commission_fee']:,} 원
        - 최종 지급액: {metrics['final_payout']:,} 원
        """
        st.download_button("📥 리포트 텍스트 다운로드", report_text, file_name="report.txt")

if __name__ == "__main__":
    main()