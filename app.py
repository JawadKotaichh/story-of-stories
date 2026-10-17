"""Local customer-facing demo. Run: streamlit run app.py"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import streamlit as st

from src.data import build_baskets, load_lines, price_book
from src.economics import add_on_economics, money
from src.recommender import IncrementalRecommender, make_demo_basket

ROOT = Path(__file__).resolve().parent
CSV = ROOT / "stories_transactions.csv"
DB = ROOT / "demo_state.sqlite3"
LOCAL_TZ = ZoneInfo("Asia/Beirut")


def connection():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS completed_orders (
        event_id TEXT PRIMARY KEY, started_utc TEXT NOT NULL, completed_utc TEXT NOT NULL,
        branch TEXT NOT NULL, seed TEXT NOT NULL, suggestions TEXT NOT NULL,
        selected TEXT, discounted_price REAL, revenue REAL NOT NULL, gross_profit REAL NOT NULL
    )""")
    return con


@st.cache_resource(show_spinner="Training from the supplied transactions...")
def resources():
    df = load_lines(CSV)
    baskets = build_baskets(df)
    book = price_book(df)
    products = sorted(df["Product"].unique().tolist())
    model = IncrementalRecommender(products, mode="pair").fit(baskets)
    with connection() as con:
        rows = con.execute("SELECT event_id, completed_utc, branch, seed, selected, revenue, gross_profit FROM completed_orders ORDER BY completed_utc").fetchall()
    for eid, completed, branch, seed, selected, revenue, gp in rows:
        bought = [seed] + ([selected] if selected else [])
        model.update(make_demo_basket(eid, datetime.fromisoformat(completed), branch, bought, revenue, gp))
    return model, book, products


def reset():
    for key in ["stage", "seed", "branch", "suggestions", "started_utc", "deadline_utc", "selected", "event_id", "hour"]:
        st.session_state.pop(key, None)
    st.rerun()


st.set_page_config(page_title="Stories Coffee | Add-on offer", page_icon="☕", layout="centered")
st.title("Stories Coffee")
st.caption("Checkout add-on demo · historical recommendations, simulated purchase")

try:
    model, book, products = resources()
except Exception as exc:
    st.error(f"Cannot load the local transaction CSV: {exc}")
    st.stop()

stage = st.session_state.get("stage", "select")
if stage == "select":
    now = datetime.now(LOCAL_TZ)
    with st.form("first_product"):
        branch = st.selectbox("Branch", sorted({b for b, _ in book}))
        seed = st.selectbox("Choose a product", products)
        hour = now.hour
        submitted = st.form_submit_button("Add first product", type="primary")
    if submitted:
        available = {p for p in products if (branch, p) in book and
                     float(add_on_economics(book[(branch, p)]["price"], book[(branch, p)]["cost"])["discounted_gross_profit"]) > 0}
        suggestions = model.recommend(seed, branch, hour, available=available)
        started = datetime.now(timezone.utc)
        st.session_state.update(stage="offer", branch=branch, seed=seed, hour=hour,
                                suggestions=suggestions, started_utc=started.isoformat(),
                                deadline_utc=(started + timedelta(seconds=15)).isoformat(),
                                selected=None, event_id="DEMO-" + uuid4().hex)
        st.rerun()

elif stage == "offer":
    seed = st.session_state.seed
    branch = st.session_state.branch
    st.subheader(f"Your basket: {seed}")
    st.write(f"Original item: **${money(book[(branch, seed)]['price'])}**")
    st.info("Choose one of these two products within 15 seconds for 15% off that add-on.")

    @st.fragment(run_every="1s")
    def offer_fragment():
        left = (datetime.fromisoformat(st.session_state.deadline_utc) - datetime.now(timezone.utc)).total_seconds()
        if left <= 0:
            st.session_state.stage = "review"
            st.session_state.selected = None
            st.rerun()
        st.metric("Time remaining", f"{max(0, int(left + .999))} seconds")
        cols = st.columns(2)
        for col, suggestion in zip(cols, st.session_state.suggestions):
            with col:
                item = suggestion.product
                e = add_on_economics(book[(branch, item)]["price"], book[(branch, item)]["cost"])
                st.markdown(f"**{item}**")
                st.html(f"<p><s>${e['price']}</s> &nbsp; <strong>${e['discounted_price']}</strong></p>")
                if st.button(f"Add {item}", key=f"choose-{item}", use_container_width=True):
                    if datetime.now(timezone.utc) < datetime.fromisoformat(st.session_state.deadline_utc):
                        st.session_state.selected = item
                    else:
                        st.session_state.selected = None
                    st.session_state.stage = "review"
                    st.rerun()
        if st.button("Continue without add-on"):
            st.session_state.selected = None
            st.session_state.stage = "review"
            st.rerun()

    offer_fragment()
    with st.expander("Why these suggestions?"):
        for suggestion in st.session_state.suggestions:
            st.write(f"{suggestion.product}: appeared with {seed} in {suggestion.pair_count} historical transactions; "
                     f"{suggestion.context_count} in the selected daypart across branches.")
        st.caption("The product-pair rule won the retrospective benchmark; adding time did not improve Hit@2. "
                   "The displayed counts describe past co-purchases, not who will respond to this offer.")

elif stage == "review":
    seed, branch, selected = st.session_state.seed, st.session_state.branch, st.session_state.selected
    first = book[(branch, seed)]
    subtotal = money(first["price"])
    gp = money(first["price"] - first["cost"])
    st.subheader("Review your order")
    st.write(f"{seed}: ${subtotal}")
    if selected:
        e = add_on_economics(book[(branch, selected)]["price"], book[(branch, selected)]["cost"])
        subtotal += e["discounted_price"]
        gp += e["discounted_gross_profit"]
        st.write(f"{selected} (15% off): ${e['discounted_price']}")
    else:
        st.write("No add-on selected. Your original item keeps its normal price.")
    st.metric("Total", f"${subtotal}")
    if st.button("Confirm demo purchase", type="primary"):
        with connection() as con:
            cursor = con.execute(
                "INSERT OR IGNORE INTO completed_orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (st.session_state.event_id, st.session_state.started_utc, datetime.now(timezone.utc).isoformat(),
                 branch, seed, " | ".join(s.product for s in st.session_state.suggestions),
                 selected, float(e["discounted_price"]) if selected else None,
                 float(subtotal), float(gp)))
            inserted = cursor.rowcount == 1
        if inserted:
            model.update(make_demo_basket(st.session_state.event_id, datetime.now(LOCAL_TZ), branch,
                                          [seed] + ([selected] if selected else []), float(subtotal), float(gp)))
        st.session_state.stage = "done"
        st.rerun()
    st.button("Start over", on_click=reset)

else:
    st.success("Demo purchase recorded. The recommender updated from this completed order once.")
    st.button("New order", on_click=reset)

st.divider()
st.caption("Local prototype. No real payment or inventory check. Offer effectiveness requires a randomized pilot.")
