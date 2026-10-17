# Stories Coffee: two-product checkout add-on

This repository contains a reproducible analysis of `stories_transactions.csv`, a small incrementally updated recommender, a local Streamlit checkout demo, and [Analysis.pdf](Analysis.pdf). The demo offers two add-ons for **15 seconds** and applies **15% off only the add-on selected in time**. It does not process real payments.

## What the evidence says

- The supplied CSV contains **51,177 line records** from **33,887 transactions** across three branches, 1 January–30 June 2026. Recorded revenue is **$305,925.14** and recorded gross profit is **$179,430.49**.
- In the retrospective pseudo-checkout benchmark, the **product-pair rule reached 11.13% Hit@2**, compared with **10.31%** for two globally popular products. Adding daypart or branch reduced Hit@2 on the evaluated later months, so the live demo uses the simpler product-pair rule.
- These figures measure whether two suggested products appear in a **completed historical basket**. They do **not** measure whether a prompt increases purchase, revenue, or profit. The CSV contains no recommendation exposures, entry sequence, or treatment assignment. The report gives labelled sensitivity scenarios and a randomized pilot design.

## Repository contents

| Path | Purpose |
|---|---|
| `app.py` | Streamlit customer-facing demo with server-side 15-second expiry and one-time purchase updates |
| `src/data.py` | CSV validation, audit, and transaction-level baskets |
| `src/recommender.py` | Smoothed co-purchase model and incremental updates |
| `src/evaluate.py` | Chronological and rolling retrospective benchmarks |
| `src/analysis.py` | Factor analysis, financial scenarios, and seven reproducible plots |
| `src/economics.py` | Discount, gross profit, and break-even arithmetic |
| `src/report.py` | PDF assembly from generated results |
| `src/pipeline.py` | One-command analysis and report build |
| `figures/`, `outputs/results.json` | Generated plots and full computed tables |
| `Analysis.pdf` | Reviewed analysis and pilot proposal |
| `IMPLEMENTATION_PLAN.md` | Original detailed implementation plan |

## Local setup

Use **64-bit Python 3.12 or 3.13**. On Windows ARM, use the x64 Python runtime: the Streamlit `pyarrow` dependency may lack an ARM wheel. The app and analysis need no external service once dependencies are installed.

```powershell
git clone <your-repository-url>
cd story-of-stories
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Place the supplied CSV at `stories_transactions.csv` in the repository root. It is intentionally ignored by Git because publication rights for transaction-level data have not been confirmed. The repository code never downloads or substitutes other business data.

On macOS/Linux, activate with `source .venv/bin/activate` and use the same Python commands below.

## Run the analysis, tests, and app

```powershell
python -m src.pipeline
python -m pytest -q
python -m streamlit run app.py
```

The pipeline writes `outputs/results.json`, seven PNGs in `figures/`, and `Analysis.pdf`. The app opens in a local browser. Select a branch and first product, then either choose one of two add-ons during the countdown or continue without one. Confirming the demo order writes an event to `demo_state.sqlite3` and updates the in-memory recommender exactly once. The SQLite file is ignored by Git. Delete it with the app stopped to reset demo history. The raw CSV is never modified.

For this Codex workspace, dependencies were installed into ignored `.deps/` using the bundled x64 Python. The commands above are the portable setup for other machines.

## Model and evaluation

The model counts distinct product pairs within transactions and divides smoothed pair counts by the number of baskets containing the first product. Global product popularity supplies a prior for sparse pairs. It returns two distinct menu products with positive recorded unit gross profit after a hypothetical 15% discount. After a confirmed order, its sufficient statistics update once using the order's event ID; showing an offer does not train it.

The benchmark fits January–March and evaluates April–June 2026. Because the CSV has no entry order, each multi-product transaction supplies every possible seed product, weighted so the transaction counts once. Hit@2 is the share of these transactions for which at least one of the two recommendations is among the other purchased products. `outputs/results.json` includes Hit@1, Hit@2, category Hit@2, candidate coverage, transaction-level confidence intervals, MRR@2, branch/daypart splits, and rolling monthly checks. Later months had already been explored in the prior proposal, so this is retrospective robustness evidence, not a pristine blind test.

## Revenue and operating decision

`Analysis.pdf` separates CSV-observed prices/costs from unknown incremental response. A 15% discount produces a known per-unit concession, but historical co-purchases cannot tell us how many buyers are truly new, how many existing buyers receive an unnecessary discount, or what they would otherwise have bought. The report therefore shows scenario calculations, break-even thresholds, operating cost categories, marketing copy and placement, and a prospective randomized pilot. **Do not present the scenario amounts as a revenue forecast.**

The minimum pilot randomly assigns eligible checkouts before the offer appears to either no offer or the exact two-product, 15-second, 15%-off experience. Compare total basket gross profit and revenue per eligible checkout, including timeouts and refusals, then subtract measured deployment and fulfillment costs. Add a no-discount suggestion arm only if sample size supports it.

## Known limitations

- No item-entry sequence or offer-response labels in the CSV; offline accuracy is not conversion accuracy.
- No stock, staff, prep-time, queue, packaging, or hosting-cost observations. Operational figures require measured inputs or labelled assumptions.
- Transaction IDs start with `SYN-`; confirm data provenance before a real deployment.
- The Streamlit demo is single-process local software. A production POS integration would need durable, shared model updates, availability checks, security, and operational monitoring.
