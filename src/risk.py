"""茶园气象风险研判引擎。

基于实时天气与逐日预报，结合茶园物候特征，用规则引擎研判：
- 气象灾害：低温冻害、高温热害、暴雨渍害、大风、干旱
- 茶树病虫害：茶小绿叶蝉、茶饼病、炭疽病、蚜虫、尺蠖、日灼等

输出统一为 {name, level, condition, advice} 结构，level 取值 low/medium/high。
"""
from __future__ import annotations

LEVEL_CN = {"low": "低风险", "medium": "中风险", "high": "高风险"}
_LEVEL_ORDER = {"low": 0, "medium": 1, "high": 2}


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _level(label: str) -> str:
    """按中文标签(低/中/高)返回内部 level。"""
    return {"低": "low", "中": "medium", "高": "high"}.get(label, "low")


def max_level(levels: list[str]) -> str:
    if not levels:
        return "low"
    return max(levels, key=lambda lv: _LEVEL_ORDER.get(lv, 0))


class RiskEngine:
    """组合多个研判规则，输出结构化风险列表。"""

    def __init__(self, rules: list | None = None):
        # 规则为无参可调用对象，返回 list[dict]，便于扩展与单测
        self.rules = rules if rules is not None else _DEFAULT_RULES

    def assess_disasters(self, now: dict, daily: list[dict]) -> list[dict]:
        return self._run("disasters", now, daily)

    def assess_pests(self, now: dict, daily: list[dict]) -> list[dict]:
        return self._run("pests", now, daily)

    def assess_all(self, now: dict, daily: list[dict]) -> dict:
        disasters = self.assess_disasters(now, daily)
        pests = self.assess_pests(now, daily)
        all_items = disasters + pests
        return {
            "disasters": disasters,
            "pests": pests,
            "items": all_items,
            "overall_level": max_level([i["level"] for i in all_items]),
        }

    def _run(self, group: str, now: dict, daily: list[dict]) -> list[dict]:
        out: list[dict] = []
        for rule in self.rules:
            if getattr(rule, "group", group) != group:
                continue
            item = rule(now, daily)
            if item:
                out.append(item)
        return sorted(out, key=lambda i: _LEVEL_ORDER.get(i["level"], 0), reverse=True)


# ---------------------------------------------------------------------------
# 气象灾害规则
# ---------------------------------------------------------------------------
def _disaster_rule(fn):
    fn.group = "disasters"
    return fn


@_disaster_rule
def rule_frost(now: dict, daily: list[dict]) -> dict | None:
    """低温冻害：以未来几天最低气温研判（春季倒春寒、冬季寒潮）。"""
    temp_mins = [_num(d.get("tempMin")) for d in daily]
    if not temp_mins:
        return None
    min_t = min(temp_mins)
    if min_t <= 0:
        return {"name": "低温冻害", "level": "high",
                "condition": f"未来 {len(daily)} 天最低气温低至 {min_t:.0f}°C，存在霜冻冻害风险",
                "advice": "覆盖遮阳网/防冻布，有条件的茶园可熏烟增温；对幼龄茶园优先浇透水保根防冻。"}
    if min_t <= 4:
        return {"name": "低温冻害", "level": "medium",
                "condition": f"未来 {len(daily)} 天最低气温约 {min_t:.0f}°C，昼夜温差大，易受倒春寒影响",
                "advice": "关注寒潮预警，提前喷施防冻剂或叶面肥，弱树、新芽重点防护。"}
    return None


