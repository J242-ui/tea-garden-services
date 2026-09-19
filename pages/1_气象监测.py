"""气象监测页：实时天气、空气质量、7 天预报与生活指数。"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import ui

st.set_page_config(page_title="气象监测", page_icon="🌡", layout="wide")
ui.inject_css()
garden = ui.select_garden()
data = ui.get_weather(garden)

st.title(f"🌡 气象监测 · {garden['name']}")
if data is None:
    st.stop()

now = data["now"]["now"]
daily = data["daily"]["daily"]
air = data["air"]["now"]

# ---- 实时天气 ----
st.subheader("实时天气")
r1, r2, r3, r4 = st.columns(4)
r1.metric("气温", f"{now['temp']}°C", f"体感 {now['feelsLike']}°C", delta_color="off")
r2.metric("相对湿度", f"{now['humidity']}%", None)
r3.metric("降水(24h)", f"{now['precip']}mm", None)
r4.metric("气压", f"{now['pressure']} hPa", None)

r5, r6, r7, r8 = st.columns(4)
r5.metric("风向/风力", f"{now['windDir']} {now['windScale']}级", None)
r6.metric("风速", f"{now['windSpeed']} km/h", None)
r7.metric("能见度", f"{now['vis']} km", None)
r8.metric("云量", f"{now.get('cloud', '-')}%", None)
st.caption(f"观测时间：{now['obsTime']}")

# ---- 空气质量 ----
st.subheader("🌫 空气质量")
a1, a2, a3, a4 = st.columns(4)
a1.metric("AQI", air["aqi"], air["category"], delta_color="off")
a2.metric("PM2.5", f"{air['pm2p5']} μg/m³", None)
a3.metric("PM10", f"{air['pm10']} μg/m³", None)
a4.metric("首要污染物", air.get("primary", "—") if air.get("primary") != "NA" else "无", None)

# ---- 7 天预报 ----
st.subheader("📅 未来 7 天预报")

df = pd.DataFrame([
    {
        "日期": d["fxDate"],
        "白天": d["textDay"],
        "夜间": d["textNight"],
        "最高温(°C)": float(d["tempMax"]),
        "最低温(°C)": float(d["tempMin"]),
        "湿度(%)": float(d["humidity"]),
        "降水(mm)": float(d["precip"]),
        "风力(级)": float(d["windScaleDay"]),
        "风向": d["windDirDay"],
    }
    for d in daily
])
st.dataframe(df, use_container_width=True, hide_index=True)

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=df["日期"], y=df["最高温(°C)"], name="最高温",
    mode="lines+markers", line=dict(color="#d64545"),
))
fig.add_trace(go.Scatter(
    x=df["日期"], y=df["最低温(°C)"], name="最低温",
    mode="lines+markers", line=dict(color="#2e6bb0"),
))
fig.add_trace(go.Bar(
    x=df["日期"], y=df["降水(mm)"], name="降水(mm)",
    yaxis="y2", marker_color="#7fb3e0",
))
fig.update_layout(
    height=360, margin=dict(l=10, r=10, t=30, b=10),
    legend=dict(orientation="h", y=1.08),
    yaxis=dict(title="温度(°C)"),
    yaxis2=dict(title="降水(mm)", overlaying="y", side="right", showgrid=False),
    hovermode="x unified",
)
st.plotly_chart(fig, use_container_width=True)

# ---- 生活指数 ----
st.subheader("🧭 生活指数")
idx_list = data["indices"].get("daily", [])
if idx_list:
    i1, i2, i3 = st.columns(3)
    i4, i5, i6 = st.columns(3)
    cols = [i1, i2, i3, i4, i5, i6]
    for i, it in enumerate(idx_list[:6]):
        with cols[i]:
            st.metric(it["name"], it["category"], it.get("level", ""), delta_color="off")
            st.caption(it.get("text", ""))
