from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .data import Basket, daypart


@dataclass(frozen=True)
class Suggestion:
    product: str
    score: float
    pair_count: int
    context_count: int


class IncrementalRecommender:
    """Smoothed transaction-level co-purchase estimator with exact-once updates."""

    def __init__(self, products: list[str], mode: str = "pair_daypart", alpha: float = 20.0):
        if mode not in {"global", "daypart", "pair", "pair_daypart", "pair_branch_daypart"}:
            raise ValueError(mode)
        self.products = sorted(set(products))
        self.mode = mode
        self.alpha = alpha
        self.seen: set[str] = set()
        self.seed_exposures: Counter = Counter()
        self.pair_counts: Counter = Counter()
        self.context_exposures: Counter = Counter()
        self.context_pairs: Counter = Counter()
        self.popularity: Counter = Counter()
        self.period_popularity: Counter = Counter()
        self.orders = 0
        self.branches: set[str] = set()

    def _context(self, seed: str, branch: str, period: str) -> tuple:
        if self.mode == "pair_branch_daypart":
            return (seed, branch, period)
        return (seed, period)

    def update(self, basket: Basket) -> bool:
        if basket.transaction_id in self.seen:
            return False
        self.seen.add(basket.transaction_id)
        self.orders += 1
        self.branches.add(basket.branch)
        items = tuple(sorted(set(basket.products)))
        for product in items:
            self.popularity[product] += 1
            self.period_popularity[(basket.period, product)] += 1
            self.seed_exposures[product] += 1
            context = (product, basket.branch, basket.period)
            self.context_exposures[context] += 1
            for other in items:
                if other != product:
                    self.pair_counts[(product, other)] += 1
                    self.context_pairs[(context, other)] += 1
        return True

    def fit(self, baskets: list[Basket]) -> "IncrementalRecommender":
        for basket in baskets:
            self.update(basket)
        return self

    def recommend(self, seed: str, branch: str, hour: int, n: int = 2,
                  available: set[str] | None = None) -> list[Suggestion]:
        if n < 1:
            raise ValueError("n must be positive")
        period = daypart(hour)
        candidates = (set(self.products) if available is None else set(self.products) & available) - {seed}
        if len(candidates) < n:
            raise ValueError(f"Only {len(candidates)} distinct eligible products")
        denominator = sum(self.popularity.values()) + len(self.products)
        scores = []
        for item in candidates:
            pop_prior = (self.popularity[item] + 1) / denominator
            pair_count = self.pair_counts[(seed, item)]
            pair_rate = (pair_count + self.alpha * pop_prior) / (self.seed_exposures[seed] + self.alpha)
            context = (seed, branch, period)
            context_count = self.context_pairs[(context, item)]
            context_n = self.context_exposures[context]
            daypart_count = sum(self.context_pairs[((seed, b, period), item)] for b in self.branches)
            daypart_n = sum(self.context_exposures[(seed, b, period)] for b in self.branches)
            if self.mode == "global":
                score = pop_prior
            elif self.mode == "daypart":
                period_n = sum(self.period_popularity[(period, x)] for x in self.products)
                score = (self.period_popularity[(period, item)] + self.alpha * pop_prior) / (period_n + self.alpha)
            elif self.mode == "pair":
                score = pair_rate
            elif self.mode == "pair_daypart":
                score = (daypart_count + self.alpha * pair_rate) / (daypart_n + self.alpha)
                context_count = daypart_count
            else:
                score = (context_count + self.alpha * pair_rate) / (context_n + self.alpha)
            if self.mode == "pair":
                context_count = daypart_count
            scores.append(Suggestion(item, float(score), int(pair_count), int(context_count)))
        return sorted(scores, key=lambda x: (-x.score, x.product))[:n]


def make_demo_basket(transaction_id: str, timestamp, branch: str, products: list[str],
                     revenue: float, gross_profit: float) -> Basket:
    return Basket(transaction_id, timestamp, branch, "Demo", tuple(sorted(set(products))),
                  dict(Counter(products)), revenue, gross_profit)
