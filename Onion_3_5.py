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

# --- [사이드바 1: 기본값 설정] ---
st.sidebar.header("⚙️ 기본값 설정")
LABOR_COST_PER_DAY = st.sidebar.number_input("1일 노임 (원)", value=153294, help="기본값: 약 153,294원")
st.sidebar.caption(f"💰 {LABOR_COST_PER_DAY:,} 원 ({LABOR_COST_PER_DAY // 10000:,} 만원)")
WORK_HOURS_PER_DAY = st.sidebar.number_input("1일 작업 시간 (시간)", value=8)
FUEL_PRICE = st.sidebar.number_input("면세유 가격 (원/L)", value=1158, help="기본값: 1,158원")
st.sidebar.caption(f"💰 {FUEL_PRICE:,} 원/L")

# 트랙터 가격 설정 (공통 자산)
st.sidebar.markdown("---")
st.sidebar.markdown("**🚜 트랙터 가격 설정** (공통 자산 — 전 공정 공유)")
st.sidebar.caption("트랙터는 여러 공정에 걸쳐 사용되므로 여기서 한 번만 입력합니다.")
TRACTOR_PRICE_VAL = st.sidebar.number_input("트랙터 가격 (원)", value=50000000, step=1000000, format="%d", key="tractor_price")
st.sidebar.caption(f"💰 {TRACTOR_PRICE_VAL:,} 원 ({TRACTOR_PRICE_VAL // 10000:,} 만원)")
TRACTOR_LIFE_YEARS = 8  # 트랙터 공통 내구연한

# 1인당 시간당 급여 (계산용 변수)
UNIT_HOURLY_WAGE = LABOR_COST_PER_DAY / WORK_HOURS_PER_DAY

# --- [사이드바 2: 계산식 보기] ---
st.sidebar.markdown("---")
st.sidebar.header("📐 계산식 보기")

with st.sidebar.expander("📌 고정비 계산식", expanded=False):
    st.markdown(
        f"""
**① 감가상각비 (연간)**
> (취득가격 - 폐기가치) ÷ 내구연한
> 폐기가치 = 취득가격 × {RATIO_SALVAGE*100:.1f}%

**② 수리비 (연간)**
> 취득가격 × {RATIO_REPAIR*100:.1f}%

**③ 이자 (연간)**
> 취득가격 × {RATIO_INTEREST*100:.1f}%

**④ 시간당 고정비**
> (감가상각비 + 수리비 + 이자) ÷ 연간 가동시간
"""
    )

