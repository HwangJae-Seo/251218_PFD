import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="농작업 경제성 분석기 Pro", layout="wide")
st.title("🚜 농작업 경제성 및 효율 분석 프로토타입 v3.0 (Graph Ver.)")
st.markdown("### 📊 기계화 vs 인력(관행) 경제성 비교 분석")

# --- [사이드바: 글로벌 변수 설정] ---
st.sidebar.header("⚙️ 분석 파라미터 설정")
st.sidebar.info("보내주신 엑셀 기준(농진청 공식)을 적용했습니다.")

# 엑셀 기준 상수
SALVAGE_RATIO = st.sidebar.number_input("폐기가치율 (잔존가치)", value=0.05, format="%.2f", help="기본 5%")
REPAIR_RATIO = st.sidebar.number_input("연 수리비율", value=0.06, format="%.2f", help="기본 6%")
INTEREST_RATIO = st.sidebar.number_input("연 이자율", value=0.025, format="%.3f", help="기본 2.5%")
USEFUL_LIFE_DEFAULT = st.sidebar.number_input("기계 내구연한 (년)", value=5, help="기계 사용 가능 연수 (기본 5년)")

st.sidebar.markdown("---")
LABOR_COST_PER_DAY = st.sidebar.number_input("1일 노임 (원)", value=153294, help="약 15만 3천원")
WORK_HOURS_PER_DAY = st.sidebar.number_input("1일 작업 시간 (시간)", value=8)
FUEL_PRICE = st.sidebar.number_input("면세유 가격 (원/L)", value=1158, help="약 1,158원")

HOURLY_LABOR_COST = LABOR_COST_PER_DAY / WORK_HOURS_PER_DAY

# --- [데이터베이스(DB)] ---
tractor_db = [
    {"브랜드": "대동", "모델": "RX730VC5", "연료": "디젤", "연료소모량": 14.1, "구입가격": 60000000},
    {"브랜드": "LS엠트론", "모델": "LL3001", "연료": "디젤", "연료소모량": 15.1, "구입가격": 58000000}
]

implement_db = [
    {"종류": "정식기(엑셀모델)", "브랜드": "죽암엠앤씨", "모델": "JOPR-4/8A", "능률_ha_h": 0.0626, "구입가격": 49000000},
    {"종류": "휴립피복기", "브랜드": "불스", "모델": "BG-1200A", "능률_ha_h": 0.85, "구입가격": 11800000},
    {"종류": "굴취기", "브랜드": "신흥공업사", "모델": "SH-1400WN", "능률_ha_h": 0.123, "구입가격": 68000000},
    {"종류": "수집기", "브랜드": "신흥공업사", "모델": "SH-T1400", "능률_ha_h": 0.091, "구입가격": 18150000}
]

tractor_options = ["선택 안 함"] + [f"[{m['브랜드']}] {m['모델']}" for m in tractor_db]
implement_options = ["선택 안 함"] + [f"({m['종류']}) {m['브랜드']} {m['모델']}" for m in implement_db]

# --- [1. 분석 대상 설정] ---
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
st.header("2. 공정별 작업 조건 설정 (기계 vs 인력)")
processes = ["정식", "휴립피복", "방제", "굴취", "수집"] 
process_data = {}

# 탭 생성
tabs = st.tabs(processes)

# 각 공정별 기본 인력(관행) 능률 추정치 (단순 가정값)
manual_defaults = {
    "정식": 0.005, "휴립피복": 0.01, "방제": 0.1, "굴취": 0.01, "수집": 0.01
}

