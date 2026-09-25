"""模型回测评估：时间序列滚动回测 LightGBM 风险分类器。

核心思路（防泄漏）：
  - 按日期升序取历史气象，用「前 N 天」训练、「后 K 天」测试；
  - 窗口逐日前移，收集所有测试段的预测与真实标签；
  - 标签沿用训练时的规则引擎弱标注（与 ml_risk._build_samples 一致），
    因此回测衡量的是「ML 能否复现规则引擎的判断」。
  - 不污染模块级 classifier 单例，每次回测新建独立 Pipeline。
"""
from __future__ import annotations

from datetime import datetime

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    recall_score,
)

from . import db, ml_risk

LEVELS = ml_risk.LEVELS  # ["low", "medium", "high"]
_LEVEL_IDX = {lv: i for i, lv in enumerate(LEVELS)}


def _new_pipeline():
    """与 ml_risk.RiskClassifier._fit 保持一致的训练管线。"""
    from lightgbm import LGBMClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LGBMClassifier(
            n_estimators=200, learning_rate=0.05, num_leaves=15,
            objective="multiclass", num_class=3, random_state=42,
            verbose=-1, class_weight="balanced",
        )),
    ])


def rolling_backtest(
    garden_key: str,
    garden: dict,
    min_train: int = 30,
    test: int = 7,
    days: int = 365,
) -> dict:
    """对单个茶园执行时间序列滚动回测，返回指标 dict。

    返回字段：
      ok / reason / sample_count / accuracy / macro_f1 / high_recall
      confusion (3x3 list, 行=真实 列=预测) / report (dict) / levels
    """
    history = db.weather_history_series(garden_key, days=days)
    if len(history) < min_train + test:
        return {
            "ok": False,
            "reason": f"历史仅 {len(history)} 天，至少需要 {min_train + test} 天才能回测",
        }

    y_true: list[int] = []
    y_pred: list[int] = []
    n = len(history)
    for start in range(min_train, n - test + 1):
        train_hist = history[:start]
        test_hist = history[start:start + test]
        X_tr, y_tr = ml_risk.RiskClassifier._build_samples([(garden, train_hist)])
        X_te, y_te = ml_risk.RiskClassifier._build_samples([(garden, test_hist)])
        if len(set(y_tr)) < 2 or not X_te:
            continue
        pipe = _new_pipeline()
        pipe.fit(X_tr, y_tr)
        y_pred.extend(int(p) for p in pipe.predict(X_te))
        y_true.extend(int(v) for v in y_te)

    if not y_true:
        return {"ok": False, "reason": "训练段标签过于单一（缺少中/高风险样本），无法回测"}

    acc = accuracy_score(y_true, y_pred)
    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    high_idx = _LEVEL_IDX["high"]
    if high_idx in set(y_true):
        high_recall = float(recall_score(
            y_true, y_pred, labels=[high_idx], average=None, zero_division=0,
        )[0])
    else:
        high_recall = 0.0
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1, 2]).tolist()
    report = classification_report(
        y_true, y_pred, target_names=LEVELS, output_dict=True, zero_division=0,
    )

    return {
        "ok": True,
        "sample_count": len(y_true),
        "accuracy": round(float(acc), 4),
        "macro_f1": round(float(macro_f1), 4),
        "high_recall": round(high_recall, 4),
        "confusion": cm,
        "report": report,
        "levels": LEVELS,
        "min_train": min_train,
        "test_window": test,
        "eval_at": datetime.now().isoformat(timespec="seconds"),
    }


def verdict(result: dict) -> str:
    """根据回测结果给出一句开发者可读的结论。"""
    if not result.get("ok"):
        return f"回测未完成：{result.get('reason', '未知原因')}"
    parts = [
        f"样本 {result['sample_count']} 条",
        f"准确率 {result['accuracy']:.1%}",
        f"宏平均F1 {result['macro_f1']:.3f}",
        f"高风险召回 {result['high_recall']:.1%}",
    ]
    if result["high_recall"] < 0.6:
        parts.append("⚠ 高风险漏报偏高，建议继续攒数据或调特征")
    elif result["macro_f1"] >= 0.7:
        parts.append("模型表现可用")
    else:
        parts.append("模型一般，数据积累后会改善")
    return "｜".join(parts)
