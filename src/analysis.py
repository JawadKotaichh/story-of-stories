from __future__ import annotations

from collections import Counter
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .data import Basket, audit, daypart, price_book
from .economics import add_on_economics, break_even_new_rate, scenario_per_offer
from .evaluate import benchmark, rolling_benchmark
from .recommender import IncrementalRecommender

COLORS = ["#2B4C3F", "#BA693B", "#D8AE55", "#718E88", "#8A6B77", "#B3C9B7",
          "#536B91", "#AFC2D5", "#D49592"]


def _save(fig, path: Path):
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _wilson(success: int, total: int) -> tuple[float, float]:
    if total == 0:
        return (0.0, 0.0)
    p = success / total
    z = 1.96
    den = 1 + z*z/total
    mid = (p + z*z/(2*total))/den
    half = z * ((p*(1-p)/total + z*z/(4*total*total)) ** 0.5)/den
    return mid-half, mid+half


def analyze(df: pd.DataFrame, baskets: list[Basket], figures: Path) -> dict:
    figures.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False,
                         "axes.spines.right": False, "figure.facecolor": "white"})
    base = audit(df)
    products = sorted(df["Product"].unique().tolist())
    categories = df.drop_duplicates("Product").set_index("Product")["Category"].astype(str).to_dict()
    bench = benchmark(baskets, products, categories)
    best = max(bench["models"], key=lambda m: bench["models"][m]["hit_at_2"])
    rolling = rolling_benchmark(baskets, products, best, categories)

    tx = pd.DataFrame([{
        "id": b.transaction_id, "branch": b.branch, "hour": b.timestamp.hour,
        "period": b.period, "weekday": b.timestamp.day_name(), "month": b.timestamp.month,
        "order_type": b.order_type, "multi": len(b.products) > 1,
        "products": b.products, "revenue": b.revenue, "gross_profit": b.gross_profit,
    } for b in baskets])
    disc_ids = set(df.loc[df["Discount Rate"] > 0, "Transaction ID"].astype(str))
    tx["discounted"] = tx["id"].isin(disc_ids)

    # 1. Order arrivals and multi-product share.
    counts = tx.groupby(["hour", "branch"]).size().unstack(fill_value=0)
    rates = tx.groupby(["hour", "branch"])["multi"].mean().unstack()
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.5))
    for i, branch in enumerate(sorted(tx.branch.unique())):
        axes[0].plot(counts.index, counts[branch], marker="o", markersize=2, color=COLORS[i], label=branch)
        axes[1].plot(rates.index, rates[branch]*100, marker="o", markersize=2, color=COLORS[i], label=branch)
    axes[0].set(title="Transactions by hour and branch", xlabel="Hour", ylabel="Transactions")
    axes[1].set(title="Multi-product share by hour", xlabel="Hour", ylabel="Percent of transactions")
    axes[0].legend(frameon=False)
    _save(fig, figures / "01_hour_branch.png")

    # 2. Category distribution, normalized within each daypart.
    category_by_tx = df[["Transaction ID", "Category", "timestamp"]].drop_duplicates(["Transaction ID", "Category"])
    category_by_tx = category_by_tx.copy()
    category_by_tx["period"] = category_by_tx["timestamp"].dt.hour.map(daypart)
    tab = pd.crosstab(category_by_tx["period"], category_by_tx["Category"])
    tab = tab.reindex(["morning", "midday", "evening"])
    shares = tab.div(tab.sum(axis=1), axis=0)*100
    fig, ax = plt.subplots(figsize=(10, 3.6))
    shares.plot(kind="bar", stacked=True, ax=ax, color=COLORS[:len(shares.columns)], width=.62)
    ax.set(title="Product-category presence by daypart", xlabel="Daypart", ylabel="Percent of category presences")
    ax.legend(loc="upper center", bbox_to_anchor=(.5, -.24), ncol=5, frameon=False, fontsize=8)
    _save(fig, figures / "02_category_daypart.png")

    # 3. Pair counts and lift for the 12 most common products.
    p_count = Counter(p for b in baskets for p in b.products)
    pair_count = Counter(pair for b in baskets for pair in combinations(b.products, 2))
    top = [p for p, _ in p_count.most_common(12)]
    n = len(baskets)
    matrix = np.full((len(top), len(top)), np.nan)
    for i, a in enumerate(top):
        for j, b in enumerate(top):
            if i == j:
                continue
            c = pair_count[tuple(sorted((a, b)))]
            matrix[i, j] = c*n/(p_count[a]*p_count[b]) if c >= 20 else np.nan
    fig, ax = plt.subplots(figsize=(9.5, 7))
    im = ax.imshow(matrix, cmap="YlGn", vmin=0, vmax=min(2.5, float(np.nanmax(matrix))))
    ax.set_xticks(range(len(top)), top, rotation=55, ha="right", fontsize=8)
    ax.set_yticks(range(len(top)), top, fontsize=8)
    ax.set_title("Pair lift (only pairs in 20+ transactions)")
    fig.colorbar(im, ax=ax, label="Observed / independence expectation", shrink=.75)
    _save(fig, figures / "03_pair_lift.png")

    # 4. Illustrative supported pair. Denominator is baskets containing seed.
    seed, addon = "Iced Matcha", "Pistachio Cookie"
    pair_rows = []
    for branch in sorted(tx.branch.unique()):
        for period in ["morning", "midday", "evening"]:
            relevant = [b for b in baskets if b.branch == branch and b.period == period and seed in b.products]
            numerator = sum(addon in b.products for b in relevant)
            lo, hi = _wilson(numerator, len(relevant))
            pair_rows.append({"branch": branch, "period": period, "seed_n": len(relevant),
                              "pair_n": numerator, "rate": numerator/len(relevant) if relevant else 0,
                              "ci_low": lo, "ci_high": hi})
    fig, ax = plt.subplots(figsize=(9, 3.5))
    x = np.arange(3)
    for i, branch in enumerate(sorted(tx.branch.unique())):
        rows = [r for r in pair_rows if r["branch"] == branch]
        y = [r["rate"]*100 for r in rows]
        lo = [(r["rate"]-r["ci_low"])*100 for r in rows]
        hi = [(r["ci_high"]-r["rate"])*100 for r in rows]
        ax.bar(x+(i-1)*.25, y, width=.24, yerr=[lo, hi], capsize=2,
               label=branch, color=COLORS[i], error_kw={"elinewidth": .7})
    ax.set(xticks=x, xticklabels=["Morning", "Midday", "Evening"],
           ylabel="Percent of Iced Matcha baskets", title="Pistachio Cookie with Iced Matcha")
    ax.legend(frameon=False)
    _save(fig, figures / "04_example_pair.png")

    # 5. Weak/unrelated factors still visible.
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4))
    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    factor_tables = {}
    for ax, (col, order) in zip(axes, [
        ("weekday", weekday_order), ("month", sorted(tx.month.unique())),
        ("order_type", sorted(tx.order_type.unique()))
    ]):
        g = tx.groupby(col)["multi"].agg(["mean", "size"]).reindex(order)
        factor_tables[col] = {str(k): {"multi_rate": float(v["mean"]), "n": int(v["size"])}
                              for k, v in g.iterrows()}
        ax.bar(range(len(g)), g["mean"]*100, color=COLORS[3])
        ax.set_xticks(range(len(g)), [str(s)[:3] if col == "weekday" else str(s) for s in g.index], rotation=30)
        ax.set(title=col.replace("_", " ").title(), ylabel="Multi-product transactions (%)", ylim=(0, 65))
    fig.suptitle("Descriptive multi-product rates; not causal effects", y=1.02)
    _save(fig, figures / "05_other_factors.png")

    # 6. Discount association and item margins (the latter uses branch/SKU medians).
    book = price_book(df)
    margins = pd.DataFrame([{"branch": b, "margin": float(add_on_economics(v["price"], v["cost"])["discounted_gross_profit"])}
                            for (b, _), v in book.items()])
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.5))
    disc = tx.groupby("discounted")["multi"].agg(["mean", "size"])
    axes[0].bar(["No discounted line", "Discounted line"], disc["mean"]*100, color=COLORS[:2])
    axes[0].set(title="Multi-product rate by recorded discount", ylabel="Percent of transactions")
    axes[0].tick_params(axis="x", rotation=15)
    branches = sorted(margins.branch.unique())
    axes[1].boxplot([margins.loc[margins.branch == b, "margin"] for b in branches], tick_labels=branches)
    axes[1].set(title="Hypothetical 15%-off add-on margin", ylabel="USD per unit")
    _save(fig, figures / "06_discount_margin.png")

    # 7. Model ablation.
    fig, ax = plt.subplots(figsize=(9, 3.7))
    names = list(bench["models"])
    vals = [bench["models"][m]["hit_at_2"]*100 for m in names]
    ax.bar([m.replace("_", "\n") for m in names], vals, color=COLORS[:len(names)])
    ax.set(title="Retrospective held-period Hit@2", ylabel="Percent of multi-product baskets")
    for i, value in enumerate(vals):
        ax.text(i, value+.1, f"{value:.1f}%", ha="center", fontsize=8)
    ax.set_ylim(0, max(vals)*1.2)
    _save(fig, figures / "07_model_ablation.png")

    example = book[("Harbour", addon)]
    scenarios = []
    for new_rate in [.01, .03, .05, .10]:
        for existing in [0, .05, .10]:
            value = scenario_per_offer(example["price"], example["cost"], new_rate, existing)
            scenarios.append({"new_add_on_rate": new_rate, "baseline_buyers_discounted_rate": existing,
                              **{k: round(v, 4) for k, v in value.items()}})
    seed_baskets = [b for b in baskets if b.branch == "Harbour" and seed in b.products]
    seed_only = [b for b in seed_baskets if len(b.products) == 1]
    # Descriptive policy mix over completed one-product baskets. This is not
    # historical offer eligibility or a response estimate.
    final_model = IncrementalRecommender(products, "pair").fit(baskets)
    discounted_prices, margins, concessions = [], [], []
    single_baskets = [b for b in baskets if len(b.products) == 1]
    for b in single_baskets:
        candidates = final_model.recommend(b.products[0], b.branch, b.timestamp.hour)
        for suggestion in candidates:
            item = suggestion.product
            unit = add_on_economics(book[(b.branch, item)]["price"], book[(b.branch, item)]["cost"])
            discounted_prices.append(float(unit["discounted_price"]))
            margins.append(float(unit["discounted_gross_profit"]))
            concessions.append(float(unit["discount_concession"]))
    mean_price = float(np.mean(discounted_prices))
    mean_margin = float(np.mean(margins))
    mean_concession = float(np.mean(concessions))
    portfolio_scenarios = []
    for new_rate in [.01, .03, .05, .10]:
        for existing_rate in [0, .05, .10]:
            # All rates and operating costs are assumed, not learned from CSV.
            revenue_per_offer = new_rate * mean_price - existing_rate * mean_concession
            gp_per_offer = new_rate * mean_margin - existing_rate * mean_concession
            net_per_offer = gp_per_offer - new_rate*.25 - .02
            portfolio_scenarios.append({
                "new_add_on_rate_assumed": new_rate,
                "existing_buyers_discounted_rate_assumed": existing_rate,
                "revenue_per_offer": round(revenue_per_offer, 4),
                "gross_profit_per_offer": round(gp_per_offer, 4),
                "six_month_revenue_proxy": round(revenue_per_offer*len(single_baskets), 2),
                "six_month_gross_profit_proxy": round(gp_per_offer*len(single_baskets), 2),
                "six_month_net_proxy_after_assumed_costs": round(net_per_offer*len(single_baskets)-6*25-500, 2),
            })
    return {
        "audit": base, "benchmarks": bench, "best_hit2_mode": best, "rolling_best": rolling,
        "pair_example": {"seed": seed, "addon": addon,
                         "total_pair_transactions": pair_count[tuple(sorted((seed, addon)))],
                         "by_branch_period": pair_rows},
        "factors": factor_tables,
        "discount_multi_rate": {str(k): {"rate": float(v["mean"]), "n": int(v["size"])}
                                for k, v in disc.iterrows()},
        "example_economics": {"branch": "Harbour", "product": addon, **example,
                              "discounted_margin": float(add_on_economics(example["price"], example["cost"])["discounted_gross_profit"]),
                              "break_even_new_rate_at_5pct_existing": break_even_new_rate(example["price"], example["cost"], .05),
                              "seed_baskets_proxy": len(seed_baskets), "seed_only_baskets_proxy": len(seed_only),
                              "scenarios_per_offer": scenarios},
        "portfolio_scenarios": {
            "completed_one_product_baskets_proxy": len(single_baskets),
            "average_of_two_offered_discounted_prices": round(mean_price, 4),
            "average_of_two_offered_discounted_gross_profits": round(mean_margin, 4),
            "average_of_two_offered_discount_concessions": round(mean_concession, 4),
            "choice_mix_assumption": "50/50 among the two shown products, conditional on purchase",
            "operating_cost_assumptions": {"per_new_add_on": .25, "per_offer": .02,
                                           "monthly_fixed": 25, "one_time": 500},
            "scenarios": portfolio_scenarios,
        },
        "figure_names": [f"{i:02d}_{name}.png" for i, name in enumerate(
            ["hour_branch", "category_daypart", "pair_lift", "example_pair",
             "other_factors", "discount_margin", "model_ablation"], 1)],
    }
