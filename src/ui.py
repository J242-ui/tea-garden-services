"""Streamlit 共享 UI 组件与数据加载。"""
from __future__ import annotations

import streamlit as st

from . import config, db, risk
from .weather import WeatherClient, WeatherError

LEVEL_COLOR = {"low": "#2e9e5b", "medium": "#e6a23c", "high": "#d64545"}
LEVEL_CN = {"low": "低风险", "medium": "中风险", "high": "高风险"}

# 用这个 key 区分花园 id 来源：数据库园以 rdb:ID 为 key，演示园用原 id


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .risk-badge { display:inline-block; padding:2px 10px; border-radius:12px;
                      color:#fff; font-size:13px; font-weight:600; }
        .garden-title { font-size:22px; font-weight:700; }
        .meta { color:#8a8f98; font-size:13px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _available_gardens() -> list[dict]:
    """已登录返回数据库里的自有茶园，否则返回演示茶园。统一转成带统一定位字段的 dict。"""
    user = st.session_state.get("user")
    if user:
        rows = db.user_gardens(user["id"])
        if rows:
            return [
                {
                    "key": f"rdb:{g['id']}",
                    "name": g["name"],
                    "location": g.get("location") or "",
                    "location_id": g.get("location_id") or "",
                    "lon": g.get("lon"),
                    "lat": g.get("lat"),
                    "variety": g.get("variety") or "",
                    "altitude_m": g.get("altitude_m"),
                    "notes": g.get("notes") or "",
                    "db_id": g["id"],
                }
                for g in rows
            ]
    # 演示园
    out = []
    for g in config.load_gardens():
        out.append({**g, "key": g["id"], "db_id": None})
    return out


def select_garden() -> dict:
    """侧边栏茶园选择：登录后看自有茶园，游客看演示园。返回园子 dict（含 key/db_id）。"""
    gardens = _available_gardens()
    if not gardens:
        st.sidebar.info("还没有茶园。登录后可到「我的茶园」添加。")
        st.stop()
    names = [g["name"] for g in gardens]
    current = st.session_state.get("garden_id")
    idx = 0
    for i, g in enumerate(gardens):
        if g["key"] == current:
            idx = i
            break

    with st.sidebar:
        _auth_ui()
        st.markdown("### 🍵 茶园选择")
        selected = st.selectbox("选择茶园", names, index=idx, label_visibility="collapsed")
        sel = gardens[names.index(selected)]
        st.caption(sel.get("location") or "")
        if st.button("🔄 刷新数据", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        st.divider()
        st.markdown("**数据源**")
        if config.get_weather_api_key():
            st.success("和风天气 已连接")
        else:
            st.warning("和风天气 演示模式")
        if config.get_qianfan_api_key():
            st.success("百度千帆 已连接")
        else:
            st.warning("百度千帆 演示模式")

    st.session_state["garden_id"] = sel["key"]
    return sel


def _loc_for(garden: dict) -> str:
    """返回查询定位：location_id 优先，否则经纬度。"""
    if garden.get("location_id"):
        return garden["location_id"]
    if garden.get("lon") is not None and garden.get("lat") is not None:
        return f"{garden['lon']},{garden['lat']}"
    return ""


@st.cache_data(ttl=600, show_spinner=False)
def _load_weather_cached(garden_key: str) -> dict:
    """内部缓存：先把园子 dict 序列化成稳定信息再取。"""
    gardens = _available_gardens()
    garden = next((g for g in gardens if g["key"] == garden_key), None)
    if garden is None:
        raise WeatherError("未找到该茶园")
    client = WeatherClient()
    loc = _loc_for(garden)
    if not loc:
        raise WeatherError("茶园缺少 location_id / 经纬度，无法查询天气")
    return {
        "now": client.get_now(loc),
        "daily": client.get_forecast(loc),
        "air": client.get_air(loc),
        "indices": client.get_indices(loc),
    }


def load_weather(garden: dict) -> dict:
    """按园子 dict 拉取天气（缓存 10 分钟）。兼容旧调用传 id 的写法。"""
    if isinstance(garden, str):
        # 兼容旧调用：config.get_garden(id)
        g = config.get_garden(garden)
        if g is None:
            raise WeatherError("未找到该茶园")
        garden = {**g, "key": g["id"], "db_id": None}
    return _load_weather_cached(garden["key"])


def get_weather(garden: dict) -> dict | None:
    """带错误处理的数据加载，失败返回 None。"""
    try:
        return load_weather(garden)
    except WeatherError as e:
        st.error(f"天气数据获取失败：{e}")
    except Exception as e:  # noqa: BLE001 - 网络/接口异常统一兜底
        st.error(f"天气数据获取失败：{e}")
    return None


def render_risk_item(item: dict) -> None:
    level = item["level"]
    color = LEVEL_COLOR[level]
    with st.container(border=True):
        col1, col2 = st.columns([3, 2])
        with col1:
            st.markdown(f"**{item['name']}**")
            st.write(item.get("condition", ""))
        with col2:
            st.markdown(
                f'<div class="risk-badge" style="background:{color}">{LEVEL_CN[level]}</div>',
                unsafe_allow_html=True,
            )
        st.caption(f"🛠 建议：{item.get('advice', '')}")


def overall_risk_banner(overall: dict) -> None:
    level = overall["overall_level"]
    color = LEVEL_COLOR[level]
    st.markdown(
        f"""
        <div style="border:1px solid {color};border-left:6px solid {color};
             border-radius:8px;padding:14px 18px;margin-bottom:12px">
          <span class="garden-title">综合风险等级：</span>
          <span class="risk-badge" style="background:{color};font-size:15px">
            {LEVEL_CN[level]}
          </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def risk_engine() -> risk.RiskEngine:
    return risk.RiskEngine()


def _auth_ui() -> None:
    """渲染账户登录入口（懒加载 auth_ui，避免与 ui 循环导入）。"""
    from .auth_ui import render_auth_ui
    render_auth_ui()
