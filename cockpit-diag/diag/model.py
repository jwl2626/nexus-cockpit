"""手搓一个 softmax 回归（多项式逻辑回归）。

为什么是它而不是神经网络：
  - 你的样本量大概率在几百到几千，参数量再大一定过拟合；
  - 线性模型每个权重都能反向解释成"某个检查项对某类故障的贡献"，
    产线要的就是这个可解释性；
  - 它足够训得快、改得动，能让你把"训练"这件事的每一步都看清楚。

训练目标：带 L2 正则的加权交叉熵
    loss = -Σ w_i·log p_{i,y_i} / Σ w_i  +  λ/2·||W||²
其中 w_i 是类别权重（balanced），用来对付"不良样本远少于正常样本"。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np


class SoftmaxRegression:
    def __init__(
        self,
        *,
        l2: float = 1e-3,
        lr: float = 0.08,
        epochs: int = 400,
        batch_size: int = 64,
        momentum: float = 0.9,
        seed: int = 0,
        verbose: bool = False,
        log_every: int = 40,
    ):
        self.l2 = l2
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.momentum = momentum
        self.seed = seed
        self.verbose = verbose
        self.log_every = log_every

        self.classes_: list[str] = []
        self.n_features_ = 0
        self.W_: np.ndarray | None = None
        self.b_: np.ndarray | None = None
        self.mean_: np.ndarray | None = None
        self.std_: np.ndarray | None = None
        self.history_: list[float] = []

    # ------------------------------------------------------------------
    def fit(
        self,
        X: np.ndarray,
        y: Sequence[str],
        classes: Iterable[str] | None = None,
        class_weight: str | None = "balanced",
    ) -> "SoftmaxRegression":
        X = np.asarray(X, dtype=np.float64)
        y_arr = np.asarray(list(y))
        if X.ndim != 2:
            raise ValueError("X 必须是二维矩阵")
        if X.shape[0] != y_arr.shape[0]:
            raise ValueError("X 和 y 的样本数不一致")

        self.classes_ = list(classes) if classes is not None else sorted(set(y_arr.tolist()))
        class_index = {c: i for i, c in enumerate(self.classes_)}
        y_idx = np.array([class_index[v] for v in y_arr], dtype=np.int64)

        self.n_features_ = X.shape[1]
        self.mean_ = X.mean(axis=0)
        std = X.std(axis=0)
        std = np.where(std < 1e-8, 1.0, std)
        self.std_ = std
        Xn = (X - self.mean_) / self.std_

        n_samples, n_classes = Xn.shape[0], len(self.classes_)
        Y = np.zeros((n_samples, n_classes), dtype=np.float64)
        Y[np.arange(n_samples), y_idx] = 1.0

        sample_w = np.ones(n_samples, dtype=np.float64)
        if class_weight == "balanced":
            counts = np.bincount(y_idx, minlength=n_classes).astype(np.float64)
            class_w = n_samples / (n_classes * np.maximum(counts, 1.0))
            sample_w = class_w[y_idx]
        weight_sum = float(sample_w.sum())

        rng = np.random.default_rng(self.seed)
        self.W_ = np.zeros((self.n_features_, n_classes), dtype=np.float64)
        self.b_ = np.zeros(n_classes, dtype=np.float64)
        vW = np.zeros_like(self.W_)
        vb = np.zeros_like(self.b_)

        for epoch in range(1, self.epochs + 1):
            order = rng.permutation(n_samples)
            for start in range(0, n_samples, self.batch_size):
                idx = order[start:start + self.batch_size]
                xb, yb, wb = Xn[idx], Y[idx], sample_w[idx]
                probs = _softmax(xb @ self.W_ + self.b_)
                denom = max(float(wb.sum()), 1e-12)
                grad_logits = ((probs - yb) * wb[:, None]) / denom
                grad_W = xb.T @ grad_logits + self.l2 * self.W_
                grad_b = grad_logits.sum(axis=0)
                vW = self.momentum * vW - self.lr * grad_W
                vb = self.momentum * vb - self.lr * grad_b
                self.W_ += vW
                self.b_ += vb

            loss = self._loss(Xn, Y, sample_w, weight_sum)
            self.history_.append(loss)
            if self.verbose and (epoch % self.log_every == 0 or epoch == 1):
                print(f"  epoch {epoch:4d}/{self.epochs}  loss={loss:.4f}")

        return self

    # ------------------------------------------------------------------
    def _loss(self, Xn: np.ndarray, Y: np.ndarray, w: np.ndarray, weight_sum: float) -> float:
        probs = _softmax(Xn @ self.W_ + self.b_)
        eps = 1e-12
        ce = -(Y * np.log(probs + eps)).sum(axis=1)
        return float((ce * w).sum() / weight_sum + 0.5 * self.l2 * float((self.W_ ** 2).sum()))

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        self._check_fitted()
        Xn = (np.atleast_2d(X) - self.mean_) / self.std_
        return _softmax(Xn @ self.W_ + self.b_)

    def predict(self, X: np.ndarray) -> list[str]:
        probs = self.predict_proba(X)
        return [self.classes_[i] for i in probs.argmax(axis=1)]

    def _check_fitted(self) -> None:
        if self.W_ is None:
            raise RuntimeError("模型还没训练，先调用 fit() 或 load()")

    # ------------------------------------------------------------------
    def feature_importance(self, feature_names: Sequence[str], top_k: int = 6) -> dict[str, list[tuple[str, float]]]:
        """每个类别最"支持"和"反对"的特征。线性模型的白盒优势就在这里。"""
        self._check_fitted()
        out: dict[str, list[tuple[str, float]]] = {}
        for i, name in enumerate(self.classes_):
            col = self.W_[:, i]
            order = np.argsort(col)
            picks = list(order[-top_k:][::-1]) + list(order[:top_k])
            out[name] = [(feature_names[j], float(col[j])) for j in picks]
        return out

    # ------------------------------------------------------------------
    def save(self, path: str | Path, schema: dict | None = None) -> Path:
        self._check_fitted()
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            target,
            W=self.W_,
            b=self.b_,
            mean=self.mean_,
            std=self.std_,
            classes=np.array(self.classes_, dtype="<U64"),
            schema=np.array([json.dumps(schema or {}, ensure_ascii=False)]),
        )
        return target

    @classmethod
    def load(cls, path: str | Path) -> "SoftmaxRegression":
        data = np.load(Path(path), allow_pickle=False)
        model = cls()
        model.W_ = data["W"]
        model.b_ = data["b"]
        model.mean_ = data["mean"]
        model.std_ = data["std"]
        model.classes_ = [str(x) for x in data["classes"]]
        model.n_features_ = int(model.W_.shape[0])
        return model

    @staticmethod
    def load_schema(path: str | Path) -> dict:
        data = np.load(Path(path), allow_pickle=False)
        return json.loads(str(data["schema"][0]))


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=1, keepdims=True)