with st.sidebar.expander("📌 유동비 계산식", expanded=False):
    st.markdown(
        f"""
**① 시간당 연료비**
> 연료소모량(L/h) × 유류비({FUEL_PRICE:,}원/L)

**② 시간당 인건비**
> 투입인력(명) × 시간당 노임({UNIT_HOURLY_WAGE:,.0f}원/h)
> ※ 시간당 노임 = 1일 노임 ÷ 1일 작업시간

**③ 시간당 유동비 합계**
> 시간당 연료비 + 시간당 인건비

**④ ha당 유동비**
> 시간당 유동비 ÷ 작업능률(ha/h)
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
            "tractor_type": None,
            "tractor_fuel_lph": 0.0,
            "assets": [],
            "default_eff_ha": 0.0312,
            "default_workers": 3,
        },
        {
            "label": "파종기",
            "tractor_type": None,   # 트랙터 미사용 (연료소모만 있음)
            "tractor_fuel_lph": 8.0,
            "assets": [
                {"name": "파종기", "price": 8000000, "life_years": 7},
            ],
            "default_eff_ha": 0.2500,
            "default_workers": 1,
        },
    ],
    "정식 준비": [
        {
            "label": "동력방제기 + 휴립피복기",
            "tractor_type": "트랙터",
            "tractor_fuel_lph": 12.0,
            "assets": [
                {"name": "휴립피복기", "price": 11800000, "life_years": 10},
                {"name": "동력방제기", "price": 1500000, "life_years": 7},
            ],
            "default_eff_ha": 0.0588,
            "default_workers": 1,
        },
        {
            "label": "복합휴립피복기",
            "tractor_type": "트랙터",
            "tractor_fuel_lph": 13.5,
            "assets": [
                {"name": "복합휴립피복기", "price": 25000000, "life_years": 10},
            ],
            "default_eff_ha": 0.1429,
            "default_workers": 1,
        },
        {
            "label": "복합휴립피복기 (자율주행)",
            "tractor_type": "트랙터",
            "tractor_fuel_lph": 13.5,
            "assets": [
                {"name": "복합휴립피복기", "price": 25000000, "life_years": 10},
                {"name": "자율주행키트", "price": 12000000, "life_years": 6},
            ],
            "default_eff_ha": 0.1429,
            "default_workers": 1,
        },
    ],
    "정식": [
        {
            "label": "인력 정식",
            "tractor_type": None,
            "tractor_fuel_lph": 0.0,
            "assets": [],
            "default_eff_ha": 0.0031,
            "default_workers": 5,
        },
        {
            "label": "반자동 정식기",
            "tractor_type": None,
            "tractor_fuel_lph": 0.0,
            "assets": [
                {"name": "반자동정식기", "price": 15000000, "life_years": 7},
            ],
            "default_eff_ha": 0.0250,
            "default_workers": 3,
        },
        {
            "label": "정식기 (8조)",
            "tractor_type": "트랙터",
            "tractor_fuel_lph": 10.0,
            "assets": [
                {"name": "자동정식기(8조)", "price": 49000000, "life_years": 5},
            ],
            "default_eff_ha": 0.0565,
            "default_workers": 2,
        },
        {
            "label": "정식기 (8조) (자율주행)",
            "tractor_type": "트랙터",
            "tractor_fuel_lph": 10.0,
            "assets": [
                {"name": "자동정식기(8조)", "price": 49000000, "life_years": 5},
                {"name": "자율주행키트", "price": 12000000, "life_years": 6},
            ],
            "default_eff_ha": 0.0629,
            "default_workers": 1,
        },
    ],
    "방제": [
        {
            "label": "인력 방제",
            "tractor_type": None,
            "tractor_fuel_lph": 0.0,
            "assets": [],
            "default_eff_ha": 0.1053,
            "default_workers": 2,
        },
        {
            "label": "동력방제기",
            "tractor_type": None,
            "tractor_fuel_lph": 0.0,
            "assets": [
                {"name": "동력방제기", "price": 1500000, "life_years": 7},
            ],
            "default_eff_ha": 0.5988,
            "default_workers": 1,
        },
        {
            "label": "승용형 붐 스프레이어",
            "tractor_type": "트랙터",
            "tractor_fuel_lph": 10.0,
            "assets": [
                {"name": "붐 스프레이어", "price": 35000000, "life_years": 10},
            ],
            "default_eff_ha": 1.2500,
            "default_workers": 1,
        },
        {
            "label": "방제 드론",
            "tractor_type": None,
            "tractor_fuel_lph": 0.0,
            "assets": [
                {"name": "농업용 드론", "price": 25000000, "life_years": 5},
            ],
            "default_eff_ha": 3.0303,
            "default_workers": 1,
        },
    ],
    "줄기절단": [
        {
            "label": "인력 줄기절단",
            "tractor_type": None,
            "tractor_fuel_lph": 0.0,
            "assets": [],
            "default_eff_ha": 0.0058,
            "default_workers": 5,
        },
        {
            "label": "줄기절단기",
            "tractor_type": "트랙터",
            "tractor_fuel_lph": 12.0,
            "assets": [
                {"name": "줄기절단기", "price": 5000000, "life_years": 10},
            ],
            "default_eff_ha": 0.2000,
            "default_workers": 1,
        },
    ],
    "수확": [
        {
            "label": "굴취기 + 인력 수집",
            "tractor_type": "트랙터",
            "tractor_fuel_lph": 14.0,
            "assets": [
                {"name": "굴취기", "price": 68000000, "life_years": 9},
            ],
            "default_eff_ha": 0.0032,
            "default_workers": 5,
        },
        {
            "label": "굴취기 + 수집기",
            "tractor_type": "트랙터",
            "tractor_fuel_lph": 16.0,
            "assets": [
                {"name": "굴취기", "price": 68000000, "life_years": 9},
                {"name": "수집기", "price": 18150000, "life_years": 9},
            ],
            "default_eff_ha": 0.0671,
            "default_workers": 2,
        },
        {
            "label": "일관 수확기",
            "tractor_type": None,
            "tractor_fuel_lph": 18.0,
            "assets": [
                {"name": "일관수확기", "price": 180000000, "life_years": 10},
            ],
            "default_eff_ha": 0.0943,
            "default_workers": 1,
        },
        {
            "label": "일관 수확기 (자율주행)",
            "tractor_type": None,
            "tractor_fuel_lph": 18.0,
            "assets": [
                {"name": "일관수확기", "price": 180000000, "life_years": 10},
                {"name": "자율주행키트", "price": 15000000, "life_years": 6},
            ],
            "default_eff_ha": 0.0943,
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
    tractor_type = level.get("tractor_type")
    if tractor_type:
        st.caption(f"ℹ️ 고정비 대상 자산: 트랙터 [공통 자산] + {asset_names}")
    else:
        st.caption(f"ℹ️ 고정비 대상 자산: {asset_names}")
    st.caption(f"⛽ 연료소모(시간당): {float(level.get('tractor_fuel_lph', 0.0)):.1f} L/h")

    # 작업기 가격 커스터마이징
    custom_assets = []
    if level.get("assets"):
        st.markdown("**🔧 작업기 가격 설정**")
        for a_idx, asset in enumerate(level["assets"]):
            custom_price = st.number_input(
                f"{asset['name']} 가격 (원)",
                value=int(asset["price"]),
                min_value=0,
                step=100000,
                format="%d",
                key=f"asset_price_{role}_{proc}_{sel_level_idx}_{a_idx}",
                help=f"기본값: {asset['price']:,}원 / 내구연한: {asset['life_years']}년"
            )
            st.caption(f"💰 **{custom_price:,} 원** ({custom_price // 10000:,} 만원)")
            custom_assets.append({
                "name": asset["name"],
                "price": custom_price,
                "life_years": asset["life_years"]
            })
    else:
        custom_assets = []

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
        "annual_hours": annual_hours,
        "custom_assets": custom_assets  # 사용자가 수정한 가격 (없으면 DB 기본값 그대로)
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
    assets_to_use = s.get("custom_assets") if s.get("custom_assets") else level.get("assets", [])
    for asset in assets_to_use:
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
        "tractor_type": level.get("tractor_type"),
    }

# 면적별 단위비용 계산 함수
def cost_per_ha_for_area(plan_costs, target_area_ha, role=None):
    """
    target_area_ha: 분석 대상 면적 (ha)
    단위면적당 비용 (원/ha) 반환
    트랙터 고정비는 해당 면적 기준 전체 공정 총 가동시간으로 안분
    """
    eff = plan_costs["eff_ha"]
    if eff <= 0:
        return 0.0

    total_hours = target_area_ha / eff
    total_variable = plan_costs["hourly_variable"] * total_hours

    # 작업기 고정비
    total_fixed = 0.0
    for afc in plan_costs["annual_fixed_costs"]:
        annual_hours_for_area = target_area_ha / eff
        hourly_fixed = afc["annual_fixed"] / annual_hours_for_area if annual_hours_for_area > 0 else 0
        total_fixed += hourly_fixed * total_hours

    # 트랙터 고정비 안분 (면적별 그래프용)
    tractor_type = plan_costs.get("tractor_type")
    if tractor_type and role and eff > 0:
        total_t_hours = 0.0
        for p in processes:
            if p in process_data:
                s2 = process_data[p][role]
                if s2["level"].get("tractor_type") == tractor_type:
                    e2 = float(s2["eff_ha"])
                    total_t_hours += (target_area_ha / e2) if e2 > 0 else 0.0
        if total_t_hours > 0:
            this_proc_hours = target_area_ha / eff
            tractor_share = this_proc_hours / total_t_hours
            total_fixed += TRACTOR_ANNUAL_FIXED * tractor_share

    total_cost = total_variable + total_fixed
    return total_cost / target_area_ha  # 원/ha

# --- [트랙터 연간 고정비 계산 (공통 자산)] ---
def calc_annual_fixed(price, life_years):
    salvage = price * RATIO_SALVAGE
    return price * RATIO_REPAIR + price * RATIO_INTEREST + (price - salvage) / life_years

TRACTOR_ANNUAL_FIXED = calc_annual_fixed(TRACTOR_PRICE_VAL, TRACTOR_LIFE_YEARS)

# 역할별로 트랙터 종류별 총 연간 가동시간 집계 (안분 분모)
# 각 공정의 연간 가동시간 = area_ha / eff_ha (현재 면적 기준)
tractor_total_hours = {"도입안": {}, "비교안": {}}
for role in ["도입안", "비교안"]:
    total_h = 0.0
    for proc, pdata in process_data.items():
        s = pdata[role]
        level = s["level"]
        if level.get("tractor_type") == "트랙터":
            eff = float(s["eff_ha"])
            total_h += (area_ha / eff) if eff > 0 else 0.0
    tractor_total_hours[role]["트랙터"] = total_h

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
        assets_to_use = s.get("custom_assets") if s.get("custom_assets") else level.get("assets", [])
        for asset in assets_to_use:
            hourly_fixed += calculate_hourly_fixed_cost(
                price=float(asset["price"]),
                annual_hours=float(s["annual_hours"]),
                useful_life=float(asset["life_years"])
            )

        # 트랙터 고정비 안분: 이 공정 가동시간 / 트랙터 전체 공정 총 가동시간
        tractor_type = level.get("tractor_type")
        if tractor_type and eff > 0:
            this_proc_hours = area_ha / eff
            total_t_hours = tractor_total_hours[role].get(tractor_type, 0.0)
            if total_t_hours > 0:
                tractor_share = this_proc_hours / total_t_hours
                hourly_fixed += (TRACTOR_ANNUAL_FIXED * tractor_share) / this_proc_hours

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
            cost_per_ha_for_area(plan_params[proc][role], area, role=role)
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
            c = cost_per_ha_for_area(plan_params[proc][role], area, role=role)
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
