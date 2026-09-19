"""农事智能问答页：携带当前气象与风险上下文的大模型对话。"""
from __future__ import annotations

import streamlit as st

from src import ui
from src.risk import build_weather_snapshot

st.set_page_config(page_title="智能问答", page_icon="🌱", layout="wide")
ui.inject_css()
garden = ui.select_garden()
data = ui.get_weather(garden)

st.title(f"🌱 农事智能问答 · {garden['name']}")

if data is None:
    st.stop()

now = data["now"]["now"]
daily = data["daily"]["daily"]
engine = ui.risk_engine()
overall = engine.assess_all(now, daily)

snapshot = build_weather_snapshot(garden, data["now"], daily, data["air"])
risk_text = "\n".join(
    f"- {i['name']}（{ui.LEVEL_CN[i['level']]}）：{i['condition']}；建议：{i['advice']}"
    for i in overall["items"]
)
context = f"{snapshot}\n\n【规则引擎风险研判】\n{risk_text if risk_text else '当前无明显风险'}"

with st.expander("🧾 对话上下文（系统自动附带）", expanded=False):
    st.code(context, language="text")

if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {
            "role": "assistant",
            "content": (
                "您好，我是茶园气象服务助手。我可以结合当前茶园的气象数据与风险研判，"
                "为您解答病虫害防治、灾害防范、采摘与施肥等农事问题。"
                "请问有什么可以帮您？"
            ),
        }
    ]

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("请输入您的农事问题，例如：最近适合打药吗？"):
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    from src.llm import QianfanClient

    with st.chat_message("assistant"):
        try:
            with st.spinner("思考中…"):
                reply = QianfanClient().ask_agri(prompt, context)
            st.markdown(reply)
            st.session_state["messages"].append({"role": "assistant", "content": reply})
        except Exception as e:  # noqa: BLE001
            st.error(f"大模型调用失败：{e}")

st.divider()
st.caption("💡 提示：切换侧边栏茶园或点击“刷新数据”后，对话上下文会自动更新。")
