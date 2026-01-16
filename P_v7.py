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

# --- [사이드바: 기본 환경 설정] ---
st.sidebar.header("⚙️ 환경 설정")
LABOR_COST_PER_DAY = st.sidebar.number_input("1일 노임 (원)", value=153294, help="기본값: 약 153,294원")
WORK_HOURS_PER_DAY = st.sidebar.number_input("1일 작업 시간 (시간)", value=8)
FUEL_PRICE = st.sidebar.number_input("면세유 가격 (원/L)", value=1158, help="기본값: 1,158원")

# 1인당 시간당 급여 (계산용 변수)
UNIT_HOURLY_WAGE = LABOR_COST_PER_DAY / WORK_HOURS_PER_DAY

st.sidebar.info(
    f"""
**[고정비 산출 기준]**
* 수리비: {RATIO_REPAIR*100:.1f}% / 이자: {RATIO_INTEREST*100:.1f}%
* 폐기율: {RATIO_SALVAGE*100:.1f}%
"""
)

# --- [기계화 수준 DB] -------------------------------------------------
# assets: 고정비 계산 대상(가격/내구연한)
# tractor_fuel_lph: 유류비(시간당) 계산용. 트랙터 없으면 0.
# default_eff_ha, default_workers: 초기 입력값(임의값 OK)
MECH_LEVELS = {
    "휴립피복": [
        {
            "label": "동력분무기 + 트랙터부착형 휴립피복기",
            "tractor_fuel_lph": 12.0,
            "assets": [
                {"name": "트랙터(중형)", "price": 60000000, "life_years": 8},
                {"name": "휴립피복기", "price": 11800000, "life_years": 10},
                {"name": "동력분무기", "price": 1500000, "life_years": 7},
            ],
            "default_eff_ha": 0.10,
            "default_workers": 1,
        },
        {
            "label": "트랙터부착형 복합휴립피복기 (방제+두둑성형+비닐피복)",
            "tractor_fuel_lph": 13.5,
            "assets": [
                {"name": "트랙터(중형)", "price": 60000000, "life_years": 8},
                {"name": "복합휴립피복기", "price": 25000000, "life_years": 10},
            ],
            "default_eff_ha": 0.13,
            "default_workers": 1,
        },
        {
            "label": "트랙터부착형 복합휴립피복기 + 자율주행키트",
            "tractor_fuel_lph": 13.5,
            "assets": [
                {"name": "트랙터(중형)", "price": 60000000, "life_years": 8},
                {"name": "복합휴립피복기", "price": 25000000, "life_years": 10},
                {"name": "자율주행키트", "price": 12000000, "life_years": 6},
            ],
            "default_eff_ha": 0.15,
            "default_workers": 1,
        },
    ],
    "정식": [
        {
            "label": "인력정식",
            "tractor_fuel_lph": 0.0,
            "assets": [],
            "default_eff_ha": 0.0020,
            "default_workers": 5,
        },
        {
            "label": "반자동 정식기",
            "tractor_fuel_lph": 0.0,
            "assets": [
                {"name": "반자동정식기", "price": 15000000, "life_years": 7},
            ],
            "default_eff_ha": 0.020,
            "default_workers": 3,
        },
        {
            "label": "자동 정식기",
            "tractor_fuel_lph": 10.0,
            "assets": [
                {"name": "트랙터(소형)", "price": 40000000, "life_years": 8},
                {"name": "자동정식기", "price": 49000000, "life_years": 5},
            ],
            "default_eff_ha": 0.060,
            "default_workers": 2,
        },
        {
            "label": "자동 정식기 + 자율주행키트",
            "tractor_fuel_lph": 10.0,
            "assets": [
                {"name": "트랙터(소형)", "price": 40000000, "life_years": 8},
                {"name": "자동정식기", "price": 49000000, "life_years": 5},
                {"name": "자율주행키트", "price": 12000000, "life_years": 6},
            ],
            "default_eff_ha": 0.070,
            "default_workers": 1,
        },
    ],
    "줄기절단": [
        {
            "label": "인력 줄기절단",
            "tractor_fuel_lph": 0.0,
            "assets": [],
            "default_eff_ha": 0.0048,
            "default_workers": 5,
        },
        {
            "label": "트랙터부착형 줄기절단기",
            "tractor_fuel_lph": 12.0,
            "assets": [
                {"name": "트랙터(중형)", "price": 60000000, "life_years": 8},
                {"name": "줄기절단기", "price": 5000000, "life_years": 10},
            ],
            "default_eff_ha": 0.30,
            "default_workers": 1,
        },
    ],
    "굴취·수집": [
        {
            "label": "트랙터부착형 굴취기 + 인력수집",
            "tractor_fuel_lph": 14.0,
            "assets": [
                {"name": "트랙터(대형)", "price": 70000000, "life_years": 8},
                {"name": "굴취기", "price": 68000000, "life_years": 9},
            ],
            "default_eff_ha": 0.18,
            "default_workers": 5,
        },
        {
            "label": "트랙터부착형 굴취기 + 트랙터부착형 수집기",
            "tractor_fuel_lph": 16.0,
            "assets": [
                {"name": "트랙터(대형)", "price": 70000000, "life_years": 8},
                {"name": "굴취기", "price": 68000000, "life_years": 9},
                {"name": "수집기", "price": 18150000, "life_years": 9},
            ],
            "default_eff_ha": 0.25,
            "default_workers": 2,
        },
        {
            "label": "일관 수확기",
            "tractor_fuel_lph": 18.0,
            "assets": [
                {"name": "일관수확기", "price": 180000000, "life_years": 10},
            ],
            "default_eff_ha": 0.35,
            "default_workers": 1,
        },
        {
            "label": "일관 수확기 + 자율주행키트",
            "tractor_fuel_lph": 18.0,
            "assets": [
                {"name": "일관수확기", "price": 180000000, "life_years": 10},
                {"name": "자율주행키트", "price": 15000000, "life_years": 6},
            ],
            "default_eff_ha": 0.40,
            "default_workers": 1,
        },
    ],
}

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