for i, proc in enumerate(processes):
    with tabs[i]:
        col_m1, col_m2 = st.columns(2)
        
        # --- [A. 기계 작업 설정] ---
        with col_m1:
            st.markdown(f"#### 🚜 [{proc}] 기계 작업 설정")
            sel_tractor = st.selectbox(f"트랙터 선택 ({proc})", tractor_options, key=f"tr_{proc}")
            sel_implement = st.selectbox(f"작업기 선택 ({proc})", implement_options, key=f"imp_{proc}")
            
            tr_info = next((m for m in tractor_db if f"[{m['브랜드']}] {m['모델']}" == sel_tractor), None)
            imp_info = next((m for m in implement_db if f"({m['종류']}) {m['브랜드']} {m['모델']}" == sel_implement), None)
            default_eff = imp_info["능률_ha_h"] if imp_info else 0.1
            
            c_eff1, c_eff2 = st.columns(2)
            with c_eff1:
                eff_ha = st.number_input(f"기계 능률 (ha/h)", value=default_eff, format="%.4f", key=f"eff_{proc}")
            with c_eff2:
                workers = st.number_input(f"기계 투입 인력 (명)", value=1, key=f"work_{proc}")
                
            # 연간 가동 시간 설정
            st.caption("※ 고정비 계산을 위한 연간 가동 시간")
            annual_use_opt = st.radio("가동 시간 기준", ["현재 면적만 작업", "다수 농가 작업(직접입력)"], key=f"opt_{proc}", label_visibility="collapsed")
            if annual_use_opt == "다수 농가 작업(직접입력)":
                calc_annual_hours = st.number_input(f"연간 총 가동(h)", value=200.0, key=f"anu_{proc}")
            else:
                calc_annual_hours = (area_ha / eff_ha) if eff_ha > 0 else 1.0

        # --- [B. 인력(관행) 작업 설정] ---
        with col_m2:
            st.markdown(f"#### 👩‍🌾 [{proc}] 인력(관행) 작업 설정")
            st.info("비교를 위한 순수 인력 작업 기준입니다.")
            
            man_eff_default = manual_defaults.get(proc, 0.01)
            c_man1, c_man2 = st.columns(2)
            with c_man1:
                man_eff = st.number_input(f"인력 능률 (ha/h)", value=man_eff_default, format="%.4f", key=f"man_eff_{proc}")
            with c_man2:
                man_workers = st.number_input(f"인력 투입 인력 (명)", value=5, help="인력 작업 시 필요 인원", key=f"man_work_{proc}")
                
            # 인력 작업 시 예상 시간
            man_time = area_ha / man_eff if man_eff > 0 else 0
            st.markdown(f"**예상 소요시간:** `{man_time:.1f} 시간`")

        # 데이터 저장
        req_time_mach = area_ha / eff_ha if eff_ha > 0 else 0
        process_data[proc] = {
            "트랙터": tr_info,
            "작업기": imp_info,
            "기계_인력": workers,
            "기계_능률": eff_ha,
            "기계_시간": req_time_mach,
            "기계_연간시간": calc_annual_hours,
            "관행_인력": man_workers,
            "관행_능률": man_eff,
            "관행_시간": man_time
        }

# --- [3. 경제성 분석 로직] ---
def calculate_fixed_cost(price, annual_hours, useful_life, current_hours):
    if price == 0 or annual_hours == 0: return 0
    salvage = price * SALVAGE_RATIO
    depreciation = (price - salvage) / useful_life
    repair = price * REPAIR_RATIO
    interest = price * INTEREST_RATIO
    hourly_fixed = (depreciation + repair + interest) / annual_hours
    return hourly_fixed * current_hours

st.header("3. 📈 경제성 분석 및 시각화")
st.markdown("---")

results = []

for proc, data in process_data.items():
    # 1. 기계 비용 계산
    mach_labor_cost = data["기계_시간"] * data["기계_인력"] * HOURLY_LABOR_COST
    mach_fuel_cost = 0
    if data["트랙터"]:
        mach_fuel_cost = data["트랙터"]["연료소모량"] * FUEL_PRICE * data["기계_시간"]
        
    mach_fixed_cost = 0
    if data["트랙터"]:
        mach_fixed_cost += calculate_fixed_cost(data["트랙터"]["구입가격"], data["기계_연간시간"], USEFUL_LIFE_DEFAULT, data["기계_시간"])
    if data["작업기"]:
        mach_fixed_cost += calculate_fixed_cost(data["작업기"]["구입가격"], data["기계_연간시간"], USEFUL_LIFE_DEFAULT, data["기계_시간"])
        
    total_mach_cost = mach_labor_cost + mach_fuel_cost + mach_fixed_cost
    
    # 2. 인력(관행) 비용 계산 (고정비=0, 유류비=0 가정, 오직 인건비)
    man_labor_cost = data["관행_시간"] * data["관행_인력"] * HOURLY_LABOR_COST
    total_man_cost = man_labor_cost
    
    results.append({
        "공정": proc,
        "구분": "기계(선택)",
        "총비용": total_mach_cost,
        "시간": data["기계_시간"]
    })
    results.append({
        "공정": proc,
        "구분": "인력(관행)",
        "총비용": total_man_cost,
        "시간": data["관행_시간"]
    })

