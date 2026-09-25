"""首页（系统总览页）内容。

由 app.py 通过 st.navigation 注册为「首页」。
"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src import ui
from src.risk import build_weather_snapshot


def main() -> None:
    garden = ui.select_garden()
    data = ui.get_weather(garden)

    st.title("🍵 茶园气象服务系统")
    st.markdown(
        f'<span class="garden-title">{garden["name"]}</span> '
        f'<span class="meta">｜ {garden["location"]} ｜ 品种 {garden["variety"]} '
        f'｜ 海拔 {garden["altitude_m"]}m</span>',
        unsafe_allow_html=True,
    )
    st.caption(garden.get("notes", ""))

    if data is None:
        st.stop()

    # 三引擎数据打底：归档今日预报 + 确保历史数据 + 懒加载/训练模型
    try:
        from src import ensemble
        ensemble.prepare(garden, data)
    except Exception:  # noqa: BLE001
        pass

    now = data["now"]["now"]
    daily = data["daily"]["daily"]

    col_cur, col_risk = st.columns([2, 1])

    with col_cur:
        st.subheader("🌡 实时天气")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("气温", f"{now['temp']}°C", f"体感 {now['feelsLike']}°C")
        m2.metric("天气", now["text"], now["windDir"])
        m3.metric("湿度", f"{now['humidity']}%", None)
        m4.metric("风力", f"{now['windScale']} 级", f"{now['windSpeed']} km/h")

        st.subheader("📈 未来 7 天气温与降水")
        days = [d["fxDate"][5:] for d in daily]
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=days, y=[float(d["tempMax"]) for d in daily],
            name="最高温", mode="lines+markers", line=dict(color="#d64545"),
        ))
        fig.add_trace(go.Scatter(
            x=days, y=[float(d["tempMin"]) for d in daily],
            name="最低温", mode="lines+markers", line=dict(color="#2e6bb0"),
        ))
        fig.add_trace(go.Bar(
            x=days, y=[float(d["precip"]) for d in daily],
            name="降水量(mm)", yaxis="y2", marker_color="#7fb3e0",
        ))
        fig.update_layout(
            height=320, margin=dict(l=10, r=10, t=30, b=10),
            legend=dict(orientation="h", y=1.08),
            yaxis=dict(title="温度(°C)"),
            yaxis2=dict(title="降水(mm)", overlaying="y", side="right", showgrid=False),
            hovermode="x unified",
        )
        st.plotly_chart(fig, width="stretch")

    with col_risk:
        engine = ui.risk_engine()
        overall = engine.assess_all(now, daily)
        ui.overall_risk_banner(overall)

        st.subheader("⚠️ 当前风险提示")
        if overall["items"]:
            for item in overall["items"][:3]:
                ui.render_risk_item(item)
        else:
            st.success("暂未检测到明显的气象灾害或病虫害风险")

        st.subheader("🤖 大模型研判")
        snapshot = build_weather_snapshot(garden, data["now"], daily, data["air"])
        with st.expander("查看大模型研判结果"):
            if st.button("生成研判", key="home_llm"):
                from src.llm import QianfanClient
                try:
                    with st.spinner("千帆大模型研判中…"):
                        st.write(QianfanClient().assess_with_llm(snapshot))
                except Exception as e:  # noqa: BLE001
                    st.error(f"研判失败：{e}")
            else:
                st.info("点击上方按钮，调用伏羲/文心大模型对当前气象做智能研判。")

    st.divider()
    st.caption("📖 通过左侧页面切换：气象监测 ｜ 风险预警 ｜ 智能问答。数据来自和风天气 API，研判由百度千帆大模型与规则引擎联合完成。")
