# Stories Coffee: two-product checkout add-on

This repository contains a reproducible analysis of `stories_transactions.csv`, a small online-trainable neural recommender, a local Streamlit checkout demo, and [Analysis.pdf](Analysis.pdf). The demo offers two add-ons for **15 seconds** and applies **15% off only the add-on selected in time**. It does not process real payments.

## What the evidence says

- The supplied CSV contains **51,177 line records** from **33,887 transactions** across three branches, 1 January–30 June 2026. Recorded revenue is **$305,925.14** and recorded gross profit is **$179,430.49**.
- The **product-only neural network reached 11.44% Hit@2** on the held-out May–June pseudo-checkout baskets, compared with **10.96%** for a product-pair count baseline and **9.98%** for two globally popular products. This is a modest retrospective prediction improvement, not measured offer conversion.
- These figures measure whether two suggested products appear in a **completed historical basket**. They do **not** measure whether a prompt increases purchase, revenue, or profit. The CSV contains no recommendation exposures, entry sequence, or treatment assignment. The report gives labelled sensitivity scenarios and a randomized pilot design.

## Repository contents

| Path | Purpose |
|---|---|
| `app.py` | Streamlit customer-facing demo with server-side 15-second expiry and one-time purchase updates |
| `src/data.py` | CSV validation, numeric audit encoding, and transaction-level baskets |
| `src/online_nn.py` | Product-only 16-unit neural recommender and online gradient updates |
| `src/recommender.py` | Count-based comparison baselines |
| `src/train.py` | Chronological split, architecture validation, final six-month refit |
| `src/evaluate.py` | Held-out and rolling retrospective benchmarks |
| `src/analysis.py`, `src/feature_study.py` | Factor and input-ablation experiments, financial scenarios, and ten reproducible plots |
| `src/economics.py` | Discount, gross profit, and break-even arithmetic |
| `src/report.py` | PDF assembly from generated results |
| `src/pipeline.py` | One-command analysis and report build |
| `models/nn_recommender.npz` | Saved six-month neural weights and product vocabulary |
| `figures/`, `outputs/results.json` | Generated plots, training curves, and computed tables |
| `Analysis.pdf` | Reviewed analysis and pilot proposal |

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

The pipeline writes `outputs/results.json`, ten PNGs in `figures/`, `models/nn_recommender.npz`, and `Analysis.pdf`. **Run the pipeline before starting the app.** The app opens in a local browser. Select a branch and first product, then either choose one of two add-ons during the countdown or continue without one. Confirming the demo order writes an event to `demo_state.sqlite3` and applies one online neural gradient step if the order has a complementary product. The SQLite file is ignored by Git. Delete it with the app stopped to reset demo history. The raw CSV and saved base weights are never modified by demo orders.

For this Codex workspace, dependencies were installed into ignored `.deps/` using the bundled x64 Python. The commands above are the portable setup for other machines.

## Model and evaluation

The model takes **only the first product** as input: a one-hot vector over the 45 products. It has one 16-unit tanh hidden layer and a masked softmax over the other products. It returns the top two distinct products. Targets are the other distinct products in a completed basket, normalized to sum to one; each transaction contributes total weight one across possible seed orientations. It trains with Adam and transaction-weighted cross-entropy. After a confirmed multi-product order, one online SGD step updates the in-memory model exactly once using the order's event ID; showing or clicking an offer does not train it. On restart, completed demo orders replay from SQLite onto the saved six-month base model.

The benchmark fits January–March, selects between 16 and 32 hidden units using April validation, and evaluates once on May–June 2026. The final app artifact then refits the selected network on all six months for the preselected epoch count. That post-refit artifact has no untouched test of its own; the reported test metrics belong to the pre-refit model. Because the CSV has no entry order, each multi-product transaction supplies every possible seed product, weighted so the transaction counts once. Hit@2 is the share of these transactions for which at least one of the two recommendations is among the other purchased products. `outputs/results.json` includes losses, Hit@1, Hit@2, category Hit@2, candidate coverage, transaction-level confidence intervals, MRR@2, and branch/daypart splits. The test months had already been discussed in prior project work, so this is retrospective evidence, not a pristine prospective study.

Every raw CSV column is also converted to a numeric representation for an **audit-only** frame, documented in the PDF. Product is the sole network input. IDs, branch, time, prices, discounts, revenue, and gross profit are excluded from model features to prevent leakage and honor the product-only requirement. The one-hot input already has unit norm; no z-score scaling is needed.

The report's input-justification study checks multi-product basket rates by branch, daypart, weekday, month, order type, and customer-ID availability, then compares product-only and context-aware count rules on the chronological held-out set. The measured basket-size associations for those factors are small (Cramer's V below 0.02). Daypart raises the count rule's May-June Hit@2 by 0.27 percentage points, but its paired 95% interval includes zero. A recorded discount has a larger association but is determined during checkout, so it cannot be a first-product input. These diagnostics support a simple product-only starting model; they do not prove contextual data can never help.

## Revenue and operating decision

`Analysis.pdf` separates CSV-observed prices/costs from unknown incremental response. A 15% discount produces a known per-unit concession, but historical co-purchases cannot tell us how many buyers are truly new, how many existing buyers receive an unnecessary discount, or what they would otherwise have bought. The report therefore shows scenario calculations, break-even thresholds, operating cost categories, marketing copy and placement, and a prospective randomized pilot. **Do not present the scenario amounts as a revenue forecast.**

The minimum pilot randomly assigns eligible checkouts before the offer appears to either no offer or the exact two-product, 15-second, 15%-off experience. Compare total basket gross profit and revenue per eligible checkout, including timeouts and refusals, then subtract measured deployment and fulfillment costs. Add a no-discount suggestion arm only if sample size supports it.

## Known limitations

- No item-entry sequence or offer-response labels in the CSV; offline accuracy is not conversion accuracy.
- No stock, staff, prep-time, queue, packaging, or hosting-cost observations. Operational figures require measured inputs or labelled assumptions.
- Transaction IDs start with `SYN-`; confirm data provenance before a real deployment.
- The Streamlit demo is single-process local software. A production POS integration would need durable, shared model updates, availability checks, security, and operational monitoring.
