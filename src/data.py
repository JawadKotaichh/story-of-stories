from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


REQUIRED = {
    "Transaction ID", "Date", "Time", "Branch", "Customer ID", "Order Type",
    "Product", "Category", "Quantity", "Unit Price (USD)", "Discount Rate",
    "Unit Cost (USD)", "Line Revenue (USD)", "Line Gross Profit (USD)",
}


def daypart(hour: int) -> str:
    if 7 <= hour < 11:
        return "morning"
    if 11 <= hour < 19:
        return "midday"
    return "evening"


@dataclass(frozen=True)
class Basket:
    transaction_id: str
    timestamp: pd.Timestamp
    branch: str
    order_type: str
    products: tuple[str, ...]
    quantities: dict[str, int]
    revenue: float
    gross_profit: float

    @property
    def period(self) -> str:
        return daypart(self.timestamp.hour)


def load_lines(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Missing CSV at {path}. See README.md for placement.")
    df = pd.read_csv(path, dtype={"Transaction ID": "string", "Customer ID": "string"})
    missing = REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"Missing CSV columns: {sorted(missing)}")
    df["timestamp"] = pd.to_datetime(
        df["Date"].astype(str) + " " + df["Time"].astype(str), errors="raise"
    )
    numeric = ["Quantity", "Unit Price (USD)", "Discount Rate", "Unit Cost (USD)",
               "Line Revenue (USD)", "Line Gross Profit (USD)"]
    if df[numeric].isna().any().any():
        raise ValueError("Required numeric values contain nulls")
    if (df["Quantity"] <= 0).any() or (df["Unit Price (USD)"] < 0).any():
        raise ValueError("Invalid quantity or unit price")
    if ((df["Discount Rate"] < 0) | (df["Discount Rate"] >= 1)).any():
        raise ValueError("Invalid discount rate")
    return df


def audit(df: pd.DataFrame) -> dict:
    g = df.groupby("Transaction ID", sort=False)
    consistency = {
        col: int((g[col].nunique(dropna=False) > 1).sum())
        for col in ["Branch", "Date", "Time", "Order Type", "Customer ID"]
    }
    if any(consistency.values()):
        raise ValueError(f"Inconsistent transaction fields: {consistency}")
    expected_revenue = df["Quantity"] * df["Unit Price (USD)"] * (1 - df["Discount Rate"])
    expected_gp = df["Line Revenue (USD)"] - df["Quantity"] * df["Unit Cost (USD)"]
    bad_revenue = int(((expected_revenue - df["Line Revenue (USD)"]).abs() > 0.021).sum())
    bad_gp = int(((expected_gp - df["Line Gross Profit (USD)"]).abs() > 0.021).sum())
    if bad_revenue or bad_gp:
        raise ValueError(f"Accounting mismatches > 2 cents: revenue={bad_revenue}, gross_profit={bad_gp}")
    return {
        "lines": int(len(df)), "transactions": int(df["Transaction ID"].nunique()),
        "date_min": str(df["timestamp"].min().date()),
        "date_max": str(df["timestamp"].max().date()),
        "branches": int(df["Branch"].nunique()), "products": int(df["Product"].nunique()),
        "categories": int(df["Category"].nunique()),
        "missing_customer_rows": int(df["Customer ID"].isna().sum()),
        "revenue": round(float(df["Line Revenue (USD)"].sum()), 2),
        "gross_profit": round(float(df["Line Gross Profit (USD)"].sum()), 2),
        "discounted_transactions": int(df.loc[df["Discount Rate"] > 0, "Transaction ID"].nunique()),
        "basket_line_counts": {str(k): int(v) for k, v in g.size().value_counts().sort_index().items()},
        "max_revenue_rounding_difference": round(float((expected_revenue - df["Line Revenue (USD)"]).abs().max()), 4),
    }


def build_baskets(df: pd.DataFrame) -> list[Basket]:
    result = []
    for txid, part in df.groupby("Transaction ID", sort=False):
        quantities = part.groupby("Product")["Quantity"].sum().astype(int).to_dict()
        first = part.iloc[0]
        result.append(Basket(
            transaction_id=str(txid), timestamp=first["timestamp"],
            branch=str(first["Branch"]), order_type=str(first["Order Type"]),
            products=tuple(sorted(quantities)), quantities=quantities,
            revenue=float(part["Line Revenue (USD)"].sum()),
            gross_profit=float(part["Line Gross Profit (USD)"].sum()),
        ))
    return sorted(result, key=lambda b: (b.timestamp, b.transaction_id))


def price_book(df: pd.DataFrame) -> dict[tuple[str, str], dict[str, float]]:
    grouped = df.groupby(["Branch", "Product"], sort=False)
    return {
        (str(branch), str(product)): {
            "price": float(part["Unit Price (USD)"].median()),
            "cost": float(part["Unit Cost (USD)"].median()),
        }
        for (branch, product), part in grouped
    }


def numeric_audit_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """Numeric audit copy of every raw field; never passed to the product-only model.

    Encoding identifiers and future basket outcomes as model inputs would leak
    information. This copy exists only to document data types and EDA handling.
    """
    out = pd.DataFrame(index=df.index)
    methods = {}
    categorical = ["Transaction ID", "Branch", "Customer ID", "Order Type", "Product", "Category"]
    for col in categorical:
        known = sorted(df[col].dropna().astype(str).unique())
        mapping = {value: i for i, value in enumerate(known)}
        out[col] = df[col].astype("string").map(mapping).fillna(-1).astype("int32")
        methods[col] = f"sorted-category integer code; {len(known)} observed values; missing=-1"
    out["Date"] = (pd.to_datetime(df["Date"]) - pd.Timestamp("1970-01-01")).dt.days.astype("int32")
    methods["Date"] = "integer days since 1970-01-01; used only for chronological split/EDA"
    seconds = pd.to_timedelta(df["Time"]).dt.total_seconds()
    out["Time"] = seconds.astype("int32")
    methods["Time"] = "integer seconds after midnight; EDA only"
    numeric = ["Quantity", "Unit Price (USD)", "Discount Rate", "Unit Cost (USD)",
               "Line Revenue (USD)", "Line Gross Profit (USD)"]
    for col in numeric:
        out[col] = pd.to_numeric(df[col], errors="raise")
        methods[col] = "original numeric value; financial audit/scenarios only"
    if set(out.columns) != REQUIRED or not all(pd.api.types.is_numeric_dtype(t) for t in out.dtypes):
        raise AssertionError("Numeric audit encoding did not cover every CSV field")
    return out, methods
