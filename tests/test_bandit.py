"""Contextual Bandit (LinUCB) 单元测试。纯算法层，不依赖数据库。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.bandit import LinUCB, build_context  # noqa: E402


def test_recommends_some_arm():
    b = LinUCB(arms=["a", "b", "c"], alpha=1.0, lamb=1.0)
    ctx = [1.0, 2.0, 3.0, 4.0, 5.0, 1.0, 9.0, 0.2, 0.3, 0.5]
    arm = b.recommend(ctx)
    assert arm in {"a", "b", "c"}


def test_cold_start_explores_all_arms():
    b = LinUCB(arms=["a", "b", "c"])
    ctx = [1.0, 2.0, 3.0, 4.0, 5.0, 1.0, 9.0, 0.2, 0.3, 0.5]
    seen = set()
    for _ in range(12):
        a = b.recommend(ctx)
        seen.add(a)
        b.update(a, ctx, 0.5)
    # 未试过的 arm 会给极大探索分，冷启动阶段应覆盖传入的全部 3 个 arm
    assert len(seen) == 3


def test_prefers_rewarded_arm():
    b = LinUCB(arms=["good", "bad"])
    ctx = [26.0, 72.0, 0.0, 2.0, 200.0, 0.0, 9.0, 0.1, 0.2, 0.7]
    # 两臂各试一次以解除"未试优先"
    for a in ("good", "bad"):
        b.update(a, ctx, 0.0)
    # 反复给 good 高分、bad 低分
    for _ in range(20):
        b.update("good", ctx, 0.9)
        b.update("bad", ctx, 0.1)
    picks = [b.recommend(ctx) for _ in range(20)]
    assert picks.count("good") > picks.count("bad")


def test_context_dimension_stable():
    now = {"temp": "26", "humidity": "72", "precip": "0.0", "windScale": "2", "obsTime": "2026-09-24T10:00"}
    garden = {"altitude_m": 200, "variety": "龙井43"}
    ctx = build_context(now, garden, {"low": 0.2, "medium": 0.3, "high": 0.5})
    assert len(ctx) == 10  # 与持久化维度绑定
