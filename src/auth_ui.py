"""登录 / 注册 / 用户态管理（Streamlit UI 层）。"""
from __future__ import annotations

import streamlit as st

from . import db


def current_user() -> dict | None:
    """返回当前登录用户 dict，未登录返回 None。"""
    return st.session_state.get("user")


def is_logged_in() -> bool:
    return bool(current_user())


def render_auth_ui() -> None:
    """在侧边栏渲染登录 / 注册 / 退出入口。"""
    user = current_user()
    with st.sidebar:
        st.markdown("### 👤 账户")
        if user:
            st.success(f"已登录：{user['nickname'] or user['username']}")
            if st.button("🚪 退出登录", width="stretch"):
                st.session_state.pop("user", None)
                st.session_state.pop("garden_id", None)
                st.cache_data.clear()
                st.rerun()
        else:
            tab_login, tab_reg = st.tabs(["登录", "注册"])
            with tab_login:
                u = st.text_input("用户名", key="auth_u", label_visibility="collapsed", placeholder="用户名")
                p = st.text_input("密码", type="password", key="auth_p", label_visibility="collapsed", placeholder="密码")
                if st.button("登录", key="auth_login", width="stretch"):
                    user = db.verify_login(u or "", p or "")
                    if user:
                        st.session_state["user"] = user
                        st.session_state.pop("garden_id", None)
                        st.success("登录成功")
                        st.rerun()
                    else:
                        _rem = db.login_remaining_lock(u or "")
                        if _rem is None:
                            st.error("登录失败次数过多，该用户名已临时锁定，请 15 分钟后再试")
                        elif _rem < 5:  # 已发生失败，提示剩余次数（最多 5 次）
                            st.error(f"用户名或密码错误（再错 {_rem} 次将临时锁定）")
                        else:
                            st.error("用户名或密码错误")
            with tab_reg:
                ru = st.text_input("用户名(≥2位)", key="reg_u", label_visibility="collapsed", placeholder="用户名")
                rp = st.text_input("密码(≥4位)", type="password", key="reg_p", label_visibility="collapsed", placeholder="密码")
                rn = st.text_input("昵称", key="reg_n", label_visibility="collapsed", placeholder="昵称(可选)")
                if st.button("注册", key="auth_reg", width="stretch"):
                    ok, msg = db.register(ru or "", rp or "", rn or None)
                    if ok:
                        st.success(msg)
                        st.info("请切到「登录」页登录")
                    else:
                        st.error(msg)
