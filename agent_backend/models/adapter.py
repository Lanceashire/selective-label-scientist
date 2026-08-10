from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression


class LogisticModelAdapter:
    """Deterministic probability model used by the generic dynamic environment."""

    def __init__(self, seed: int = 0):
        self.seed = seed
        self.model: LogisticRegression | None = None
        self.constant_probability: float | None = None

    def fit(self, x: np.ndarray, y: np.ndarray) -> "LogisticModelAdapter":
        if len(y) == 0:
            self.constant_probability = 0.5
            return self
        unique = np.unique(y)
        if len(unique) < 2:
            self.constant_probability = float(unique[0])
            return self
        self.model = LogisticRegression(max_iter=500, random_state=self.seed)
        self.model.fit(x, y)
        self.constant_probability = None
        return self

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        if self.model is not None:
            return self.model.predict_proba(x)[:, 1]
        return np.full(len(x), 0.5 if self.constant_probability is None else self.constant_probability, dtype=float)

    def clone_with_seed(self, seed: int) -> "LogisticModelAdapter":
        return LogisticModelAdapter(seed)