processes = ["휴립피복", "정식", "줄기절단", "굴취·수집"]
process_data = {}
tabs = st.tabs(processes)

def calculate_hourly_fixed_cost(price: float, annual_hours: float, useful_life: float) -> float:
    """시간당 고정비 = 연간(수리+이자+감가) / 연간가동시간"""
    if price <= 0 or annual_hours <= 0 or useful_life <= 0:
        return 0.0
    annual_repair = price * RATIO_REPAIR
    annual_interest = price * RATIO_INTEREST
    salvage_value = price * RATIO_SALVAGE
    annual_depreciation = (price - salvage_value) / useful_life
    return (annual_repair + annual_interest + annual_depreciation) / annual_hours

def render_plan_panel(proc: str, role: str):
    """role: '도입안' 또는 '비교안'"""
    st.markdown(f"#### 🧩 [{proc}] {role}")

    level_items = MECH_LEVELS.get(proc, [])
    if not level_items:
        st.error("이 공정에 대한 기계화 수준 DB가 없습니다.")
        st.stop()

    level_labels = [x["label"] for x in level_items]
    sel_level = st.selectbox(
        f"{role} 기계화 수준",
        level_labels,
        key=f"lvl_{role}_{proc}"
    )
    level = next(x for x in level_items if x["label"] == sel_level)

    asset_names = ", ".join([a["name"] for a in level.get("assets", [])]) if level.get("assets") else "없음(인력 중심)"
    st.caption(f"ℹ️ 고정비 대상 자산: {asset_names}")
    st.caption(f"⛽ 연료소모(시간당): {float(level.get('tractor_fuel_lph', 0.0)):.1f} L/h")

    c1, c2 = st.columns(2)
    with c1:
        eff_ha = st.number_input(
            "작업 능률 (ha/h)",
            value=float(level["default_eff_ha"]),
            format="%.4f",
            key=f"eff_{role}_{proc}"
        )
    with c2:
        workers = st.number_input(
            "투입 인력 (명)",
            value=int(level["default_workers"]),
            min_value=0,
            step=1,
            key=f"work_{role}_{proc}"
        )

    st.markdown("---")
    annual_use_opt = st.radio(
        "연간 가동 시간 기준 (고정비 산출용)",
        ["현재 면적만", "직접 입력"],
        key=f"opt_{role}_{proc}",
        horizontal=True
    )

    if annual_use_opt == "직접 입력":
        annual_hours = st.number_input(
            "연간 예상 가동시간(h)",
            value=200.0,
            min_value=1.0,
            step=10.0,
            key=f"anu_{role}_{proc}",
            help="이 '패키지(트랙터/작업기/키트/장비)'가 1년 동안 작업하는 총 시간"
        )
    else:
        annual_hours = (area_ha / eff_ha) if eff_ha > 0 else 1.0
        st.caption(f"└ 1년 동안 이 면적({area_ha:.4f}ha)만 작업 시: 약 {annual_hours:.1f}시간")

    return {
        "level": level,
        "eff_ha": eff_ha,
        "workers": workers,
        "annual_hours": annual_hours
    }

for i, proc in enumerate(processes):
    with tabs[i]:
        col_left, col_right = st.columns(2)

        with col_left:
            plan_intro = render_plan_panel(proc, "도입안")

        with col_right:
            plan_base = render_plan_panel(proc, "비교안")

        process_data[proc] = {"도입안": plan_intro, "비교안": plan_base}

