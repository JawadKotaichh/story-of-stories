from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def money(value: float | str | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def discounted_price(price: float, discount: float = 0.15) -> Decimal:
    return money(Decimal(str(price)) * (1 - Decimal(str(discount))))


def add_on_economics(price: float, cost: float, discount: float = 0.15) -> dict[str, Decimal]:
    sale = discounted_price(price, discount)
    return {
        "price": money(price), "discounted_price": sale, "cost": money(cost),
        "discount_concession": money(Decimal(str(price)) - sale),
        "discounted_gross_profit": money(sale - Decimal(str(cost))),
    }


def scenario_per_offer(
    price: float, cost: float, new_add_on_rate: float,
    baseline_buyers_discounted_rate: float, substitution_revenue: float = 0,
    substitution_gross_profit: float = 0, variable_operating_cost: float = 0,
) -> dict[str, float]:
    """All rates/costs are explicit assumptions, never inferred treatment effects."""
    if not 0 <= new_add_on_rate <= 1 or not 0 <= baseline_buyers_discounted_rate <= 1:
        raise ValueError("Scenario rates must be within [0, 1]")
    econ = add_on_economics(price, cost)
    revenue = (new_add_on_rate * float(econ["discounted_price"])
               - baseline_buyers_discounted_rate * float(econ["discount_concession"])
               - substitution_revenue)
    gp = (new_add_on_rate * float(econ["discounted_gross_profit"])
          - baseline_buyers_discounted_rate * float(econ["discount_concession"])
          - substitution_gross_profit - variable_operating_cost)
    return {"incremental_revenue": revenue, "incremental_gross_profit": gp}


def break_even_new_rate(price: float, cost: float, baseline_buyers_discounted_rate: float,
                        substitution_gross_profit: float = 0,
                        variable_operating_cost: float = 0) -> float | None:
    e = add_on_economics(price, cost)
    margin = float(e["discounted_gross_profit"])
    if margin <= 0:
        return None
    return (baseline_buyers_discounted_rate * float(e["discount_concession"])
            + substitution_gross_profit + variable_operating_cost) / margin