df_res = pd.DataFrame(results)

# --- [4. 결과 그래프 출력] ---

# 4-1. 공정별 비교 그래프
col_g1, col_g2 = st.columns(2)

with col_g1:
    st.subheader("📊 1. 공정별 비용 비교 (기계 vs 인력)")
    fig_bar = px.bar(
        df_res, 
        x="공정", 
        y="총비용", 
        color="구분", 
        barmode="group",
        text="총비용",
        title="공정별 소요 비용 비교",
        color_discrete_map={"기계(선택)": "#1f77b4", "인력(관행)": "#ff7f0e"}
    )
    fig_bar.update_traces(texttemplate='%{text:.2s}', textposition='outside')
    fig_bar.update_layout(yaxis_title="비용 (원)")
    st.plotly_chart(fig_bar, use_container_width=True)

with col_g2:
    st.subheader("⏱️ 2. 공정별 소요 시간 비교")
    fig_time = px.bar(
        df_res, 
        x="공정", 
        y="시간", 
        color="구분", 
        barmode="group",
        text="시간",
        title="공정별 작업 소요 시간(h) 비교",
        color_discrete_map={"기계(선택)": "#1f77b4", "인력(관행)": "#ff7f0e"}
    )
    fig_time.update_traces(texttemplate='%{text:.1f}h', textposition='outside')
    fig_time.update_layout(yaxis_title="시간 (Hour)")
    st.plotly_chart(fig_time, use_container_width=True)


# 4-2. 최종 총괄 비교
st.markdown("---")
st.subheader("🏆 최종 결과: 전체 공정 합계 비교")

total_mach_sum = df_res[df_res["구분"]=="기계(선택)"]["총비용"].sum()
total_man_sum = df_res[df_res["구분"]=="인력(관행)"]["총비용"].sum()

diff = total_man_sum - total_mach_sum

c_final1, c_final2 = st.columns([1, 2])

with c_final1:
    st.metric("기계화 전체 도입 시 총 비용", f"{total_mach_sum:,.0f} 원")
    st.metric("All 인력(관행) 작업 시 총 비용", f"{total_man_sum:,.0f} 원")
    
    if diff > 0:
        st.success(f"🎉 기계화 도입 시 **{diff:,.0f} 원** 절감 가능!")
    else:
        st.error(f"⚠️ 현재 면적/가동시간으로는 인력이 **{abs(diff):,.0f} 원** 더 저렴합니다.")

with c_final2:
    # 전체 비용 비교 파이차트 or 바차트
    summary_df = pd.DataFrame([
        {"방식": "기계화 전체 도입", "비용": total_mach_sum},
        {"방식": "All 인력(관행)", "비용": total_man_sum}
    ])
    fig_total = px.bar(summary_df, x="비용", y="방식", orientation='h', text="비용", color="방식", 
                       color_discrete_map={"기계화 전체 도입": "#1f77b4", "All 인력(관행)": "#ff7f0e"})
    fig_total.update_traces(texttemplate='%{text:,.0f} 원', textposition='inside')
    fig_total.update_layout(title="전체 공정 총 비용 비교", xaxis_title="총 비용 (원)")
    st.plotly_chart(fig_total, use_container_width=True)

# 4-3. 데이터 테이블 보기
with st.expander("📋 상세 데이터 테이블 보기"):
    st.dataframe(df_res.style.format({"총비용": "{:,.0f}", "시간": "{:.2f}"}))