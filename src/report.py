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
    example = results["example_economics"]
    pair = results["pair_example"]

    p("STORIES COFFEE", "SmallX")
    p("Two-product checkout offer:<br/>evidence, model, and economics", "CoverTitle")
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
    with_time = bench["models"]["pair_daypart"]
    pp_gain = (product_pair["hit_at_2"] - popularity["hit_at_2"]) * 100
    cases = results["portfolio_scenarios"]["scenarios"]
    case_5_5 = next(s for s in cases if s["new_add_on_rate_assumed"] == .05 and
                    s["existing_buyers_discounted_rate_assumed"] == .05)
    case_5_10 = next(s for s in cases if s["new_add_on_rate_assumed"] == .05 and
                     s["existing_buyers_discounted_rate_assumed"] == .10)
    heading("Did the idea improve anything?")
    p(f"<b>Historical prediction: modestly.</b> On {product_pair['transactions']:,} later-period "
      f"multi-product baskets, the selected product-pair rule achieved {product_pair['hit_at_2']:.2%} "
      f"Hit@2 versus {popularity['hit_at_2']:.2%} for two popular items, a {pp_gain:.2f} "
      f"percentage-point gain. Adding daypart reached {with_time['hit_at_2']:.2%}, so it was omitted "
      "from the live rule. This is retrospective prediction, not customer response to a prompt.")
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

    captions = [
        ("2. Time and branch", "01_hour_branch.png",
         "Counts use transactions per branch-hour. Multi-product share divides multi-product transactions by all transactions in each branch-hour. Traffic is not a measure of queue length or capacity."),
        ("3. Category mix by daypart", "02_category_daypart.png",
         "Each transaction/category presence is counted once. Shares are within daypart and describe product mix, not a probability that a recommendation will convert."),
        ("4. Product-pair association", "03_pair_lift.png",
         "Lift compares observed pair frequency with the expectation under unconditioned independence. Only pairs with at least 20 transactions are shown; lift remains associational and can reflect context and basket size."),
        ("5. Example pairing", "04_example_pair.png",
         f"{escape(pair['seed'])} and {escape(pair['addon'])} occur together in {pair['total_pair_transactions']} completed transactions. Bars divide pair baskets by seed-containing baskets in each branch and daypart; detailed cell counts are in outputs/results.json."),
        ("6. Other factors", "05_other_factors.png",
         "Weekday, month, and order type are plotted even when differences are small. Rates use all completed transactions in each group. Effects can be confounded by branch, product mix, and traffic."),
        ("7. Discount and margin", "06_discount_margin.png",
         "The left panel is a descriptive split by whether any line was discounted; it is not a causal discount estimate. The right panel uses branch-product median price and cost to calculate a hypothetical 15%-off unit margin."),
        ("8. Retrospective model comparison", "07_model_ablation.png",
         f"Models fit January-March and evaluate April-June. Best plotted Hit@2 is {escape(results['best_hit2_mode'])}; that choice is exploratory because later months were already discussed in prior project context."),
    ]
    for title, name, caption in captions:
        heading(title)
        story.append(_image(figures/name))
        story.append(Spacer(1, 10))
        p(caption, "SmallX")
        story.append(PageBreak())

    heading("9. Model and validation")
    p("The live recommender is a smoothed product-pair co-purchase table. It records pair counts and "
      "seed-product exposures, with global popularity as a prior for sparse pairs. The benchmark also tests "
      "daypart and branch conditioning with additional shrinkage. The live rule returns two distinct menu products "
      "with positive hypothetical discounted unit gross "
      "profit. A completed local demo order updates counts once using its event ID; a displayed suggestion does not.")
    rows = [["Rule", "Hit@1", "Hit@2 (95% CI)", "MRR@2"]]
    for mode, r in bench["models"].items():
        lo, hi = r["hit_at_2_ci95"]
        rows.append([mode, f"{r['hit_at_1']:.1%}", f"{r['hit_at_2']:.1%} ({lo:.1%}-{hi:.1%})", f"{r['mrr_at_2']:.3f}"])
    table(rows, [135, 70, 210, 105])
    p(f"Training transactions: {bench['train_transactions']:,}. Evaluation transactions: "
      f"{bench['test_transactions']:,}; the metric denominator is multi-product transactions in that period "
      "with a pseudo-seed. Hit@2 means at least one actual other product is in the two suggestions. "
      "It does not measure add-on conversion or causal sales uplift.")
    selected = bench["models"]["pair"]
    p(f"The selected pair rule has {selected['category_hit_at_2']:.1%} category-level Hit@2 and "
      f"{selected['candidate_coverage']:.0%} candidate coverage across evaluated seeds. "
      "The reported 95% intervals use transaction-level standard errors; they describe retrospective "
      "ranking uncertainty, not uncertainty in business uplift.")
    roll = results["rolling_best"]
    table([["Month", "Multi-product test baskets", "Hit@2"]] +
          [[m, f"{v['transactions']:,}", f"{v['hit_at_2']:.1%}"] for m, v in roll.items()], [150, 210, 160])
    p("A neural network is not used: the dataset is small, there is no intervention-response label, and a "
      "count-based model is directly updatable and auditable. Adding daypart and branch reduced Hit@2 in "
      "this retrospective evaluation, so the app uses the simpler product-pair policy. Time remains available "
      "for future testing when new intervention data arrive.")
    story.append(PageBreak())

    heading("10. Financial sensitivity - example, not forecast")
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

    heading("11. Portfolio-scale sensitivity")
    portfolio = results["portfolio_scenarios"]
    cost = portfolio["operating_cost_assumptions"]
    p(f"There are {portfolio['completed_one_product_baskets_proxy']:,} completed one-product transactions. "
      "Using them as a historical sizing proxy, the final product-pair model generates two offers for each basket. "
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

    heading("12. Marketing, operations, and pilot")
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