# --- [3. 분석 결과] ---
st.header("3. 📈 분석 결과 (1ha 기준)")
st.markdown("---")

results = []

for proc, pdata in process_data.items():
    for role in ["도입안", "비교안"]:
        s = pdata[role]
        level = s["level"]

        # 시간당 유류비 + 인건비(유동비)
        hourly_fuel = float(level.get("tractor_fuel_lph", 0.0)) * FUEL_PRICE
        hourly_labor = float(s["workers"]) * UNIT_HOURLY_WAGE
        hourly_variable = hourly_fuel + hourly_labor

        # 시간당 고정비(assets 합산)
        hourly_fixed = 0.0
        for asset in level.get("assets", []):
            hourly_fixed += calculate_hourly_fixed_cost(
                price=float(asset["price"]),
                annual_hours=float(s["annual_hours"]),
                useful_life=float(asset["life_years"])
            )

        hourly_total = hourly_variable + hourly_fixed

        if float(s["eff_ha"]) > 0:
            cost_per_ha = hourly_total / float(s["eff_ha"])
            time_per_ha = 1.0 / float(s["eff_ha"])
        else:
            cost_per_ha = 0.0
            time_per_ha = 0.0

        results.append({
            "공정": proc,
            "구분": role,
            "세부수준": level["label"],
            "ha당_비용": cost_per_ha,
            "ha당_시간": time_per_ha,
            "상세": f"시간당:{hourly_total:,.0f}원 (유동:{hourly_variable:,.0f} / 고정:{hourly_fixed:,.0f})"
        })

df_res = pd.DataFrame(results)

# --- [4. 그래프] ---
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
        labels={"ha당_비용": "단위 면적당 비용 (원/ha)"}
    )
    fig_bar.update_traces(texttemplate='%{text:,.0f}')
    fig_bar.update_layout(yaxis_title="비용 (원/ha)", legend_title_text="")
    st.plotly_chart(fig_bar, use_container_width=True)

with col_g2:
    st.subheader("⏱️ 소요 시간 비교 (시간/ha)")
    fig_time = px.bar(
        df_res,
        x="공정",
        y="ha당_시간",
        color="구분",
        barmode="group",
        text="ha당_시간",
        labels={"ha당_시간": "단위 면적당 시간 (h/ha)"}
    )
    fig_time.update_traces(texttemplate='%{text:.1f}h')
    fig_time.update_layout(yaxis_title="시간 (Hour/ha)", legend_title_text="")
    st.plotly_chart(fig_time, use_container_width=True)

# --- [5. 결과 테이블] ---
st.markdown("---")
st.subheader("📋 결과 테이블")
st.dataframe(df_res, use_container_width=True)

# --- [6. 요약 통계] ---
st.markdown("---")
col_s1, col_s2 = st.columns(2)

with col_s1:
    total_intro_cost = df_res[df_res["구분"] == "도입안"]["ha당_비용"].sum()
    total_base_cost = df_res[df_res["구분"] == "비교안"]["ha당_비용"].sum()
    diff_cost = total_base_cost - total_intro_cost  # (+)면 도입안이 절감

    st.info("**[비용 비교]** 1ha 작업 시")
    st.write(f"비교안: {total_base_cost:,.0f} 원 vs 도입안: {total_intro_cost:,.0f} 원")
    if diff_cost > 0:
        st.success(f"👉 도입안이 **{diff_cost:,.0f} 원** 비용 절감")
    elif diff_cost < 0:
        st.error(f"👉 도입안이 **{abs(diff_cost):,.0f} 원** 비용 증가")
    else:
        st.write("👉 비용 동일")

with col_s2:
    total_intro_time = df_res[df_res["구분"] == "도입안"]["ha당_시간"].sum()
    total_base_time = df_res[df_res["구분"] == "비교안"]["ha당_시간"].sum()
    diff_time = total_base_time - total_intro_time  # (+)면 도입안이 단축

    st.info("**[시간 비교]** 1ha 작업 시")
    st.write(f"비교안: {total_base_time:.1f} 시간 vs 도입안: {total_intro_time:.1f} 시간")
    if total_intro_time > 0 and diff_time > 0:
        st.success(f"👉 도입안이 **{diff_time:.1f} 시간** 단축 ({total_base_time/total_intro_time:.1f}배)")
    elif total_intro_time > 0 and diff_time < 0:
        st.error("👉 도입안이 더 오래 걸림")
    else:
        st.warning("👉 시간이 0으로 계산되었습니다(능률 설정 확인).")
