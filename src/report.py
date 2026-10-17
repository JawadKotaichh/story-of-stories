from __future__ import annotations

from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                Image, PageBreak, KeepTogether)

from .economics import add_on_economics

GREEN = colors.HexColor("#234A3C")
TAN = colors.HexColor("#BA693B")
PALE = colors.HexColor("#EFF4F0")


def _image(path: Path, max_width=7.1*inch, max_height=5.6*inch):
    from PIL import Image as PILImage
    with PILImage.open(path) as im:
        width, height = im.size
    ratio = min(max_width/width, max_height/height)
    return Image(str(path), width=width*ratio, height=height*ratio)


def build_report(results: dict, figures: Path, output: Path):
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CoverTitle", parent=styles["Title"], fontSize=27,
                              leading=33, textColor=GREEN, spaceAfter=18))
    styles.add(ParagraphStyle(name="HeadingX", parent=styles["Heading1"], fontSize=16,
                              leading=20, textColor=GREEN, spaceBefore=8, spaceAfter=10))
    styles.add(ParagraphStyle(name="BodyX", parent=styles["BodyText"], fontSize=10,
                              leading=14, spaceAfter=9))
    styles.add(ParagraphStyle(name="SmallX", parent=styles["BodyText"], fontSize=8,
                              leading=11, textColor=colors.HexColor("#4A5451"), spaceAfter=8))
    styles.add(ParagraphStyle(name="TableHeadX", parent=styles["SmallX"],
                              textColor=colors.white, fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle(name="CenterX", parent=styles["BodyX"], alignment=TA_CENTER))
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(output), pagesize=(612, 792), rightMargin=44, leftMargin=44,
                            topMargin=43, bottomMargin=43, title="Stories Coffee Add-On Analysis",
                            author="Stories Coffee project")
    story = []

    def p(text, style="BodyX"):
        story.append(Paragraph(text, styles[style]))

    def heading(text):
        p(text, "HeadingX")

    def table(rows, widths=None):
        t = Table([[Paragraph(escape(str(x)), styles["TableHeadX" if i == 0 else "SmallX"])
                    for x in row] for i, row in enumerate(rows)],
                  colWidths=widths, repeatRows=1, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), GREEN), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 12))

    audit = results["audit"]
    bench = results["benchmarks"]
    neural = results["neural_training"]
    example = results["example_economics"]
    pair = results["pair_example"]

    p("STORIES COFFEE", "SmallX")
    p("Product-only neural recommendations:<br/>training, evidence, and economics", "CoverTitle")
    p("Reproducible analysis of the supplied transaction CSV | 17 October 2026", "BodyX")
    story.append(Spacer(1, 15))
    heading("Executive decision")
    p("A customer selects one product; the prototype offers exactly two complementary products for 15 seconds. "
      "Choosing either add-on in time applies a 15% discount to that add-on only. The historical data can support "
      "which products to test and the unit economics. It cannot establish that this promotion increases revenue or profit.")
    p("<b>Recommendation:</b> use the working local demo and run a randomized checkout pilot. Measure total basket "
      "gross profit and revenue per eligible checkout against a no-offer control. Do not describe the scenario "
      "figures in this report as a forecast.")
    popularity = bench["models"]["global"]
    product_pair = bench["models"]["pair"]
    nn_test = neural["test_metrics"]
    nn_gain = (nn_test["hit_at_2"] - popularity["hit_at_2"]) * 100
    cases = results["portfolio_scenarios"]["scenarios"]
    case_5_5 = next(s for s in cases if s["new_add_on_rate_assumed"] == .05 and
                    s["existing_buyers_discounted_rate_assumed"] == .05)
    case_5_10 = next(s for s in cases if s["new_add_on_rate_assumed"] == .05 and
                     s["existing_buyers_discounted_rate_assumed"] == .10)
    heading("Did the idea improve anything?")
    p(f"<b>Historical prediction: modestly.</b> On {nn_test['transactions']:,} May-June "
      f"multi-product baskets, the selected neural network achieved {nn_test['hit_at_2']:.2%} "
      f"Hit@2 versus {product_pair['hit_at_2']:.2%} for a product-pair rule and "
      f"{popularity['hit_at_2']:.2%} for two popular items, a {nn_gain:.2f} "
      "percentage-point gain over popularity. This is retrospective prediction, not customer response to a prompt.")
    p(f"<b>Sales impact: not measured.</b> For illustration, assuming 5% genuinely new add-ons and 5% "
      f"existing-buyer discount leakage, the six-month proxy gives ${case_5_5['six_month_revenue_proxy']:,.0f} "
      f"extra revenue, ${case_5_5['six_month_gross_profit_proxy']:,.0f} extra gross profit, "
      f"and ${case_5_5['six_month_net_proxy_after_assumed_costs']:,.0f} after assumed operating costs. "
      f"With 10% leakage, that net becomes ${case_5_10['six_month_net_proxy_after_assumed_costs']:,.0f}. "
      "The CSV cannot establish either response rate; only a randomized pilot can establish uplift.")
    table([["Evidence class", "What is known"],
           ["Observed", f"{audit['transactions']:,} completed transactions, ${audit['revenue']:,.2f} recorded revenue."],
           ["Backtested", "Historical top-two basket prediction on later months; not offer response."],
           ["Scenario", "Financial effects under explicit assumed incremental and baseline-buyer rates."],
           ["Unknown", "Actual offer exposure, incremental conversion, substitution, labor, inventory, and net profit."]],
          [100, 420])
    p("<b>Data source:</b> stories_transactions.csv only. Transaction IDs begin with SYN-, a provenance signal "
      "that should be clarified before operational deployment. All final figures are regenerated by the repository code.", "SmallX")
    story.append(PageBreak())

    heading("1. Data audit and scope")
    table([["Measure", "Result"], ["Product lines", f"{audit['lines']:,}"],
           ["Transactions", f"{audit['transactions']:,}"],
           ["Period", f"{audit['date_min']} to {audit['date_max']}"],
           ["Branches / products / categories", f"{audit['branches']} / {audit['products']} / {audit['categories']}"],
           ["Recorded revenue", f"${audit['revenue']:,.2f}"],
           ["Recorded gross profit", f"${audit['gross_profit']:,.2f}"],
           ["Missing customer ID rows", f"{audit['missing_customer_rows']:,}"],
           ["Transactions with a discounted line", f"{audit['discounted_transactions']:,}"]], [310, 210])
    p("Transaction ID defines the basket. Pair counts use distinct product presence, while financial totals preserve "
      "quantity and recorded line revenue/gross profit. Date, time, branch, order type, and customer ID are checked "
      "for within-transaction consistency. Source amounts reconcile within two cents per line; cent differences may "
      "reflect rounding. Customer ID is omitted from the recommender because of missingness and lack of a verified "
      "personalization benefit.")
    p("<b>Offline pseudo-checkout:</b> the file does not contain entry sequence. Each multi-product basket is evaluated "
      "from every possible seed item with total weight one per transaction. This estimates retrospective ranking "
      "quality, not an actual point-of-sale impression or response.")
    story.append(PageBreak())

    heading("2. Preprocessing and numeric encoding")
    p("Every raw CSV field is converted to a numeric representation in an <b>audit-only</b> table. This makes "
      "missingness, type handling, and reproducibility explicit. The network is deliberately given only the "
      "selected product; transaction IDs, dates, branch, prices, discounts, and final revenue never enter its input.")
    table([["Field group", "Audit/analysis transformation", "Model input?"] ,
           ["Transaction ID", "Sorted integer code; grouping key", "No"],
           ["Date / Time", "Days since 1970 / seconds after midnight", "No - split and EDA only"],
           ["Branch / Order Type / Category", "Sorted integer code", "No"],
           ["Customer ID", "Sorted integer code; missing = -1", "No"],
           ["Product", "Sorted integer code; training-only vocabulary", "Yes - one-hot"],
           ["Quantity", "Original positive integer", "No"],
           ["Unit Price / Unit Cost", "Original USD numeric values", "No - economics only"],
           ["Discount Rate", "Original decimal fraction", "No - descriptive only"],
           ["Line Revenue / Gross Profit", "Original USD numeric values", "No - outcomes only"]],
          [175, 245, 100])
    p("<b>Model normalization:</b> a product is a 45-dimensional one-hot vector (one 1, all other entries 0); "
      "its Euclidean norm is already 1, so z-score scaling is unnecessary. Basket targets become a normalized "
      "distribution over the other distinct purchased products. Each basket contributes total training weight 1, "
      "regardless of whether it contains two or three products. Single-product baskets contain no positive "
      "complement label and are excluded from the ranking loss, but remain in EDA and opportunity sizing.")
    p("<b>Leakage controls:</b> vocabulary is learned on training records for evaluation; dates define chronological "
      "splits; no test basket updates the benchmark model. The final app model is retrained on all six months only "
      "after the test result is fixed. The numeric audit table is never passed to model.fit().")
    story.append(PageBreak())

    captions = [
        ("3. Time and branch", "01_hour_branch.png",
         "Counts use transactions per branch-hour. Multi-product share divides multi-product transactions by all transactions in each branch-hour. Traffic is not a measure of queue length or capacity."),
        ("4. Category mix by daypart", "02_category_daypart.png",
         "Each transaction/category presence is counted once. Shares are within daypart and describe product mix, not a probability that a recommendation will convert."),
        ("5. Product-pair association", "03_pair_lift.png",
         "Lift compares observed pair frequency with the expectation under unconditioned independence. Only pairs with at least 20 transactions are shown; lift remains associational and can reflect context and basket size."),
        ("6. Example pairing", "04_example_pair.png",
         f"{escape(pair['seed'])} and {escape(pair['addon'])} occur together in {pair['total_pair_transactions']} completed transactions. Bars divide pair baskets by seed-containing baskets in each branch and daypart; detailed cell counts are in outputs/results.json."),
        ("7. Other factors", "05_other_factors.png",
         "Weekday, month, and order type are plotted even when differences are small. Rates use all completed transactions in each group. Effects can be confounded by branch, product mix, and traffic."),
        ("8. Discount and margin", "06_discount_margin.png",
         "The left panel is a descriptive split by whether any line was discounted; it is not a causal discount estimate. The right panel uses branch-product median price and cost to calculate a hypothetical 15%-off unit margin."),
        ("9. Held-out model comparison", "07_model_ablation.png",
         "All models fit January-March and are evaluated on May-June after April validation selects neural architecture. The historical test period was discussed in previous project work, so this is retrospective evidence rather than a pristine prospective study."),
    ]
    for title, name, caption in captions:
        heading(title)
        story.append(_image(figures/name))
        story.append(Spacer(1, 10))
        p(caption, "SmallX")
        story.append(PageBreak())

    heading("10. Neural training decisions and learning curves")
    story.append(_image(figures / "08_neural_training.png"))
    story.append(Spacer(1, 10))
    p("Two small networks were tried: 45 product inputs, either 16 or 32 tanh hidden units, and 45 softmax "
      "outputs. The output corresponding to the selected product is masked. Training uses transaction-weighted "
      "cross-entropy, Adam with learning rate 0.01, batches of 512, L2 weight decay 0.0001, a fixed seed, "
      "and early stopping after six epochs without lower April validation loss. The architecture is selected "
      "by April Hit@2, with validation loss as a tie-breaker; May-June is not used for tuning.", "SmallX")
    story.append(PageBreak())

    heading("11. Train / validation / test results")
    split = neural["split"]
    table([["Partition", "Dates", "Transactions", "Multi-product baskets"],
           ["Train", split["train"], f"{split['train_transactions']:,}", f"{split['train_multi_product_transactions']:,}"],
           ["Validation", split["validation"], f"{split['validation_transactions']:,}", f"{split['validation_multi_product_transactions']:,}"],
           ["Test", split["test"], f"{split['test_transactions']:,}", f"{split['test_multi_product_transactions']:,}"]],
          [85, 195, 110, 130])
    table([["Hidden units", "Chosen epoch", "April validation Hit@2", "Validation loss"]] +
          [[str(c["hidden_units"]), str(c["best_epoch"]),
            f"{c['validation_metrics']['hit_at_2']:.2%}", f"{c['validation_loss']:.3f}"]
           for c in neural["candidates"]], [95, 105, 170, 150])
    p(f"<b>Selected network:</b> {neural['architecture']}. The input is exactly one product; the final output "
      "is the two highest-scoring different products. The app loads weights refit on all six months for the "
      f"preselected {neural['selected_epoch']} epochs. Its held-out result below belongs to the pre-refit "
      "train/validation model, not the post-refit app weights.")
    rows = [["Rule", "Hit@1", "Hit@2 (95% CI)", "Category Hit@2"]]
    for mode in ["global", "pair", "pair_daypart"]:
        r = bench["models"][mode]
        lo, hi = r["hit_at_2_ci95"]
        rows.append([mode, f"{r['hit_at_1']:.2%}", f"{r['hit_at_2']:.2%} ({lo:.2%}-{hi:.2%})",
                     f"{r['category_hit_at_2']:.2%}"])
    lo, hi = nn_test["hit_at_2_ci95"]
    rows.append(["Neural network", f"{nn_test['hit_at_1']:.2%}",
                 f"{nn_test['hit_at_2']:.2%} ({lo:.2%}-{hi:.2%})",
                 f"{nn_test['category_hit_at_2']:.2%}"])
    table(rows, [110, 75, 225, 110])
    p("Hit@2 counts a transaction as successful when at least one of the two recommendations appears among "
      "its other purchased products. Every possible seed orientation is evaluated, weighted to total one per "
      "transaction. All shown models cover 100% of known seed products. MRR@2, branch/daypart breakdowns, "
      "full candidate histories, and exact values are in outputs/results.json. Intervals use transaction-level "
      "standard errors. This is basket prediction, not offer conversion or causal uplift.")
    p("<b>Online learning:</b> every confirmed multi-product demo order produces one gradient step at learning "
      "rate 0.025; an event ID prevents double updates. Single-product orders are logged but have no positive "
      "complement target. On restart, the app loads the saved six-month base weights and replays completed "
      "demo events once. No prompt impression is used as a training label.")
    story.append(PageBreak())

    heading("12. Why product is the sole neural input: factor tests")
    inputs = results["input_justification"]
    factors = inputs["factors"]
    p("We tested the claim that other CSV fields predict combo buying rather than assuming it. The outcome here "
      "is whether a completed transaction contains more than one distinct product. Cramer's V is an association "
      "effect size from 0 (none) to 1 (strong); these are descriptive relationships, not causal effects. "
      "A small p-value alone would be unhelpful at this sample size.")
    story.append(_image(figures / "09_input_associations.png", max_height=3.65*inch))
    rows = [["Recorded factor", "Cramer's V", "Lowest / highest multi-product rate", "Use at offer time?"]]
    labels = {"branch": "Branch", "daypart": "Daypart", "weekday": "Weekday",
              "month": "Month", "order_type": "Order type",
              "customer_id_recorded": "Customer ID present", "discounted_line": "Discounted line"}
    for key, label in labels.items():
        f = factors[key]
        availability = "Potentially" if key not in ["discounted_line"] else "No - post-purchase"
        rows.append([label, f"{f['cramers_v']:.3f}",
                     f"{f['min_rate']:.1%} / {f['max_rate']:.1%}", availability])
    table(rows, [135, 76, 181, 128])
    p("Branch, daypart, weekday, month, order type, and recorded-customer availability all have V below 0.02. "
      "The discounted-line indicator has a larger association, but is determined during the completed sale; "
      "using it at first-product selection would leak the outcome. Customer ID itself is an identifier with "
      "substantial missingness, not a numeric quantity with meaningful distance.", "SmallX")
    story.append(PageBreak())

    heading("13. Do extra checkout inputs improve recommendations?")
    p("We also tested whether known checkout context improves the <b>identity of the companion product</b>. "
      "This diagnostic keeps the same smoothed product-pair count rule and adds one context at a time. "
      "It fits January-March, picks smoothing on April, and reports May-June Hit@2. It is a feature "
      "ablation for a simple comparator, not a retraining of the neural architecture. Exact month is "
      "not tested as a context key because future months have no matching training observations.")
    story.append(_image(figures / "10_input_ablation.png", max_height=3.5*inch))
    ablation = inputs["context_ablation"]
    rows = [["Count-rule input", "May-June Hit@2", "Change vs product only (paired 95% CI)"]]
    input_labels = {"product_only": "Product only", "branch": "Product + branch",
                    "daypart": "Product + daypart", "weekday": "Product + weekday",
                    "order_type": "Product + order type",
                    "branch_daypart": "Product + branch + daypart"}
    for key in ["product_only", "branch", "daypart", "weekday", "order_type", "branch_daypart"]:
        result = ablation[key]
        delta = ("Reference" if key == "product_only" else
                 f"{result['test_delta_vs_product_only']*100:+.2f} pp "
                 f"({result['paired_delta_ci95'][0]*100:+.3f}, "
                 f"{result['paired_delta_ci95'][1]*100:+.3f})")
        rows.append([input_labels[key], f"{result['test_hit2']:.2%}", delta])
    table(rows, [158, 115, 247])
    p("Daypart has the highest point estimate for this count rule, but its paired interval includes zero; "
      "the other tested contexts show no reliable held-out gain over the product-only version. "
      "Intervals account for pairing on the same test baskets, not for all "
      "model-selection uncertainty. The product-only neural network scored "
      f"{nn_test['hit_at_2']:.2%} Hit@2 on this period. We keep its input to the selected product because "
      "that is available at the exact offer moment, is simpler to update, and meets the product brief. "
      "These experiments do not prove that all contextual signals are useless; a prospective test or a "
      "controlled neural input ablation would be needed for that stronger claim.", "SmallX")
    story.append(PageBreak())

    heading("14. Financial sensitivity - example, not forecast")
    e = example
    unit = add_on_economics(e["price"], e["cost"])
    p(f"Example: Harbour, first item {pair['seed']}, offered add-on {pair['addon']}. "
      f"Median add-on price ${e['price']:.2f}; median recorded unit cost ${e['cost']:.2f}. "
      f"At 15% off, the rounded add-on selling price is ${unit['discounted_price']} and unit "
      f"gross profit before extra operating costs is ${unit['discounted_gross_profit']}.")
    p(f"The CSV contains {e['seed_baskets_proxy']:,} Harbour baskets with the seed and "
      f"{e['seed_only_baskets_proxy']:,} completed seed-only baskets. Neither count is a known number of live offer impressions.")
    p("Per eligible offer, under the stated simplifying assumptions: incremental revenue = newly added rate x "
      "discounted price - rate of existing buyers receiving a discount x concession - substituted revenue. "
      "Incremental gross profit replaces price with discounted unit gross profit, then subtracts discount leakage, "
      "substitution, and added variable operating cost. All response rates are unknown until tested.")
    rows = [["Assumed new add-on", "Existing buyers discounted", "Revenue / offer", "Gross profit / offer"]]
    for row in e["scenarios_per_offer"]:
        if row["new_add_on_rate"] in [.03, .05, .10] and row["baseline_buyers_discounted_rate"] in [0, .05, .10]:
            rows.append([f"{row['new_add_on_rate']:.0%}", f"{row['baseline_buyers_discounted_rate']:.0%}",
                         f"${row['incremental_revenue']:.3f}", f"${row['incremental_gross_profit']:.3f}"])
    table(rows, [120, 165, 110, 125])
    p(f"At an assumed 5% existing-buyer discount leakage and zero substitution/extra cost, new add-on "
      f"conversion would need to exceed {e['break_even_new_rate_at_5pct_existing']:.1%} for positive "
      "incremental gross profit in this simplified example. Larger operating or substitution costs raise this threshold.")
    story.append(PageBreak())

    heading("15. Portfolio-scale sensitivity")
    portfolio = results["portfolio_scenarios"]
    cost = portfolio["operating_cost_assumptions"]
    p(f"There are {portfolio['completed_one_product_baskets_proxy']:,} completed one-product transactions. "
      "Using them as a historical sizing proxy, the final neural model generates two offers for each basket. "
      f"An equal mix of the two offers has mean discounted selling price "
      f"${portfolio['average_of_two_offered_discounted_prices']:.2f}, mean discounted unit gross profit "
      f"${portfolio['average_of_two_offered_discounted_gross_profits']:.2f}, and mean discount concession "
      f"${portfolio['average_of_two_offered_discount_concessions']:.2f}. These item amounts are computed from the "
      "CSV; the 50/50 choice mix and response rates are assumptions. One-product completed receipts are not "
      "known live offer impressions.")
    p("The following six-month numbers multiply per-offer scenarios by that sizing proxy. They are "
      "<b>not forecasts</b>. Net scenarios additionally assume $0.25 per newly added item, $0.02 per offer, "
      "$25 monthly fixed expense, and $500 one-time development expense. No such operating cost is recorded "
      "in the CSV; replace each assumption with a quote or pilot observation before a rollout decision.")
    rows = [["New add-on", "Existing buyer discount", "Extra revenue", "Extra gross profit", "Net after assumed costs"]]
    for row in portfolio["scenarios"]:
        if row["new_add_on_rate_assumed"] in [.03, .05, .10] and row["existing_buyers_discounted_rate_assumed"] in [0, .05, .10]:
            rows.append([f"{row['new_add_on_rate_assumed']:.0%}",
                         f"{row['existing_buyers_discounted_rate_assumed']:.0%}",
                         f"${row['six_month_revenue_proxy']:,.0f}",
                         f"${row['six_month_gross_profit_proxy']:,.0f}",
                         f"${row['six_month_net_proxy_after_assumed_costs']:,.0f}"])
    table(rows, [78, 115, 95, 105, 127])
    p("These calculations assume no substitution and no effect on first-item sales. Either could make the "
      "outcome worse. Conversely, repeat visits or a different offer mix could change it. The randomized pilot "
      "must measure full baskets, not only recommended-item redemptions.")
    story.append(PageBreak())

    heading("16. Marketing, operations, and pilot")
    p("<b>Customer presentation:</b> after the first item, show two relevant add-ons, each original and discounted "
      "price, and a plain 15-second timer. Discount only a selected add-on. Monitor whether urgency increases "
      "abandonment or dissatisfaction. Branch and daypart can be used for targeting only when retrospective "
      "evidence supports them.")
    table([["Cost", "CSV evidence", "Needed before rollout"],
           ["Discount concession", "Listed price and 15% rule", "Actual redemptions and baseline buyers"],
           ["Product cost", "Recorded unit cost by branch", "Confirm cost definition"],
           ["Development / hosting", "None", "Time log and supplier quote"],
           ["Staff / prep / packaging", "None", "Observed incremental minutes and costs"],
           ["Stockouts / substitution", "None", "Inventory and full-basket outcomes"]],
          [150, 170, 200])
    p("<b>Minimum randomized pilot:</b> assign eligible checkouts before the offer is displayed to either ordinary "
      "checkout or the exact two-item, 15-second, 15%-off experience. Keep assignment stable on refresh and log "
      "both shown items, expiry, response, completed basket, revenue, gross profit, and order completion. "
      "Analyze all assigned checkouts, including refusals/timeouts. Primary endpoint is total basket gross "
      "profit per eligible checkout with a confidence interval; revenue per eligible checkout is a co-primary "
      "business view or key secondary metric. Obtain pilot variance before final sample sizing.")
    p("If volume permits, add an otherwise identical no-discount arm to separate suggestion effects from the "
      "discount. Measure baseline-buyer discount leakage and substitution across the whole basket. Scale only "
      "when incremental contribution exceeds operating costs without unacceptable customer or service effects.")
    p("<b>Reproduction:</b> run <font name='Courier'>python -m src.pipeline</font> from the repository root, "
      "then <font name='Courier'>streamlit run app.py</font>. The CSV remains the only source of historical "
      "business figures; outputs/results.json contains the complete computed tables and cell counts.", "SmallX")

    def page(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(GREEN)
        canvas.line(44, 37, 568, 37)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(GREEN)
        canvas.drawString(44, 25, "STORIES COFFEE  /  ADD-ON ANALYSIS")
        canvas.drawRightString(568, 25, f"{document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=page, onLaterPages=page)
