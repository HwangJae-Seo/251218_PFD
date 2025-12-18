import streamlit as st
import pandas as pd
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="농작업 경제성 분석기 Pro", layout="wide")
st.title("🚜 농작업 경제성 및 시간 효율 분석 (1ha 기준)")
st.markdown("### 📊 공정별 비용(원/ha) 및 소요시간(시간/ha) 비교 분석")

# --- [설정: 고정 상수 및 공식 파라미터] ---
RATIO_SALVAGE = 0.05   # 폐기가치율 5%
RATIO_REPAIR = 0.06    # 연 수리비율 6%
RATIO_INTEREST = 0.025 # 연 이자율 2.5%

# 트랙터 기본 내구연한
TRACTOR_LIFE_YEARS = 8 

# 작업기별 내구연한
IMPLEMENT_LIFE_MAP = {
    "휴립피복": 10, "정식": 5, "줄기절단": 10, "굴취": 9, "수집": 9
}

# 기계 작업 효율 기본값
DEFAULT_EFFICIENCY = {
    "휴립피복": 0.1, "정식": 0.06, "줄기절단": 0.3, "굴취": 0.2, "수집": 0.1
}

# --- [사이드바: 기본 환경 설정] ---
st.sidebar.header("⚙️ 환경 설정")
LABOR_COST_PER_DAY = st.sidebar.number_input("1일 노임 (원)", value=153294, help="기본값: 약 153,294원")
WORK_HOURS_PER_DAY = st.sidebar.number_input("1일 작업 시간 (시간)", value=8)
FUEL_PRICE = st.sidebar.number_input("면세유 가격 (원/L)", value=1158, help="기본값: 1,158원")

# 1인당 시간당 급여 (계산용 변수로만 사용하고 표시는 하지 않음)
UNIT_HOURLY_WAGE = LABOR_COST_PER_DAY / WORK_HOURS_PER_DAY

st.sidebar.info(
    f"""
    **[고정비 산출 기준]**
    * 수리비: {RATIO_REPAIR*100}% / 이자: {RATIO_INTEREST*100}%
    * 폐기율: {RATIO_SALVAGE*100}%
    """
)
# (시간당 인건비 표시는 사용자 요청으로 삭제함)

# --- [데이터베이스(DB)] ---
tractor_db = [
    {"브랜드": "대동", "모델": "RX730VC5", "연료": "디젤", "연료소모량": 14.1, "구입가격": 60000000},
    {"브랜드": "LS엠트론", "모델": "LL3001", "연료": "디젤", "연료소모량": 15.1, "구입가격": 58000000}
]

implement_db = [
    {"종류": "휴립피복기", "브랜드": "불스", "모델": "BG-1200A", "구입가격": 11800000},
    {"종류": "정식기", "브랜드": "죽암엠앤씨", "모델": "JOPR-4/8A", "구입가격": 49000000},
    {"종류": "줄기절단기", "브랜드": "기본모델", "모델": "SC-100", "구입가격": 5000000},
    {"종류": "굴취기", "브랜드": "신흥공업사", "모델": "SH-1400WN", "구입가격": 68000000},
    {"종류": "수집기", "브랜드": "신흥공업사", "모델": "SH-T1400", "구입가격": 18150000}
]

tractor_options = ["선택 안 함"] + [f"[{m['브랜드']}] {m['모델']}" for m in tractor_db]
implement_options = ["선택 안 함"] + [f"({m['종류']}) {m['브랜드']} {m['모델']}" for m in implement_db]

# --- [1. 분석 대상 면적 설정] ---
st.header("1. 분석 대상 면적 설정")
col1, col2 = st.columns([1, 2])
with col1:
    unit_type = st.radio("면적 단위", ["평", "ha", "a"], horizontal=True)
with col2:
    if unit_type == "평":
        input_area = st.number_input("면적 입력", value=3000.0)
        area_ha = input_area / 3025
    elif unit_type == "ha":
        input_area = st.number_input("면적 입력", value=1.0)
        area_ha = input_area
    else:
        input_area = st.number_input("면적 입력", value=100.0)
        area_ha = input_area / 100
st.info(f"📐 **환산 면적:** {area_ha:.4f} ha ({area_ha * 3025:,.0f} 평)")

# --- [2. 공정별 설정] ---
st.header("2. 공정별 작업 조건 설정")
processes = ["휴립피복", "정식", "줄기절단", "굴취", "수집"]
process_data = {}

tabs = st.tabs(processes)

# 사용자 요청 인력 능률 초기값 (ha/h)
manual_defaults = {
    "휴립피복": 0.0100, 
    "정식": 0.0020,     
    "줄기절단": 0.0048, 
    "굴취": 0.0032,     
    "수집": 0.0034      
}

