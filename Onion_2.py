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
# default_eff_ha, default_workers: 초기 입력값
MECH_LEVELS = {
    "파종·육묘": [
        {
            "label": "인력 파종",
            "tractor_fuel_lph": 0.0,
            "assets": [],
            "default_eff_ha": 0.0312,  # 3.2 hr/10a
            "default_workers": 3,
        },
        {
            "label": "파종기",
            "tractor_fuel_lph": 8.0,
            "assets": [
                {"name": "트랙터(소형)", "price": 40000000, "life_years": 8},
                {"name": "파종기", "price": 8000000, "life_years": 7},
            ],
            "default_eff_ha": 0.2500,  # 0.4 hr/10a
            "default_workers": 1,
        },
    ],
    "정식 준비": [
        {
            "label": "동력방제기 + 휴립피복기",
            "tractor_fuel_lph": 12.0,
            "assets": [
                {"name": "트랙터(중형)", "price": 60000000, "life_years": 8},
                {"name": "휴립피복기", "price": 11800000, "life_years": 10},
                {"name": "동력방제기", "price": 1500000, "life_years": 7},
            ],
            "default_eff_ha": 0.0588,  # 1.7 hr/10a
            "default_workers": 1,
        },
        {
            "label": "복합휴립피복기",
            "tractor_fuel_lph": 13.5,
            "assets": [
                {"name": "트랙터(중형)", "price": 60000000, "life_years": 8},
                {"name": "복합휴립피복기", "price": 25000000, "life_years": 10},
            ],
            "default_eff_ha": 0.1429,  # 0.7 hr/10a
            "default_workers": 1,
        },
        {
            "label": "복합휴립피복기 (자율주행)",
            "tractor_fuel_lph": 13.5,
            "assets": [
                {"name": "트랙터(중형)", "price": 60000000, "life_years": 8},
                {"name": "복합휴립피복기", "price": 25000000, "life_years": 10},
                {"name": "자율주행키트", "price": 12000000, "life_years": 6},
            ],
            "default_eff_ha": 0.1429,  # 0.7 hr/10a (자율주행으로 인력 절감)
            "default_workers": 1,
        },
    ],
    "정식": [
        {
            "label": "인력 정식",
            "tractor_fuel_lph": 0.0,
            "assets": [],
            "default_eff_ha": 0.0031,  # 32 hr/10a
            "default_workers": 5,
        },
        {
            "label": "반자동 정식기",
            "tractor_fuel_lph": 0.0,
            "assets": [
                {"name": "반자동정식기", "price": 15000000, "life_years": 7},
            ],
            "default_eff_ha": 0.0250,  # 4 hr/10a
            "default_workers": 3,
        },
        {
            "label": "정식기 (8조)",
            "tractor_fuel_lph": 10.0,
            "assets": [
                {"name": "트랙터(소형)", "price": 40000000, "life_years": 8},
                {"name": "자동정식기(8조)", "price": 49000000, "life_years": 5},
            ],
            "default_eff_ha": 0.0565,  # 1.77 hr/10a
            "default_workers": 2,
        },
        {
            "label": "정식기 (8조) (자율주행)",
            "tractor_fuel_lph": 10.0,
            "assets": [
                {"name": "트랙터(소형)", "price": 40000000, "life_years": 8},
                {"name": "자동정식기(8조)", "price": 49000000, "life_years": 5},
                {"name": "자율주행키트", "price": 12000000, "life_years": 6},
            ],
            "default_eff_ha": 0.0629,  # 1.59 hr/10a
            "default_workers": 1,
        },
    ],
    "방제": [
        {
            "label": "인력 방제",
            "tractor_fuel_lph": 0.0,
            "assets": [],
            "default_eff_ha": 0.1053,  # 0.95 hr/10a
            "default_workers": 2,
        },
        {
            "label": "동력방제기",
            "tractor_fuel_lph": 0.0,
            "assets": [
                {"name": "동력방제기", "price": 1500000, "life_years": 7},
            ],
            "default_eff_ha": 0.5988,  # 0.167 hr/10a
            "default_workers": 1,
        },
        {
            "label": "승용형 붐 스프레이어",
            "tractor_fuel_lph": 10.0,
            "assets": [
                {"name": "트랙터(중형)", "price": 60000000, "life_years": 8},
                {"name": "붐 스프레이어", "price": 35000000, "life_years": 10},
            ],
            "default_eff_ha": 1.2500,  # 0.08 hr/10a
            "default_workers": 1,
        },
        {
            "label": "방제 드론",
            "tractor_fuel_lph": 0.0,
            "assets": [
                {"name": "농업용 드론", "price": 25000000, "life_years": 5},
            ],
            "default_eff_ha": 3.0303,  # 0.033 hr/10a
            "default_workers": 1,
        },
    ],
    "줄기절단": [
        {
            "label": "인력 줄기절단",
            "tractor_fuel_lph": 0.0,
            "assets": [],
            "default_eff_ha": 0.0058,  # 17.2 hr/10a
            "default_workers": 5,
        },
        {
            "label": "줄기절단기",
            "tractor_fuel_lph": 12.0,
            "assets": [
                {"name": "트랙터(중형)", "price": 60000000, "life_years": 8},
                {"name": "줄기절단기", "price": 5000000, "life_years": 10},
            ],
            "default_eff_ha": 0.2000,  # 0.5 hr/10a
            "default_workers": 1,
        },
    ],
    "수확": [
        {
            "label": "굴취기 + 인력 수집",
            "tractor_fuel_lph": 14.0,
            "assets": [
                {"name": "트랙터(대형)", "price": 70000000, "life_years": 8},
                {"name": "굴취기", "price": 68000000, "life_years": 9},
            ],
            "default_eff_ha": 0.0032,  # 31.7 hr/10a
            "default_workers": 5,
        },
        {
            "label": "굴취기 + 수집기",
            "tractor_fuel_lph": 16.0,
            "assets": [
                {"name": "트랙터(대형)", "price": 70000000, "life_years": 8},
                {"name": "굴취기", "price": 68000000, "life_years": 9},
                {"name": "수집기", "price": 18150000, "life_years": 9},
            ],
            "default_eff_ha": 0.0671,  # 1.49 hr/10a
            "default_workers": 2,
        },
        {
            "label": "일관 수확기",
            "tractor_fuel_lph": 18.0,
            "assets": [
                {"name": "일관수확기", "price": 180000000, "life_years": 10},
            ],
            "default_eff_ha": 0.0943,  # 1.06 hr/10a
            "default_workers": 1,
        },
        {
            "label": "일관 수확기 (자율주행)",
            "tractor_fuel_lph": 18.0,
            "assets": [
                {"name": "일관수확기", "price": 180000000, "life_years": 10},
                {"name": "자율주행키트", "price": 15000000, "life_years": 6},
            ],
            "default_eff_ha": 0.0943,  # 1.06 hr/10a (자율주행으로 인력 절감)
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

processes = ["파종·육묘", "정식 준비", "정식", "방제", "줄기절단", "수확"]
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
    
    # 기계화 수준 선택
    sel_level_idx = st.selectbox(
        f"{role} 기계화 수준",
        range(len(level_labels)),
        format_func=lambda x: level_labels[x],
        key=f"lvl_{role}_{proc}"
    )
    level = level_items[sel_level_idx]

    asset_names = ", ".join([a["name"] for a in level.get("assets", [])]) if level.get("assets") else "없음(인력 중심)"
    st.caption(f"ℹ️ 고정비 대상 자산: {asset_names}")
    st.caption(f"⛽ 연료소모(시간당): {float(level.get('tractor_fuel_lph', 0.0)):.1f} L/h")

    # 선택된 레벨의 기본값을 사용 (매번 업데이트됨)
    default_eff = float(level["default_eff_ha"])
    default_work = int(level["default_workers"])

    c1, c2 = st.columns(2)
    with c1:
        eff_ha = st.number_input(
            "작업 능률 (ha/h)",
            value=default_eff,
            format="%.4f",
            key=f"eff_{role}_{proc}_{sel_level_idx}"  # 레벨 인덱스 포함하여 키 변경
        )
    with c2:
        workers = st.number_input(
            "투입 인력 (명)",
            value=default_work,
            min_value=0,
            step=1,
            key=f"work_{role}_{proc}_{sel_level_idx}"  # 레벨 인덱스 포함하여 키 변경
        )

    st.markdown("---")
    annual_use_opt = st.radio(
        "연간 가동 시간 기준 (고정비 산출용)",
        ["현재 면적만", "직접 입력"],
        key=f"opt_{role}_{proc}_{sel_level_idx}",
        horizontal=True
    )

    if annual_use_opt == "직접 입력":
        annual_hours = st.number_input(
            "연간 예상 가동시간(h)",
            value=200.0,
            min_value=1.0,
            step=10.0,
            key=f"anu_{role}_{proc}_{sel_level_idx}",
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
st.header("3. 📈 분석 결과")
st.markdown("---")

# 면적 범위 설정 (꺾은선 그래프용)
st.subheader("📐 단위면적당 비용 분석 면적 범위 설정")
col_range1, col_range2 = st.columns(2)
with col_range1:
    area_min_ha = st.number_input("최소 면적 (ha)", value=1.0, min_value=0.1, step=0.5)
with col_range2:
    area_max_ha = st.number_input("최대 면적 (ha)", value=10.0, min_value=0.5, step=0.5)
area_steps = st.slider("면적 구간 수", min_value=5, max_value=30, value=10)

import numpy as np
area_range = np.linspace(area_min_ha, area_max_ha, area_steps)

# 공정별 고정비·유동비 계산 (면적 독립 부분)
def compute_plan_costs(s):
    """
    한 계획(plan)에 대해
    - total_fixed_cost: 전체 고정비 합계 (원) - 면적에 무관
    - hourly_variable: 시간당 유동비 (원/h)
    - eff_ha: 작업 능률 (ha/h)
    반환
    """
    level = s["level"]
    hourly_fuel = float(level.get("tractor_fuel_lph", 0.0)) * FUEL_PRICE
    hourly_labor = float(s["workers"]) * UNIT_HOURLY_WAGE
    hourly_variable = hourly_fuel + hourly_labor

    # 고정비: 연간 가동시간을 '현재 면적만' 모드일 때 면적에 따라 재계산해야 하므로
    # asset별 연간비용(수리+이자+감가)을 먼저 계산
    annual_fixed_costs = []
    for asset in level.get("assets", []):
        price = float(asset["price"])
        life = float(asset["life_years"])
        salvage = price * RATIO_SALVAGE
        annual_repair = price * RATIO_REPAIR
        annual_interest = price * RATIO_INTEREST
        annual_depreciation = (price - salvage) / life
        annual_fixed = annual_repair + annual_interest + annual_depreciation
        annual_fixed_costs.append({
            "annual_fixed": annual_fixed,
            "price": price,
            "life": life,
            "annual_hours_mode": s.get("annual_hours_mode", "현재 면적만"),
            "annual_hours_fixed": float(s["annual_hours"]),  # 직접입력시 사용
        })

    return {
        "hourly_variable": hourly_variable,
        "annual_fixed_costs": annual_fixed_costs,
        "eff_ha": float(s["eff_ha"]),
        "level": level,
        "annual_hours_source": s["annual_hours"],
    }

# 면적별 단위비용 계산 함수
def cost_per_ha_for_area(plan_costs, target_area_ha):
    """
    target_area_ha: 분석 대상 면적 (ha)
    단위면적당 비용 (원/ha) 반환
    """
    eff = plan_costs["eff_ha"]
    if eff <= 0:
        return 0.0

    # 이 면적 작업에 필요한 총 시간
    total_hours = target_area_ha / eff

    # 유동비: 시간당 × 총 시간
    total_variable = plan_costs["hourly_variable"] * total_hours

    # 고정비: 연간고정비를 연간가동시간으로 나눈 시간당 고정비 × 총시간
    # "현재 면적만" 모드: 연간가동시간 = total_hours (이 면적만 작업)
    total_fixed = 0.0
    for afc in plan_costs["annual_fixed_costs"]:
        # 연간 가동시간: 항상 이 면적에 해당하는 시간으로 재계산
        # (사용자가 직접 입력한 경우라도 단위비용 곡선은 면적 변화에 따라 보여줌)
        annual_hours_for_area = target_area_ha / eff
        hourly_fixed = afc["annual_fixed"] / annual_hours_for_area if annual_hours_for_area > 0 else 0
        total_fixed += hourly_fixed * total_hours

    total_cost = total_variable + total_fixed
    return total_cost / target_area_ha  # 원/ha

# 공정별 계획 비용 파라미터 계산
plan_params = {}
for proc, pdata in process_data.items():
    plan_params[proc] = {}
    for role in ["도입안", "비교안"]:
        plan_params[proc][role] = compute_plan_costs(pdata[role])

# 현재 설정 면적(area_ha)에서의 결과 (기존 결과 테이블용)
results = []
for proc, pdata in process_data.items():
    for role in ["도입안", "비교안"]:
        s = pdata[role]
        level = s["level"]
        pc = plan_params[proc][role]

        hourly_variable = pc["hourly_variable"]
        eff = pc["eff_ha"]

        hourly_fixed = 0.0
        for asset in level.get("assets", []):
            hourly_fixed += calculate_hourly_fixed_cost(
                price=float(asset["price"]),
                annual_hours=float(s["annual_hours"]),
                useful_life=float(asset["life_years"])
            )

        hourly_total = hourly_variable + hourly_fixed

        if eff > 0:
            cost_per_ha = hourly_total / eff
            time_per_ha = 1.0 / eff
        else:
            cost_per_ha = 0.0
            time_per_ha = 0.0

        results.append({
            "공정": proc,
            "구분": role,
            "세부수준": level["label"],
            "ha당_비용(현재면적)": cost_per_ha,
            "ha당_시간": time_per_ha,
            "상세": f"시간당:{hourly_total:,.0f}원 (유동:{hourly_variable:,.0f} / 고정:{hourly_fixed:,.0f})"
        })

df_res = pd.DataFrame(results)

# --- [4. 그래프] ---

# 4-1. 면적별 단위비용 꺾은선 그래프 (전체 합산)
st.subheader("💰 면적별 단위면적당 총 비용 (원/ha) — 전 공정 합산")
st.caption("고정비는 총액이 일정하므로, 면적이 커질수록 단위비용이 감소합니다.")

line_data = []
for area in area_range:
    for role in ["도입안", "비교안"]:
        total_cost_per_ha = sum(
            cost_per_ha_for_area(plan_params[proc][role], area)
            for proc in processes
        )
        line_data.append({
            "면적 (ha)": round(area, 2),
            "구분": role,
            "단위비용 (원/ha)": total_cost_per_ha,
        })

df_line = pd.DataFrame(line_data)

fig_line = px.line(
    df_line,
    x="면적 (ha)",
    y="단위비용 (원/ha)",
    color="구분",
    markers=True,
    labels={"단위비용 (원/ha)": "단위면적당 비용 (원/ha)", "면적 (ha)": "작업 면적 (ha)"},
)
fig_line.update_traces(mode="lines+markers", marker=dict(size=7))
fig_line.update_layout(
    yaxis_title="비용 (원/ha)",
    xaxis_title="작업 면적 (ha)",
    legend_title_text="",
    hovermode="x unified"
)
# 현재 설정 면적 표시
fig_line.add_vline(
    x=area_ha,
    line_dash="dash",
    line_color="gray",
    annotation_text=f"현재 설정 면적 ({area_ha:.2f}ha)",
    annotation_position="top right"
)
st.plotly_chart(fig_line, use_container_width=True)

# 4-2. 공정별 꺾은선 그래프 (개별 공정)
st.subheader("📊 공정별 면적별 단위비용 비교")
proc_line_data = []
for area in area_range:
    for proc in processes:
        for role in ["도입안", "비교안"]:
            c = cost_per_ha_for_area(plan_params[proc][role], area)
            proc_line_data.append({
                "면적 (ha)": round(area, 2),
                "공정": proc,
                "구분": role,
                "단위비용 (원/ha)": c,
                "범례": f"{proc} ({role})",
            })

df_proc_line = pd.DataFrame(proc_line_data)

fig_proc = px.line(
    df_proc_line,
    x="면적 (ha)",
    y="단위비용 (원/ha)",
    color="범례",
    line_dash="구분",
    markers=True,
    facet_col="공정",
    facet_col_wrap=3,
    labels={"단위비용 (원/ha)": "원/ha"},
)
fig_proc.update_traces(marker=dict(size=5))
fig_proc.update_layout(legend_title_text="", hovermode="x unified")
fig_proc.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
st.plotly_chart(fig_proc, use_container_width=True)

# 4-3. 소요시간 비교 (기존 바 차트 유지)
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
st.subheader("📋 결과 테이블 (현재 설정 면적 기준)")
st.dataframe(df_res, use_container_width=True)

# --- [6. 요약 통계] ---
st.markdown("---")
col_s1, col_s2 = st.columns(2)

with col_s1:
    total_intro_cost = df_res[df_res["구분"] == "도입안"]["ha당_비용(현재면적)"].sum()
    total_base_cost = df_res[df_res["구분"] == "비교안"]["ha당_비용(현재면적)"].sum()
    diff_cost = total_base_cost - total_intro_cost

    st.info(f"**[비용 비교]** 현재 설정 면적 ({area_ha:.2f}ha) 기준, 단위면적당(원/ha)")
    st.write(f"비교안: {total_base_cost:,.0f} 원/ha vs 도입안: {total_intro_cost:,.0f} 원/ha")
    if diff_cost > 0:
        st.success(f"👉 도입안이 **{diff_cost:,.0f} 원/ha** 비용 절감")
    elif diff_cost < 0:
        st.error(f"👉 도입안이 **{abs(diff_cost):,.0f} 원/ha** 비용 증가")
    else:
        st.write("👉 비용 동일")

with col_s2:
    total_intro_time = df_res[df_res["구분"] == "도입안"]["ha당_시간"].sum()
    total_base_time = df_res[df_res["구분"] == "비교안"]["ha당_시간"].sum()
    diff_time = total_base_time - total_intro_time

    st.info("**[시간 비교]** 1ha 작업 시")
    st.write(f"비교안: {total_base_time:.1f} 시간 vs 도입안: {total_intro_time:.1f} 시간")
    if total_intro_time > 0 and diff_time > 0:
        st.success(f"👉 도입안이 **{diff_time:.1f} 시간** 단축 ({total_base_time/total_intro_time:.1f}배)")
    elif total_intro_time > 0 and diff_time < 0:
        st.error("👉 도입안이 더 오래 걸림")
    else:
        st.warning("👉 시간이 0으로 계산되었습니다(능률 설정 확인).")
