"""A small product-only neural recommender with deterministic online SGD updates.

Input: one selected product (one-hot, represented by its vocabulary index).
Output: a softmax ranking over other products; the top two are displayed.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .data import Basket


@dataclass(frozen=True)
class NeuralSuggestion:
    product: str
    score: float


def basket_examples(baskets: list[Basket], product_to_index: dict[str, int]):
    """One weighted orientation per seed; each transaction has total weight one."""
    seeds, targets, weights = [], [], []
    n_products = len(product_to_index)
    used_transactions = 0
    for basket in baskets:
        items = [p for p in basket.products if p in product_to_index]
        if len(items) < 2:
            continue
        used_transactions += 1
        for seed in items:
            target = np.zeros(n_products, dtype=np.float64)
            for other in items:
                if other != seed:
                    target[product_to_index[other]] = 1 / (len(items) - 1)
            seeds.append(product_to_index[seed])
            targets.append(target)
            weights.append(1 / len(items))
    if not seeds:
        return (np.empty(0, dtype=np.int64), np.empty((0, n_products), dtype=np.float64),
                np.empty(0, dtype=np.float64), 0)
    return np.asarray(seeds, dtype=np.int64), np.asarray(targets), np.asarray(weights), used_transactions


class OnlineNeuralRecommender:
    def __init__(self, products: list[str], hidden: int = 32, seed: int = 490,
                 online_learning_rate: float = .025):
        self.products = sorted(set(products))
        self.index = {product: i for i, product in enumerate(self.products)}
        self.hidden = hidden
        self.online_learning_rate = online_learning_rate
        self.seen: set[str] = set()
        self.online_updates = 0
        rng = np.random.default_rng(seed)
        n = len(self.products)
        self.w1 = rng.normal(0, .12, (n, hidden))
        self.b1 = np.zeros(hidden)
        self.w2 = rng.normal(0, .12, (hidden, n))
        self.b2 = np.zeros(n)

    def _forward(self, seed_indices: np.ndarray):
        hidden = np.tanh(self.w1[seed_indices] + self.b1)
        logits = hidden @ self.w2 + self.b2
        logits[np.arange(len(seed_indices)), seed_indices] = -1e9
        logits -= logits.max(axis=1, keepdims=True)
        exp = np.exp(logits)
        probs = exp / exp.sum(axis=1, keepdims=True)
        return hidden, probs

    def loss(self, examples) -> float:
        seeds, targets, weights, _ = examples
        if not len(seeds):
            return float("nan")
        _, probs = self._forward(seeds)
        return float(-np.sum(weights[:, None] * targets * np.log(np.maximum(probs, 1e-12))) / weights.sum())

    def _gradients(self, seeds, targets, weights, weight_decay: float):
        hidden, probs = self._forward(seeds)
        delta = (probs - targets) * (weights[:, None] / weights.sum())
        gw2 = hidden.T @ delta + weight_decay * self.w2
        gb2 = delta.sum(axis=0)
        dh = (delta @ self.w2.T) * (1 - hidden * hidden)
        gw1 = np.zeros_like(self.w1)
        np.add.at(gw1, seeds, dh)
        gw1 += weight_decay * self.w1
        gb1 = dh.sum(axis=0)
        return (gw1, gb1, gw2, gb2)

    def _parameters(self):
        return (self.w1, self.b1, self.w2, self.b2)

    def fit(self, train_baskets: list[Basket], validation_baskets: list[Basket] | None,
            epochs: int = 40, learning_rate: float = .01, batch_size: int = 512,
            weight_decay: float = .0001, patience: int = 6, seed: int = 490) -> list[dict]:
        train = basket_examples(train_baskets, self.index)
        validation = basket_examples(validation_baskets, self.index) if validation_baskets is not None else None
        if not len(train[0]) or (validation is not None and not len(validation[0])):
            raise ValueError("Training and validation require multi-product baskets")
        rng = np.random.default_rng(seed)
        params = self._parameters()
        first_moments = [np.zeros_like(p) for p in params]
        second_moments = [np.zeros_like(p) for p in params]
        step = 0
        best_loss = float("inf")
        best_params = None
        best_epoch = 0
        history = []
        for epoch in range(1, epochs + 1):
            indices = rng.permutation(len(train[0]))
            for start in range(0, len(indices), batch_size):
                batch = indices[start:start+batch_size]
                gradients = self._gradients(train[0][batch], train[1][batch],
                                            train[2][batch], weight_decay)
                step += 1
                for j, (parameter, gradient) in enumerate(zip(params, gradients)):
                    first_moments[j] = .9 * first_moments[j] + .1 * gradient
                    second_moments[j] = .999 * second_moments[j] + .001 * gradient * gradient
                    mhat = first_moments[j] / (1 - .9**step)
                    vhat = second_moments[j] / (1 - .999**step)
                    parameter -= learning_rate * mhat / (np.sqrt(vhat) + 1e-8)
            train_loss = self.loss(train)
            validation_loss = self.loss(validation) if validation is not None else train_loss
            history.append({"epoch": epoch, "train_loss": train_loss,
                            "validation_loss": validation_loss if validation is not None else None})
            if validation is None:
                best_epoch = epoch
                best_params = [p.copy() for p in params]
                continue
            if validation_loss < best_loss - 1e-5:
                best_loss = validation_loss
                best_epoch = epoch
                best_params = [p.copy() for p in params]
            elif epoch - best_epoch >= patience:
                break
        for parameter, saved in zip(params, best_params):
            parameter[:] = saved
        self.best_epoch = best_epoch
        return history

    def recommend(self, seed: str, branch: str | None = None, hour: int | None = None,
                  n: int = 2, available: set[str] | None = None) -> list[NeuralSuggestion]:
        if seed not in self.index:
            raise ValueError(f"Product {seed!r} is not in the trained vocabulary")
        if n < 1:
            raise ValueError("n must be positive")
        _, probs = self._forward(np.asarray([self.index[seed]]))
        choices = [p for p in self.products if p != seed and (available is None or p in available)]
        if len(choices) < n:
            raise ValueError(f"Only {len(choices)} eligible products")
        return [NeuralSuggestion(p, float(probs[0, self.index[p]])) for p in
                sorted(choices, key=lambda p: (-probs[0, self.index[p]], p))[:n]]

    def update(self, basket: Basket) -> bool:
        if basket.transaction_id in self.seen:
            return False
        self.seen.add(basket.transaction_id)
        examples = basket_examples([basket], self.index)
        if len(examples[0]):
            gradients = self._gradients(examples[0], examples[1], examples[2], 0.0)
            for parameter, gradient in zip(self._parameters(), gradients):
                parameter -= self.online_learning_rate * gradient
            self.online_updates += 1
        return True

    def save(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, products=np.asarray(self.products), hidden=self.hidden,
                            online_learning_rate=self.online_learning_rate,
                            w1=self.w1, b1=self.b1, w2=self.w2, b2=self.b2)

    @classmethod
    def load(cls, path: str | Path) -> "OnlineNeuralRecommender":
        with np.load(path, allow_pickle=False) as data:
            model = cls(data["products"].tolist(), int(data["hidden"]),
                        online_learning_rate=float(data["online_learning_rate"]))
            for name in ["w1", "b1", "w2", "b2"]:
                getattr(model, name)[:] = data[name]
        return model
