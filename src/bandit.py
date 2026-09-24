"""Contextual Bandit（LinUCB）——三引擎联动的【决策引擎】。

以"当前环境因子 + 风险概率"为 context，在处置动作池（arm）中在线择优，
用反馈(是否采纳/风险是否成真)持续更新。相比普通 UCB，LinUCB 利用 context
的相关性：不同环境下最优处置不同，从而缓解冷门建议被饿死的问题。

持久化：A/b/counts 存到 data/models/bandit.joblib。
降级：无任何反馈时，LinUCB 的未试 arm 给最大探索分，保证每类处置都有曝光。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from . import risk

MODEL_DIR = Path(__file__).resolve().parent.parent / "data" / "models"
MODEL_PATH = MODEL_DIR / "bandit.joblib"

# 处置动作池（arm）：对应风险场景下的农事处置方向
ARMS = ["补水灌溉", "遮阳降温", "防冻保暖", "排水防渍", "喷药防治", "暂缓作业"]


class LinUCB:
    """线性上下文老虎机：每个 arm 维护岭回归参数，按 UCB 选动作。"""

    def __init__(self, arms: list[str] | None = None, alpha: float = 1.0, lamb: float = 1.0):
        self.arms = arms if arms is not None else list(ARMS)
        self.alpha = alpha
        self.lamb = lamb
        self._A: dict[str, np.ndarray] = {}
        self._b: dict[str, np.ndarray] = {}
        self._counts: dict[str, int] = {a: 0 for a in self.arms}
        self._dim = 0

    def _init_dim(self, d: int) -> None:
        if self._dim == d:
            return
        self._dim = d
        I = self.lamb * np.eye(d)
        for a in self.arms:
            self._A.setdefault(a, I.copy())
            self._b.setdefault(a, np.zeros(d))

    def recommend(self, context: list[float]) -> str:
        """按 context 返回最优处置动作。context 长度需固定（=训练时 dim）。"""
        x = np.asarray(context, dtype=float)
        self._init_dim(x.shape[0])
        scores = {}
        for a in self.arms:
            A = self._A[a]
            b = self._b[a]
            theta = np.linalg.solve(A, b)
            mean = float(theta @ x)
            # 未试过的 arm：探索项给一个大的常数，保证每臂至少曝光一次
            if self._counts[a] == 0:
                scores[a] = mean + 1e6
            else:
                conf = self.alpha * float(np.sqrt(x @ np.linalg.solve(A, x)))
                scores[a] = mean + conf
        return max(scores, key=scores.get)

    def update(self, arm: str, context: list[float], reward: float) -> None:
        """收到反馈后更新该 arm 的参数（reward ∈ [0,1]）。"""
        x = np.asarray(context, dtype=float)
        self._init_dim(x.shape[0])
        if arm not in self._A:
            return
        self._A[arm] += np.outer(x, x)
        self._b[arm] += reward * x
        self._counts[arm] += 1

    @property
    def n_updates(self) -> int:
        return sum(self._counts.values())

    # ---------- 持久化 ----------
    def save(self) -> None:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        import joblib
        joblib.dump({
            "arms": self.arms, "alpha": self.alpha, "lamb": self.lamb,
            "dim": self._dim, "A": self._A, "b": self._b, "counts": self._counts,
        }, MODEL_PATH)

    def load(self) -> bool:
        if not MODEL_PATH.exists():
            return False
        try:
            import joblib
            obj = joblib.load(MODEL_PATH)
            self.arms = obj.get("arms") or list(ARMS)
            self.alpha = obj.get("alpha", self.alpha)
            self.lamb = obj.get("lamb", self.lamb)
            self._dim = obj.get("dim", 0)
            self._A = obj.get("A", {})
            self._b = obj.get("b", {})
            self._counts = obj.get("counts", {a: 0 for a in self.arms})
            return True
        except Exception:  # noqa: BLE001
            return False


# ---------------------------------------------------------------------------
# context 构造：把环境因子 + 风险概率压成一个固定维度向量
# ---------------------------------------------------------------------------
_CONTEXT_FEATURES = [
    "temp", "humidity", "precip", "wind", "altitude", "variety", "month",
    "p_low", "p_medium", "p_high",
]


def build_context(now: dict, garden: dict, proba: dict | None = None) -> list[float]:
    """构造 bandit 的 context 向量（顺序与持久化维度绑定，请勿随意改列数）。"""
    from .ml_risk import _variety_code, _num_date
    proba = proba or {"low": 1.0, "medium": 0.0, "high": 0.0}
    ctx = [
        float(risk._num(now.get("temp"))),
        float(risk._num(now.get("humidity"))),
        float(risk._num(now.get("precip"))),
        float(risk._num(now.get("windScale"))),
        float(garden.get("altitude_m") or 0),
        _variety_code(garden.get("variety")),
        _num_date(now.get("obsTime")),
        float(proba.get("low", 0.0)),
        float(proba.get("medium", 0.0)),
        float(proba.get("high", 0.0)),
    ]
    return ctx


# 模块级单例
bandit = LinUCB()
