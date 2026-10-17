from __future__ import annotations

import json
from pathlib import Path

from .analysis import analyze
from .data import build_baskets, load_lines
from .report import build_report


def main():
    root = Path(__file__).resolve().parents[1]
    df = load_lines(root / "stories_transactions.csv")
    baskets = build_baskets(df)
    figures = root / "figures"
    results = analyze(df, baskets, figures)
    outputs = root / "outputs"
    outputs.mkdir(exist_ok=True)
    (outputs / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    build_report(results, figures, root / "Analysis.pdf")
    print(json.dumps({
        "audit": results["audit"],
        "models_hit_at_2": {k: round(v["hit_at_2"], 4) for k, v in results["benchmarks"]["models"].items()},
        "best_hit2_mode": results["best_hit2_mode"],
        "pair_example": results["pair_example"]["total_pair_transactions"],
        "pdf": str(root / "Analysis.pdf"),
    }, indent=2))


if __name__ == "__main__":
    main()