@_disaster_rule
def rule_heat(now: dict, daily: list[dict]) -> dict | None:
    """高温热害。"""
    temp_maxs = [_num(d.get("tempMax")) for d in daily]
    if not temp_maxs:
        return None
    max_t = max(temp_maxs)
    if max_t >= 38:
        return {"name": "高温热害", "level": "high",
                "condition": f"未来 {len(daily)} 天最高气温可达 {max_t:.0f}°C，易灼伤新梢叶片",
                "advice": "及时浇灌/喷灌降温增湿，茶园覆盖遮阳网，避免高温时段修剪与施肥。"}
    if max_t >= 35:
        return {"name": "高温热害", "level": "medium",
                "condition": f"未来 {len(daily)} 天最高气温约 {max_t:.0f}°C，午后易出现热害",
                "advice": "关注午后高温，适时补水；有喷灌条件的茶园在高温时段短时喷灌降温。"}
    if max_t >= 33:
        return {"name": "高温热害", "level": "low",
                "condition": f"未来 {len(daily)} 天最高气温约 {max_t:.0f}°C，晴热时段注意补水",
                "advice": "午后小水勤浇，保持土壤湿润。"}
    return None


@_disaster_rule
def rule_heavy_rain(now: dict, daily: list[dict]) -> dict | None:
    """暴雨渍害。"""
    precip_max = max([_num(d.get("precip")) for d in daily] or [0.0])
    if precip_max >= 50:
        return {"name": "暴雨渍害", "level": "high",
                "condition": f"未来 {len(daily)} 天单日降水量可达 {precip_max:.0f}mm，茶园易积水渍害",
                "advice": "提前疏通排水沟渠，低洼茶园做好排涝准备；雨前暂停施肥与中耕。"}
    if precip_max >= 25:
        return {"name": "暴雨渍害", "level": "medium",
                "condition": f"未来 {len(daily)} 天单日降水量约 {precip_max:.0f}mm，需防范积水",
                "advice": "检查排水系统，雨后及时排除积水并松土透气。"}
    if precip_max >= 10:
        return {"name": "暴雨渍害", "level": "low",
                "condition": f"未来 {len(daily)} 天有降水（单日最大 {precip_max:.0f}mm）",
                "advice": "雨后注意排水，防止局部积水。"}
    return None


@_disaster_rule
def rule_wind(now: dict, daily: list[dict]) -> dict | None:
    """大风灾害。"""
    scales = [_num(d.get("windScaleDay")) for d in daily] + [_num(now.get("windScale"))]
    max_scale = max(scales) if scales else 0
    if max_scale >= 7:
        return {"name": "大风", "level": "high",
                "condition": f"最大风力约 {max_scale:.0f} 级，易吹折新梢、刮伤叶片",
                "advice": "加固茶园遮阳设施与防虫网，暂停露天喷药；新栽幼树做好支撑。"}
    if max_scale >= 6:
        return {"name": "大风", "level": "medium",
                "condition": f"最大风力约 {max_scale:.0f} 级，需注意田间作业安全",
                "advice": "减少高空作业与喷药，检查加固设施。"}
    return None


@_disaster_rule
def rule_drought(now: dict, daily: list[dict]) -> dict | None:
    """干旱：连续晴热少雨。"""
    hot_dry_days = sum(
        1 for d in daily
        if _num(d.get("precip")) < 5 and _num(d.get("tempMax")) >= 30
    )
    if hot_dry_days >= 4:
        return {"name": "干旱", "level": "high",
                "condition": f"未来 {len(daily)} 天中 {hot_dry_days} 天晴热少雨，土壤墒情易告急",
                "advice": "启动灌溉补水（以滴灌/喷灌为佳），茶园行间覆盖稻草保墒，避开正午浇灌。"}
    if hot_dry_days == 3:
        return {"name": "干旱", "level": "medium",
                "condition": f"未来 {len(daily)} 天约 {hot_dry_days} 天晴热少雨，需关注墒情",
                "advice": "密切监测土壤湿度，提前做好灌溉安排。"}
    return None


# ---------------------------------------------------------------------------
# 茶树病虫害规则
# ---------------------------------------------------------------------------
def _pest_rule(fn):
    fn.group = "pests"
    return fn


