"""风险研判引擎单元测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.risk import RiskEngine  # noqa: E402


def make_now(temp="26", humidity="72", wind_scale="2", text="多云"):
    return {"temp": temp, "humidity": humidity, "windScale": wind_scale, "text": text}


def make_daily(temps_max, temps_min, precip, wind_scale="2", humidity="70"):
    import datetime

    today = datetime.date.today()
    return [
        {
            "fxDate": (today + datetime.timedelta(days=i)).isoformat(),
            "tempMax": str(t), "tempMin": str(t_min),
            "precip": str(p), "windScaleDay": wind_scale,
            "humidity": humidity, "textDay": "多云",
        }
        for i, (t, t_min, p) in enumerate(zip(temps_max, temps_min, precip))
    ]


def test_no_risk_in_mild_weather():
    engine = RiskEngine()
    # 30°C 且湿度 45%：不在叶蝉/蚜虫/病害的适生区间，也无灾害触发条件
    now = make_now(temp="30", humidity="45", wind_scale="1")
    daily = make_daily([28, 29, 28], [18, 19, 18], [0, 0, 0], wind_scale="1")
    result = engine.assess_all(now, daily)
    assert result["overall_level"] == "low"


def test_frost_high_risk():
    engine = RiskEngine()
    now = make_now(temp="2", humidity="80")
    daily = make_daily([6, 5, 7], [-2, 0, 1], [0, 0, 0])
    disasters = engine.assess_disasters(now, daily)
    frost = next(i for i in disasters if i["name"] == "低温冻害")
    assert frost["level"] == "high"


def test_heat_high_risk():
    engine = RiskEngine()
    now = make_now(temp="36", humidity="50")
    daily = make_daily([38, 39, 37], [24, 25, 24], [0, 0, 0])
    disasters = engine.assess_disasters(now, daily)
    heat = next(i for i in disasters if i["name"] == "高温热害")
    assert heat["level"] == "high"


def test_heavy_rain_high_risk():
    engine = RiskEngine()
    now = make_now(temp="24", humidity="90")
    daily = make_daily([26, 27, 25], [20, 21, 20], [55, 30, 5])
    disasters = engine.assess_disasters(now, daily)
    rain = next(i for i in disasters if i["name"] == "暴雨渍害")
    assert rain["level"] == "high"


def test_leafhopper_high_risk():
    engine = RiskEngine()
    now = make_now(temp="24", humidity="75")
    daily = make_daily([28, 29, 28], [22, 23, 22], [0, 0, 0])
    pests = engine.assess_pests(now, daily)
    leafhopper = next(i for i in pests if i["name"] == "茶小绿叶蝉")
    assert leafhopper["level"] == "high"


def test_blister_blight_high_risk():
    engine = RiskEngine()
    now = make_now(temp="18", humidity="88")
    daily = make_daily([22, 23, 22], [16, 17, 16], [10, 8, 5])
    pests = engine.assess_pests(now, daily)
    blight = next(i for i in pests if i["name"] == "茶饼病")
    assert blight["level"] == "high"


def test_drought_high_risk():
    engine = RiskEngine()
    now = make_now(temp="34", humidity="35")
    daily = make_daily([35, 36, 34, 35], [24, 25, 24, 25], [0, 0, 2, 1])
    disasters = engine.assess_disasters(now, daily)
    drought = next(i for i in disasters if i["name"] == "干旱")
    assert drought["level"] == "high"
