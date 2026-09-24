"""三引擎训练/运行状态检查（跑完即删）。"""
import sys
from collections import Counter

sys.path.insert(0, ".")

from src import bandit, config, db, ml_risk, risk, ts
from src.weather import WeatherClient

gardens = config.load_gardens()
g = {**gardens[0], "key": gardens[0]["id"], "db_id": None}

print("=== 1. 历史气象数据（weather_history）===")
for gg in gardens:
    print(f"  {gg['name']:<10}({gg['id']}): {db.weather_history_count(gg['id'])} 天")

print("\n=== 2. ML 分类器状态 ===")
loaded = ml_risk.classifier.load()
print(f"  模型文件存在: {ml_risk.MODEL_PATH.exists()} | load成功: {loaded} | ready: {ml_risk.classifier.ready}")

print("\n=== 3. 训练标签分布（规则引擎弱标注）===")
engine = risk.RiskEngine()
hist = db.weather_history_series(g["key"], days=365)
labels = Counter()
for d in hist:
    now = {"temp": d["temp_max"], "humidity": d["humidity"], "windScale": d["wind_scale"]}
    daily = [{"fxDate": str(d["obs_date"]), "tempMax": d["temp_max"], "tempMin": d["temp_min"],
              "humidity": d["humidity"], "precip": d["precip"], "windScaleDay": d["wind_scale"]}]
    labels[engine.assess_all(now, daily)["overall_level"]] += 1
print(f"  low={labels['low']}  medium={labels['medium']}  high={labels['high']}  (共 {len(hist)} 天)")

print("\n=== 4. ML 预测表现（演示天气）===")
client = WeatherClient(demo=True)
data = {"now": client.get_now("x"), "daily": client.get_forecast("x")}
now = data["now"]["now"]; daily = data["daily"]["daily"]
ml = ml_risk.classifier.predict_over_daily(daily, g)
print(f"  未来7天逐日: {[(d['fxDate'][5:], d['level']) for d in ml['per_day']]}")
print(f"  整体: {ml['overall_level']}  proba { {k: round(v, 2) for k, v in ml['proba'].items()} }")

print("\n=== 5. Bandit（多臂老虎机）学习状态 ===")
bandit.bandit.load()
print(f"  累计反馈更新: {bandit.bandit.n_updates}")
print(f"  各处置动作被选/更新次数: {bandit.bandit._counts}")

print("\n=== 6. 风险反馈样本（risk_feedback）===")
for gg in gardens:
    try:
        print(f"  {gg['name']}: {db.risk_feedback_stats(gg['id'])}")
    except Exception as e:  # noqa: BLE001
        print(f"  {gg['name']}: 读取异常 {e}")

print("\n=== 7. 时序引擎 ===")
w = ts.historical_window(g["key"])
print(f"  近7天窗口: 均温{w['temp_max_mean']}°C 高温{w['hot_days']}天 降水{w['precip_sum']}mm 趋势{w['temp_trend']}")
f = ts.forecast(g["key"])
print(f"  未来预测: temp_max={f['temp_max'] if f else 'None'} precip={f['precip'] if f else 'None'}")

print("\n=== DONE ===")
