"""农事建议（智能推送）引擎：基于天气与茶园物候，生成日常农事参考建议。

说明：风险预警/告警逻辑已独立到风险研判与[风险预警]页；本模块专注生成
非紧急的日常农事操作建议（浇水/施肥/打药/采摘等），供 [农事建议] 页参考。

每条建议卡片统一为 {id, cat, level, time_text, title, body, advice, extra}：
- cat: water/fertilize/spray/harvest 农事类别（用于页面筛选）
- level: 固定为 low（参考性质，不构成风险告警）
"""
from __future__ import annotations

from datetime import date

from .risk import RiskEngine, _num

LEVEL_CN = {"low": "低", "medium": "中", "high": "高"}


CAT_CN = {"water": "浇水/灌溉", "fertilize": "施肥", "spray": "打药/防治", "harvest": "采摘/物候"}
CAT_ORDER = {"water": 0, "fertilize": 1, "spray": 2, "harvest": 3}


def _flag(overall: dict) -> dict:
    """从规则引擎结果里提取影响‘是否建议农事操作’的判断标志。"""
    items = overall.get("items", [])
    return {
        "has_high": any(i.get("level") == "high" for i in items),
        "has_drought": any(i.get("name") == "干旱" for i in items),
        "has_rain": any(i.get("name") == "暴雨渍害" for i in items),
    }


def build_routine_cards(
    garden: dict,
    now: dict,
    daily: list[dict],
    air: dict | None = None,
    overall: dict | None = None,
) -> list[dict]:
    """生成日常农事参考建议卡片（不包含风险告警，供农事建议页使用）。"""
    if overall is None:
        overall = RiskEngine().assess_all(now, daily)
    cards: list[dict] = []

    n = now.get("now", now)
    temp = _num(n.get("temp"))
    precip = _num(n.get("precip"))
    fl = _flag(overall)

    # --- 浇水 / 灌溉 ---
    if fl["has_drought"] and not fl["has_rain"]:
        cards.append({
            "id": "water-drought", "cat": "water", "level": "low", "time_text": "今日",
            "title": "浇水提醒（墒情偏干）",
            "body": "未来几天晴热少雨、墒情偏干，午后日照强。",
            "advice": "优先清晨或傍晚滴灌/喷灌补水，行间覆盖稻草保墒。", "extra": {},
        })
    elif not fl["has_rain"] and precip < 5 and temp >= 30:
        cards.append({
            "id": "water-hot", "cat": "water", "level": "low", "time_text": "今日",
            "title": "补水提醒（晴热）",
            "body": f"当前 {temp:.0f}°C 且降水少，晴热时段注意保墒。",
            "advice": "小水勤浇，避开正午浇灌；有喷灌条件的午后短时增湿。", "extra": {},
        })

    # --- 施肥 ---
    if 12 <= temp <= 25 and not fl["has_high"]:
        cards.append({
            "id": "fertilize-window", "cat": "fertilize", "level": "low", "time_text": "近日",
            "title": "施肥窗口",
            "body": f"气温 {temp:.0f}°C 适宜根系吸收，是追肥好时机。",
            "advice": "雨后墒情好时施速效氮肥，配合中耕浅埋。", "extra": {},
        })
    elif temp >= 33 and not fl["has_rain"]:
        cards.append({
            "id": "fertilize-pause", "cat": "fertilize", "level": "low", "time_text": "今日",
            "title": "暂缓施肥（高温）",
            "body": f"高温 {temp:.0f}°C 下施肥易伤根烧叶。",
            "advice": "避开高温时段，待气温回落后再追肥。", "extra": {},
        })

    # --- 打药 / 防治 ---
    if fl["has_rain"]:
        cards.append({
            "id": "spray-skip-rain", "cat": "spray", "level": "low", "time_text": "未来",
            "title": "请避开雨天施药",
            "body": "未来有较强降水，喷药易被冲刷、药效下降并污染水体。",
            "advice": "待雨停、叶面干爽后再施药。", "extra": {},
        })
    elif 15 <= temp <= 28 and not fl["has_high"]:
        cards.append({
            "id": "spray-window", "cat": "spray", "level": "low", "time_text": "近日",
            "title": "防治窗口",
            "body": f"气温 {temp:.0f}°C，适合开展病虫害防治作业（请结合风险预警页的虫情研判）。",
            "advice": "优先选用生物农药，选无风清晨或傍晚施药。", "extra": {},
        })

    # --- 采摘 / 物候 ---
    variety = str(garden.get("variety", ""))
    if ("龙井" in variety or "碧螺春" in variety) and 15 <= temp <= 25 and not fl["has_high"]:
        cards.append({
            "id": "harvest-window", "cat": "harvest", "level": "low", "time_text": "近日",
            "title": "采摘窗口",
            "body": f"{variety} 当前气温适宜，嫩芽长势良好可适时采摘。",
            "advice": "晴天露水干后开采，按一芽一叶/一芽二叶标准采。", "extra": {},
        })

    cards.sort(key=lambda c: CAT_ORDER.get(c.get("cat", 99), 99))
    return cards


# 兼容旧模块名：生成农事建议 = build_routine_cards
build_advisory_cards = build_routine_cards


def summarize(cards: list[dict]) -> dict:
    """按类别统计农事建议数量。"""
    by_cat: dict[str, int] = {}
    for c in cards:
        cat = c.get("cat", "other")
        by_cat[cat] = by_cat.get(cat, 0) + 1
    return {"total": len(cards), "by_cat": by_cat}


def today_range_text() -> str:
    t = date.today()
    return f"{t.month}月{t.day}日 · {t.strftime('%A')}"


def forecast_note(daily: list[dict]) -> str:
    if not daily:
        return ""
    hot = sum(1 for d in daily if _num(d.get("tempMax")) >= 33)
    rain = sum(1 for d in daily if _num(d.get("precip")) >= 10)
    parts = []
    if hot:
        parts.append(f"未来{len(daily)}天中{hot}天最高温≥33°C")
    if rain:
        parts.append(f"{rain}天有明显降水(≥10mm)")
    return "；".join(parts)