for i, proc in enumerate(processes):
    with tabs[i]:
        col_m1, col_m2 = st.columns(2)
        
        # --- [A. 기계 작업 설정] ---
        with col_m1:
            st.markdown(f"#### 🚜 [{proc}] 기계 작업")
            sel_tractor = st.selectbox(f"트랙터 ({proc})", tractor_options, key=f"tr_{proc}")
            sel_implement = st.selectbox(f"작업기 ({proc})", implement_options, key=f"imp_{proc}")
            
            tr_info = next((m for m in tractor_db if f"[{m['브랜드']}] {m['모델']}" == sel_tractor), None)
            imp_info = next((m for m in implement_db if f"({m['종류']}) {m['브랜드']} {m['모델']}" == sel_implement), None)
            
            imp_life = IMPLEMENT_LIFE_MAP.get(proc, 5)
            st.caption(f"ℹ️ 적용 내구연한 - 트랙터: {TRACTOR_LIFE_YEARS}년, 작업기: {imp_life}년")

            default_val = DEFAULT_EFFICIENCY.get(proc, 0.1)
            c_eff1, c_eff2 = st.columns(2)
            with c_eff1:
                eff_ha = st.number_input(f"작업 능률 (ha/h)", value=default_val, format="%.4f", key=f"eff_{proc}")
            with c_eff2:
                workers = st.number_input(f"투입 인력 (명)", value=1, key=f"work_{proc}")
            
            # 연간 가동 시간 (고정비 산출용)
            st.markdown("---")
            annual_use_opt = st.radio("연간 가동 시간 기준 (고정비 산출용)", ["현재 면적만", "직접 입력"], key=f"opt_{proc}", horizontal=True)
            
            if annual_use_opt == "직접 입력":
                calc_annual_hours = st.number_input(f"연간 예상 가동시간(h)", value=200.0, key=f"anu_{proc}", help="이 기계가 1년 동안 작업하는 총 시간")
            else:
                calc_annual_hours = (area_ha / eff_ha) if eff_ha > 0 else 1.0
                st.caption(f"└ 1년 동안 이 면적({area_ha}ha)만 작업 시: 약 {calc_annual_hours:.1f}시간")

        # --- [B. 인력 작업 설정] ---
        with col_m2:
            st.markdown(f"#### 👩‍🌾 [{proc}] 인력(관행) 작업")
            man_eff_default = manual_defaults.get(proc, 0.01)
            
            c_man1, c_man2 = st.columns(2)
            with c_man1:
                man_eff = st.number_input(f"인력 능률 (ha/h)", value=man_eff_default, format="%.4f", key=f"man_eff_{proc}")
            with c_man2:
                man_workers = st.number_input(f"투입 인력 (명)", value=5, key=f"man_work_{proc}")
            
            # 참고용 소요시간 표시
            man_time_ref = area_ha / man_eff if man_eff > 0 else 0
            st.caption(f"참고: 현재 면적 작업 시 약 {man_time_ref:.1f}시간 소요 예상")

        # 데이터 저장
        process_data[proc] = {
            "트랙터": tr_info, "작업기": imp_info, 
            "기계_인력": workers, "기계_능률": eff_ha, "기계_연간시간": calc_annual_hours,
            "작업기_내구연한": imp_life,
            "관행_인력": man_workers, "관행_능률": man_eff
        }

# --- [3. 분석 로직 (비용 & 시간)] ---
def calculate_hourly_fixed_cost(price, annual_hours, useful_life):
    """ 시간당 고정비 = 연간총고정비 / 연간가동시간 """
    if price == 0 or annual_hours == 0: return 0
    annual_repair = price * RATIO_REPAIR
    annual_interest = price * RATIO_INTEREST
    salvage_value = price * RATIO_SALVAGE
    annual_depreciation = (price - salvage_value) / useful_life
    return (annual_repair + annual_interest + annual_depreciation) / annual_hours

st.header("3. 📈 분석 결과 (1ha 기준)")
st.markdown("---")

results = []

