"""时序模块（三引擎联动的【时序引擎】）。

职责（不重复和风 API 的 7 天预报）：
1. historical_window() —— 从 weather_history 提取"近 N 天气象窗口"的统计特征与趋势，
   作为环境上下文/ML 特征补充。
2. forecast() —— 用 statsforecast 的 AutoARIMA 对关键气象指标（最高温、降水）做未来
   数日预测，用于刻画"风险指标演化趋势"（高温天数、降雨累积等）。

全部 try/except 降级：无历史数据或 statsforecast 不可用时返回安全默认值，不影响主流程。
"""
from __future__ import annotations

from datetime import date

from . import db, risk


def historical_window(garden_key: str, window: int = 7) -> dict:
    """最近 window 天气象窗口的聚合特征。无数据时返回全空安全值。"""
    rows = db.weather_history_series(garden_key, days=window)
    if not rows:
        return {
            "temp_max_mean": 0.0, "temp_max_max": 0.0,
            "precip_sum": 0.0, "rainy_days": 0, "hot_days": 0,
            "temp_trend": 0.0, "humidity_mean": 0.0, "n": 0,
        }
    temps = [risk._num(r.get("temp_max")) for r in rows]
    precips = [risk._num(r.get("precip")) for r in rows]
    hums = [risk._num(r.get("humidity")) for r in rows]
    # 简单趋势：最近 window 天的线性趋势系数（归一化斜率）
    n = len(temps)
    x = list(range(n))
    x_mean = sum(x) / n
    y_mean = sum(temps) / n
    denom = sum((xi - x_mean) ** 2 for xi in x)
    slope = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, temps)) / denom if denom else 0.0
    return {
        "temp_max_mean": round(sum(temps) / n, 2),
        "temp_max_max": max(temps),
        "precip_sum": round(sum(precips), 2),
        "rainy_days": sum(1 for p in precips if p >= 10),
        "hot_days": sum(1 for t in temps if t >= 33),
        "temp_trend": round(slope, 3),
        "humidity_mean": round(sum(hums) / n, 1),
        "n": n,
    }


def forecast(garden_key: str, horizon: int = 3) -> dict | None:
    """对未来 horizon 天做 AutoARIMA 预测（temp_max 与 precip），返回预测序列或 None。

    返回: {"dates": [...], "temp_max": [...], "precip": [...]}
    数据不足(<15)或 statsforecast 不可用/全部指标拟合失败时返回 None。
    单条指标拟合失败不影响其它指标（逐序列独立降级）。
    """
    rows = db.weather_history_series(garden_key, days=120)
    if len(rows) < 15:
        return None
    try:
        from datetime import timedelta
        from statsforecast import StatsForecast
        from statsforecast.models import AutoARIMA
        import pandas as pd
    except Exception:  # noqa: BLE001
        return None

    out: dict = {"dates": [], "temp_max": [], "precip": []}
    for field, key in (("temp_max", "temp_max"), ("precip", "precip")):
        try:
            ys = [(str(r["obs_date"]), max(0.0, risk._num(r.get(field)))) for r in rows]
            df = pd.DataFrame(ys, columns=["ds", "y"])
            df["unique_id"] = "g"
            sf = StatsForecast(
                models=[AutoARIMA(season_length=7)],
                freq="D", n_jobs=1, verbose=False,
            )
            fcst = sf.forecast(df=df, h=horizon)
            out[key] = [round(max(0.0, float(p)), 1) for p in fcst["AutoARIMA"].tolist()]
        except Exception:  # noqa: BLE001 - 单条指标失败则跳过
            out[key] = []
    if not out["temp_max"] and not out["precip"]:
        return None
    last_date = date.fromisoformat(str(rows[-1]["obs_date"]))
    out["dates"] = [(last_date + timedelta(days=i + 1)).isoformat() for i in range(horizon)]
    return out