@_pest_rule
def rule_leafhopper(now: dict, daily: list[dict]) -> dict | None:
    """茶小绿叶蝉：20~28°C 且湿度较高时繁殖迅速，为夏秋茶主要害虫。"""
    temp = _num(now.get("temp"))
    hum = _num(now.get("humidity"))
    if 20 <= temp <= 28:
        if hum >= 60:
            return {"name": "茶小绿叶蝉", "level": "high",
                    "condition": f"当前 {temp:.0f}°C、湿度 {hum:.0f}%，处于其最适繁殖区间",
                    "advice": "及时田间监测虫口，达到防治指标选用生物农药（如绿僵菌）或黄板诱杀，轮换用药。"}
        return {"name": "茶小绿叶蝉", "level": "medium",
                "condition": f"当前 {temp:.0f}°C 处于其适生范围",
                "advice": "加密观测嫩梢虫情，设置诱虫板。"}
    return None


@_pest_rule
def rule_blister_blight(now: dict, daily: list[dict]) -> dict | None:
    """茶饼病：低温高湿（15~20°C、湿度>85%）高发，多雨季节重。"""
    temp = _num(now.get("temp"))
    hum = _num(now.get("humidity"))
    if 15 <= temp <= 20 and hum >= 85:
        return {"name": "茶饼病", "level": "high",
                "condition": f"当前 {temp:.0f}°C、湿度 {hum:.0f}%，低温高湿易诱发茶饼病",
                "advice": "雨后及时通风排湿，发病初期喷施苯醚甲环唑等保护性药剂，清除病叶病枝。"}
    if 15 <= temp <= 22 and hum >= 80:
        return {"name": "茶饼病", "level": "medium",
                "condition": f"当前 {temp:.0f}°C、湿度 {hum:.0f}%，需警惕病害发生",
                "advice": "关注持续降雨，雨前雨后喷施保护剂预防。"}
    return None


@_pest_rule
def rule_anthracnose(now: dict, daily: list[dict]) -> dict | None:
    """茶炭疽病：22~28°C 高湿高发。"""
    temp = _num(now.get("temp"))
    hum = _num(now.get("humidity"))
    if 22 <= temp <= 28 and hum >= 80:
        return {"name": "茶炭疽病", "level": "medium",
                "condition": f"当前 {temp:.0f}°C、湿度 {hum:.0f}%，高温高湿利于炭疽病蔓延",
                "advice": "及时清除病叶，喷施咪鲜胺/苯醚甲环唑，避免偏施氮肥旺长。"}
    return None


@_pest_rule
def rule_aphid(now: dict, daily: list[dict]) -> dict | None:
    """茶蚜：16~24°C 温暖少雨时易爆发。"""
    temp = _num(now.get("temp"))
    if 16 <= temp <= 24:
        return {"name": "茶蚜", "level": "medium",
                "condition": f"当前 {temp:.0f}°C 处于茶蚜适生温度",
                "advice": "检查嫩梢与叶背虫情，发生较重时喷施吡虫啉等并保护瓢虫等天敌。"}
    return None


@_pest_rule
def rule_geometer(now: dict, daily: list[dict]) -> dict | None:
    """茶尺蠖/茶毛虫：20~30°C 暴食期。"""
    temp = _num(now.get("temp"))
    if 20 <= temp <= 30:
        return {"name": "茶尺蠖/茶毛虫", "level": "low",
                "condition": f"当前 {temp:.0f}°C 适宜食叶害虫活动",
                "advice": "巡查茶蓬虫情，幼虫期可用苏云金杆菌(Bt)等生物农药防治。"}
    return None


@_pest_rule
def rule_sun_scald(now: dict, daily: list[dict]) -> dict | None:
    """日灼生理性危害：高温 + 低湿。"""
    temp_maxs = [_num(d.get("tempMax")) for d in daily]
    hum = _num(now.get("humidity"))
    max_t = max(temp_maxs) if temp_maxs else _num(now.get("temp"))
    if max_t >= 33 and hum < 40:
        return {"name": "日灼（生理性）", "level": "medium",
                "condition": f"最高 {max_t:.0f}°C 且湿度仅 {hum:.0f}%，强光下新叶易日灼",
                "advice": "午后遮阳、喷水增湿，避免强光时段修剪造成伤口。"}
    return None


