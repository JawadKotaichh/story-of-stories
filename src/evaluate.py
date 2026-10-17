from __future__ import annotations

from collections import defaultdict
from datetime import date

import numpy as np

from .data import Basket
from .recommender import IncrementalRecommender


MODES = ["global", "daypart", "pair", "pair_daypart", "pair_branch_daypart"]


def evaluate_model(model: IncrementalRecommender, baskets: list[Basket],
                   categories: dict[str, str] | None = None) -> dict:
    weighted = defaultdict(float)
    tx_hits = []
    by_group = defaultdict(lambda: [0.0, 0.0])
    n_transactions = 0
    for basket in baskets:
        if len(basket.products) < 2:
            continue
        n_transactions += 1
        weight = 1.0 / len(basket.products)
        basket_hit2 = 0.0
        for seed in basket.products:
            truth = set(basket.products) - {seed}
            ranked = [s.product for s in model.recommend(seed, basket.branch, basket.timestamp.hour)]
            hit1 = ranked[0] in truth
            hit2 = bool(truth.intersection(ranked))
            if categories:
                truth_categories = {categories[p] for p in truth}
                weighted["category_hit2"] += weight * any(categories[p] in truth_categories for p in ranked)
            weighted["hit1"] += weight * hit1
            weighted["hit2"] += weight * hit2
            basket_hit2 += weight * hit2
            weighted["mrr"] += weight * (1 if hit1 else (0.5 if ranked[1] in truth else 0))
            for key in [f"branch:{basket.branch}", f"daypart:{basket.period}"]:
                by_group[key][0] += weight * hit2
                by_group[key][1] += weight
        tx_hits.append(basket_hit2)
    if not n_transactions:
        raise ValueError("No multi-product baskets in evaluation period")
    hit2_mean = weighted["hit2"] / n_transactions
    se = float(np.std(tx_hits, ddof=1) / np.sqrt(n_transactions)) if n_transactions > 1 else 0.0
    return {
        "transactions": n_transactions,
        "hit_at_1": weighted["hit1"] / n_transactions,
        "hit_at_2": hit2_mean,
        "hit_at_2_ci95": [max(0.0, hit2_mean - 1.96*se), min(1.0, hit2_mean + 1.96*se)],
        "mrr_at_2": weighted["mrr"] / n_transactions,
        "category_hit_at_2": weighted["category_hit2"] / n_transactions if categories else None,
        "candidate_coverage": 1.0,
        "by_group_hit_at_2": {k: {"hit_at_2": v[0] / v[1], "weighted_n": v[1]}
                              for k, v in sorted(by_group.items())},
    }


def benchmark(baskets: list[Basket], products: list[str],
              categories: dict[str, str] | None = None) -> dict:
    train = [b for b in baskets if b.timestamp.date() < date(2026, 4, 1)]
    test = [b for b in baskets if b.timestamp.date() >= date(2026, 4, 1)]
    results = {}
    for mode in MODES:
        model = IncrementalRecommender(products, mode).fit(train)
        results[mode] = evaluate_model(model, test, categories)
    return {"train_transactions": len(train), "test_transactions": len(test), "models": results}


def rolling_benchmark(baskets: list[Basket], products: list[str], mode: str,
                      categories: dict[str, str] | None = None) -> dict:
    windows = {}
    for month in [4, 5, 6]:
        train = [b for b in baskets if b.timestamp.month < month]
        test = [b for b in baskets if b.timestamp.month == month]
        model = IncrementalRecommender(products, mode).fit(train)
        windows[f"2026-{month:02d}"] = evaluate_model(model, test, categories)
    return windows
