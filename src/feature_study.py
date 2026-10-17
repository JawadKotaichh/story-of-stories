"""Reproducible checks of candidate checkout inputs using only the supplied CSV."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from math import sqrt
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .data import Basket


def _cramers_v_binary(frame: pd.DataFrame, feature: str) -> float:
    tab = pd.crosstab(frame[feature], frame["multi"]).to_numpy(dtype=float)
    expected = tab.sum(axis=1, keepdims=True) @ tab.sum(axis=0, keepdims=True) / tab.sum()
    chi2 = np.divide((tab - expected) ** 2, expected,
                     out=np.zeros_like(tab), where=expected > 0).sum()
    return float(sqrt(chi2 / tab.sum()))  # min(r-1, c-1) = 1 for a binary outcome


def _context(b: Basket, feature: str) -> str:
    if feature == "branch":
        return b.branch
    if feature == "daypart":
        return b.period
    if feature == "weekday":
        return str(b.timestamp.weekday())
    if feature == "order_type":
        return b.order_type
    if feature == "branch_daypart":
        return b.branch + "|" + b.period
    raise ValueError(feature)


class SmoothedPairStudy:
    """A fixed count-rule ablation, separate from the deployed neural model."""

    def __init__(self, baskets: list[Basket], products: list[str], feature: str | None,
                 alpha: float = 50.0):
        self.products, self.feature, self.alpha = products, feature, alpha
        self.base = defaultdict(Counter)
        self.base_n = Counter()
        self.local = defaultdict(Counter)
        self.local_n = Counter()
        self.global_pop = Counter()
        for b in baskets:
            for product in b.products:
                self.global_pop[product] += 1
            if len(b.products) < 2:
                continue
            weight = 1 / len(b.products)
            for seed in b.products:
                context_key = (seed, _context(b, feature)) if feature else None
                self.base_n[seed] += weight
                if context_key:
                    self.local_n[context_key] += weight
                for target in b.products:
                    if target == seed:
                        continue
                    self.base[seed][target] += weight / (len(b.products) - 1)
                    if context_key:
                        self.local[context_key][target] += weight / (len(b.products) - 1)

    def recommend(self, seed: str, basket: Basket) -> list[str]:
        key = (seed, _context(basket, self.feature)) if self.feature else None
        base_den = self.base_n[seed]
        global_den = sum(v for p, v in self.global_pop.items() if p != seed)
        scores = {}
        for target in self.products:
            if target == seed:
                continue
            prior = (self.base[seed][target] / base_den if base_den else
                     self.global_pop[target] / global_den)
            scores[target] = ((self.local[key][target] + self.alpha * prior) /
                              (self.local_n[key] + self.alpha)) if key else prior
        return sorted(scores, key=lambda p: (-scores[p], p))[:2]


def _hit2(model: SmoothedPairStudy, baskets: list[Basket]) -> float:
    hit, total = 0.0, 0
    for b in baskets:
        if len(b.products) < 2:
            continue
        total += 1
        for seed in b.products:
            hit += bool((set(b.products) - {seed}) & set(model.recommend(seed, b))) / len(b.products)
    return hit / total


def _basket_hits(model: SmoothedPairStudy, baskets: list[Basket]) -> np.ndarray:
    values = []
    for b in baskets:
        if len(b.products) < 2:
            continue
        values.append(sum(bool((set(b.products) - {seed}) & set(model.recommend(seed, b)))
                          for seed in b.products) / len(b.products))
    return np.asarray(values, dtype=float)


def study_inputs(df: pd.DataFrame, baskets: list[Basket], figures: Path) -> dict:
    tx = pd.DataFrame({
        "id": [b.transaction_id for b in baskets],
        "multi": [len(b.products) > 1 for b in baskets],
        "branch": [b.branch for b in baskets],
        "daypart": [b.period for b in baskets],
        "weekday": [b.timestamp.day_name() for b in baskets],
        "month": [str(b.timestamp.month) for b in baskets],
        "order_type": [b.order_type for b in baskets],
    })
    customer = df.groupby("Transaction ID")["Customer ID"].first()
    discount = df.groupby("Transaction ID")["Discount Rate"].max()
    tx["customer_id_recorded"] = tx.id.map(customer).notna().map({True: "yes", False: "no"})
    tx["discounted_line"] = tx.id.map(discount).gt(0).map({True: "yes", False: "no"})
    factors = {}
    for feature in ["branch", "daypart", "weekday", "month", "order_type",
                    "customer_id_recorded", "discounted_line"]:
        grouped = tx.groupby(feature).multi.agg(["mean", "size"])
        factors[feature] = {
            "cramers_v": _cramers_v_binary(tx, feature),
            "min_rate": float(grouped["mean"].min()),
            "max_rate": float(grouped["mean"].max()),
            "levels": {str(k): {"n": int(v["size"]), "multi_rate": float(v["mean"])}
                       for k, v in grouped.iterrows()},
        }

    fig, axes = plt.subplots(2, 3, figsize=(11, 6.7))
    for ax, feature in zip(axes.flat, ["branch", "daypart", "weekday", "month",
                                        "order_type", "customer_id_recorded"]):
        levels = factors[feature]["levels"]
        labels = list(levels)
        rates = [levels[k]["multi_rate"] * 100 for k in labels]
        ns = [levels[k]["n"] for k in labels]
        ax.bar(range(len(labels)), rates, color="#718E88")
        ax.set_xticks(range(len(labels)), [k[:3] if feature == "weekday" else k for k in labels],
                      rotation=35 if len(labels) > 4 else 0, ha="right" if len(labels) > 4 else "center")
        ax.set_ylim(0, 70)
        ax.set_title(f"{feature.replace('_', ' ').title()}  |  V={factors[feature]['cramers_v']:.3f}")
        ax.set_ylabel("Multi-product baskets (%)")
        for i, (rate, n) in enumerate(zip(rates, ns)):
            ax.text(i, rate + 1, f"n={n:,}", ha="center", fontsize=7)
    fig.suptitle("Basket-size association by recorded factor (descriptive; no causal claim)")
    fig.tight_layout()
    fig.savefig(figures / "09_input_associations.png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    train = [b for b in baskets if b.timestamp.date() < date(2026, 4, 1)]
    validation = [b for b in baskets if date(2026, 4, 1) <= b.timestamp.date() < date(2026, 5, 1)]
    test = [b for b in baskets if b.timestamp.date() >= date(2026, 5, 1)]
    products = sorted(df.Product.unique())
    candidates = ["product_only", "branch", "daypart", "weekday", "order_type", "branch_daypart"]
    ablations = {}
    reference_hits = None
    for feature in candidates:
        if feature == "product_only":
            model = SmoothedPairStudy(train, products, None)
            reference_hits = _basket_hits(model, test)
            ablations[feature] = {"alpha": None, "validation_hit2": _hit2(model, validation),
                                  "test_hit2": float(reference_hits.mean())}
            continue
        tried = []
        for alpha in [10.0, 50.0, 200.0]:
            model = SmoothedPairStudy(train, products, feature, alpha)
            tried.append((alpha, _hit2(model, validation), model))
        alpha, val, model = max(tried, key=lambda row: (row[1], row[0]))
        hits = _basket_hits(model, test)
        differences = hits - reference_hits
        delta = float(differences.mean())
        se = float(differences.std(ddof=1) / sqrt(len(differences)))
        ablations[feature] = {"alpha": alpha, "validation_hit2": val,
                              "test_hit2": float(hits.mean()),
                              "test_delta_vs_product_only": delta,
                              "paired_delta_ci95": [delta - 1.96 * se, delta + 1.96 * se]}
    fig, ax = plt.subplots(figsize=(9.2, 4.2))
    names = list(ablations)
    vals = [ablations[k]["test_hit2"] * 100 for k in names]
    ax.bar(range(len(names)), vals, color=["#2B4C3F"] + ["#BA693B"] * (len(names) - 1))
    ax.set_xticks(range(len(names)), [n.replace("_", "\n") for n in names])
    ax.set_ylabel("May-June Hit@2 (%)")
    ax.set_title("Extra checkout context: same count rule, April-selected smoothing")
    ax.set_ylim(0, max(vals) * 1.2)
    for i, value in enumerate(vals):
        ax.text(i, value + .1, f"{value:.2f}%", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(figures / "10_input_ablation.png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return {"outcome": "more than one distinct product in completed transaction",
            "association_note": "Cramer's V measures association, not causal effect; discount is observed after checkout.",
            "factors": factors, "context_ablation": ablations,
            "context_ablation_note": "Count-rule diagnostic, not a neural architecture comparison; smoothing selected on April only."}