_DEFAULT_RULES = [
    rule_frost, rule_heat, rule_heavy_rain, rule_wind, rule_drought,
    rule_leafhopper, rule_blister_blight, rule_anthracnose, rule_aphid,
    rule_geometer, rule_sun_scald,
]


def build_weather_snapshot(garden: dict, now: dict, daily: list[dict], air: dict | None = None) -> str:
    """将天气数据整理为便于大模型理解的中文快照文本。"""
    n = now.get("now", now)
    lines = [
        f"茶园：{garden.get('name', '')}（{garden.get('location', '')}）",
        f"当前时间：{n.get('obsTime', '')}",
        f"当前天气：{n.get('text', '')}，气温 {n.get('temp', '')}°C，体感 {n.get('feelsLike', '')}°C",
        f"湿度 {n.get('humidity', '')}%，风向 {n.get('windDir', '')} {n.get('windScale', '')} 级，",
        f"24h 降水 {n.get('precip', '')}mm，气压 {n.get('pressure', '')}hPa",
    ]
    if air and air.get("now"):
        a = air["now"]
        lines.append(f"空气质量：AQI {a.get('aqi', '-')}（{a.get('category', '-')}），PM2.5 {a.get('pm2p5', '-')}")
    if daily:
        lines.append("\n未来预报：")
        for d in daily[:5]:
            lines.append(
                f"  {d.get('fxDate', '')} {d.get('textDay', '')} "
                f"{d.get('tempMin', '')}~{d.get('tempMax', '')}°C，降水 {d.get('precip', '')}mm，"
                f"湿度 {d.get('humidity', '')}%，风力 {d.get('windScaleDay', '')} 级"
            )
    return "\n".join(lines)


# ===========================================================================
# 风险预警分级机制（预警中心）
# ---------------------------------------------------------------------------
# 将每条风险研判结果归档到某一档位，并给出对应处置动作，便于页面做“分级预警”：
#   act(红色·紧急处置)  -> 高风险：需立即采取行动
#   prevent(橙色·提前预防) -> 中风险：需在本周内落实预防措施
#   observe(黄色·持续观察) -> 低风险：注意观察、常备预案
# 台风/升级逻辑：整体预警档位由最高的单条风险决定；新增/升级风险视为触发预警。
# ===========================================================================

TIER_ORDER = {"observe": 0, "prevent": 1, "act": 2}
TIER_META = {
    "observe": {"label": "持续观察", "color": "#e6a23c"},
    "prevent": {"label": "提前预防", "color": "#f08c2e"},
    "act":     {"label": "紧急处置", "color": "#d64545"},
}


def tier_of(item: dict) -> str:
    """把单条风险(item, 含 level/name)归档到预警档位。"""
    lv = item.get("level", "low")
    if lv == "high":
        return "act"
    if lv == "medium":
        return "prevent"
    return "observe"


def tier_action(item: dict) -> str:
    """返回该风险当前档位下应采取的处置动作描述。"""
    tier = tier_of(item)
    act = {
        "act":     "⚠ 已达高风险：请按建议立即处置，切勿拖延；事关作物安全请优先处理。",
        "prevent": "⏱ 已达中风险：请在本周内落实预防措施，并留意后续天气预报变化。",
        "observe": "👀 目前仅低风险：注意观察，建议随时储备对应预案与物资。",
    }[tier]
    return act


def get_warning_system(item_colors: bool = True) -> dict:
    """给页面用的分级预警说明（是否显示颜色等）。"""
    return {k: {**v, "order": TIER_ORDER[k]} for k, v in TIER_META.items()}


def overall_tier(overall: dict) -> str:
    """综合判定整个茶园的预警档位（取最高的单条风险档位）。"""
    items = overall.get("items", [])
    if not items:
        return "observe"
    return max((tier_of(i) for i in items), key=lambda t: TIER_ORDER.get(t, 0))
