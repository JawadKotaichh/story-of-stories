from datetime import datetime

import pytest

from src.data import Basket, audit, build_baskets, load_lines
from src.economics import add_on_economics, break_even_new_rate, scenario_per_offer
from src.recommender import IncrementalRecommender


def basket(txid, products, hour=9, branch="Harbour"):
    return Basket(txid, datetime(2026, 1, 1, hour), branch, "Takeaway",
                  tuple(products), {p: 1 for p in products}, 10, 5)


def test_incremental_update_is_exactly_once_and_excludes_seed():
    m = IncrementalRecommender(["Coffee", "Cookie", "Tea"], mode="pair", alpha=1)
    assert m.update(basket("a", ["Coffee", "Cookie"]))
    assert not m.update(basket("a", ["Coffee", "Cookie"]))
    assert m.orders == 1
    assert m.pair_counts[("Coffee", "Cookie")] == 1
    result = m.recommend("Coffee", "Harbour", 9)
    assert len(result) == 2
    assert {s.product for s in result} == {"Cookie", "Tea"}
    assert result[0].product == "Cookie"


def test_discount_applies_to_add_on_only_and_break_even():
    e = add_on_economics(3.62, 1.18)
    assert str(e["discounted_price"]) == "3.08"
    assert str(e["discounted_gross_profit"]) == "1.90"
    assert str(e["discount_concession"]) == "0.54"
    assert break_even_new_rate(3.62, 1.18, .05) == pytest.approx(.05*.54/1.90)
    scenario = scenario_per_offer(3.62, 1.18, .05, .10)
    assert scenario["incremental_gross_profit"] == pytest.approx(.05*1.90-.10*.54)


def test_source_reconciliation():
    df = load_lines("stories_transactions.csv")
    summary = audit(df)
    baskets = build_baskets(df)
    assert summary["lines"] == 51177
    assert summary["transactions"] == 33887 == len(baskets)
    assert summary["revenue"] == 305925.14
    assert summary["gross_profit"] == 179430.49
    assert sum(b.revenue for b in baskets) == pytest.approx(305925.14)