for proc, data in process_data.items():
    # -------------------------------------------
    # 1. 기계화 비용 및 시간 계산
    # -------------------------------------------
    
    # A. 시간당 유동비 (유류비 + 인건비)
    # 인건비 = 투입인원 * 1인당시급
    hourly_fuel = 0
    if data["트랙터"]:
        hourly_fuel = data["트랙터"]["연료소모량"] * FUEL_PRICE
    
    hourly_labor_mach = data["기계_인력"] * UNIT_HOURLY_WAGE
    hourly_variable_cost = hourly_fuel + hourly_labor_mach

    # B. 시간당 고정비
    hourly_fixed_cost = 0
    if data["트랙터"]:
        hourly_fixed_cost += calculate_hourly_fixed_cost(data["트랙터"]["구입가격"], data["기계_연간시간"], TRACTOR_LIFE_YEARS)
    if data["작업기"]:
        hourly_fixed_cost += calculate_hourly_fixed_cost(data["작업기"]["구입가격"], data["기계_연간시간"], data["작업기_내구연한"])

    # C. 시간당 총 비용
    hourly_total_cost_mach = hourly_variable_cost + hourly_fixed_cost

    # D. 결과 산출 (ha당 비용 & ha당 시간)
    if data["기계_능률"] > 0:
        mach_cost_per_ha = hourly_total_cost_mach / data["기계_능률"]
        mach_time_per_ha = 1 / data["기계_능률"] # 1ha 하는 데 걸리는 시간
    else:
        mach_cost_per_ha = 0
        mach_time_per_ha = 0

    results.append({
        "공정": proc, 
        "구분": "기계(선택)", 
        "ha당_비용": mach_cost_per_ha,
        "ha당_시간": mach_time_per_ha,
        "상세": f"시간당:{hourly_total_cost_mach:,.0f}원"
    })

    # -------------------------------------------
    # 2. 인력(관행) 비용 및 시간 계산
    # -------------------------------------------
    
    # A. 시간당 비용 (인건비만 존재, 투입인원 * 시급)
    hourly_total_cost_man = data["관행_인력"] * UNIT_HOURLY_WAGE

    # B. 결과 산출
    if data["관행_능률"] > 0:
        man_cost_per_ha = hourly_total_cost_man / data["관행_능률"]
        man_time_per_ha = 1 / data["관행_능률"]
    else:
        man_cost_per_ha = 0
        man_time_per_ha = 0

    results.append({
        "공정": proc, 
        "구분": "인력(관행)", 
        "ha당_비용": man_cost_per_ha,
        "ha당_시간": man_time_per_ha,
        "상세": f"시간당:{hourly_total_cost_man:,.0f}원"
    })

df_res = pd.DataFrame(results)

# --- [4. 그래프 시각화] ---
col_g1, col_g2 = st.columns(2)

with col_g1:
    st.subheader("💰 비용 비교 (원/ha)")
    fig_bar = px.bar(
        df_res, 
        x="공정", 
        y="ha당_비용", 
        color="구분", 
        barmode="group", 
        text="ha당_비용",
        color_discrete_map={"기계(선택)": "#1f77b4", "인력(관행)": "#ff7f0e"},
        labels={"ha당_비용": "단위 면적당 비용 (원/ha)"}
    )
    fig_bar.update_traces(texttemplate='%{text:,.0f}')
    fig_bar.update_layout(yaxis_title="비용 (원/ha)", legend_title_text='')
    st.plotly_chart(fig_bar, use_container_width=True)

with col_g2:
    st.subheader("⏱️ 소요 시간 비교 (시간/ha)")
    # [복구됨] 시간 비교 그래프
    fig_time = px.bar(
        df_res, 
        x="공정", 
        y="ha당_시간", 
        color="구분", 
        barmode="group", 
        text="ha당_시간",
        color_discrete_map={"기계(선택)": "#1f77b4", "인력(관행)": "#ff7f0e"},
        labels={"ha당_시간": "단위 면적당 시간 (h/ha)"}
    )
    fig_time.update_traces(texttemplate='%{text:.1f}h')
    fig_time.update_layout(yaxis_title="시간 (Hour/ha)", legend_title_text='')
    st.plotly_chart(fig_time, use_container_width=True)

# [요약 통계]
st.markdown("---")
col_s1, col_s2 = st.columns(2)

with col_s1:
    total_mach_cost = df_res[df_res["구분"]=="기계(선택)"]["ha당_비용"].sum()
    total_man_cost = df_res[df_res["구분"]=="인력(관행)"]["ha당_비용"].sum()
    diff_cost = total_man_cost - total_mach_cost
    
    st.info(f"**[비용 절감 효과]** 1ha 작업 시")
    st.write(f"관행: {total_man_cost:,.0f} 원 vs 기계: {total_mach_cost:,.0f} 원")
    if diff_cost > 0:
        st.success(f"👉 **{diff_cost:,.0f} 원** 절감")
    else:
        st.error(f"👉 **{abs(diff_cost):,.0f} 원** 손해 (가동시간 부족 등 원인)")

with col_s2:
    total_mach_time = df_res[df_res["구분"]=="기계(선택)"]["ha당_시간"].sum()
    total_man_time = df_res[df_res["구분"]=="인력(관행)"]["ha당_시간"].sum()
    diff_time = total_man_time - total_mach_time

    st.info(f"**[시간 단축 효과]** 1ha 작업 시")
    st.write(f"관행: {total_man_time:.1f} 시간 vs 기계: {total_mach_time:.1f} 시간")
    if diff_time > 0:
        st.success(f"👉 **{diff_time:.1f} 시간** 단축 ({total_man_time/total_mach_time:.1f}배 빠름)")
    else:
        st.error(f"👉 기계가 더 오래 걸림")