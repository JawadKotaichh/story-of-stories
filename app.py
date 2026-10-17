"""Local customer-facing demo. Run: streamlit run app.py"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import streamlit as st

from src.data import load_lines, price_book
from src.economics import add_on_economics, money
from src.online_nn import OnlineNeuralRecommender
from src.product_images import product_image_url
from src.recommender import make_demo_basket

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


@st.cache_resource(show_spinner="Loading the trained neural model...")
def resources():
    df = load_lines(CSV)
    book = price_book(df)
    model_path = ROOT / "models" / "nn_recommender.npz"
    if not model_path.exists():
        raise FileNotFoundError("Trained model missing. Run: python -m src.pipeline")
    model = OnlineNeuralRecommender.load(model_path)
    products = model.products
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


def product_card(product, price, key):
    """The photograph and its short label form one accessible native button."""
    return st.button(
        f"![{product}]({product_image_url(product)})\n\n**{product}**  \n{price}",
        key=key, use_container_width=True,
    )


def basket_item(product, price, label):
    st.html(
        f'<div class="basket-item"><img src="{escape(product_image_url(product), quote=True)}" '
        f'alt="{escape(product, quote=True)}"><div class="item-info">'
        f'<small>{escape(label)}</small>{escape(product)}</div>'
        f'<span class="price">${price}</span></div>'
    )


st.set_page_config(page_title="Stories Coffee | Add-on offer", page_icon="☕", layout="wide")
st.html(f"<style>{(ROOT / 'ui' / 'styles.css').read_text(encoding='utf-8')}</style>")
stage = st.session_state.get("stage", "select")
step = {"select": 0, "offer": 1, "review": 2, "done": 2}.get(stage, 2)
steps = "".join(
    f'<span class="{"active" if index == step else ""}">{label}</span>'
    for index, label in enumerate(["01 Choose", "02 Pair", "03 Enjoy"])
)
st.html(f'<header class="brand-bar"><div class="brand">stories<small>COFFEE</small></div>'
        f'<nav class="steps" aria-label="Order progress">{steps}</nav></header>')

try:
    model, book, products = resources()
except Exception as exc:
    st.error(f"Cannot load the local data or trained model: {exc}")
    st.stop()

if stage == "select":
    now = datetime.now(LOCAL_TZ)
    st.html('<h1 class="page-heading">Pick your favourite.</h1>'
            '<p class="page-note">Good things start here.</p>')
    branch = st.radio("Branch", sorted({b for b, _ in book}), horizontal=True, key="branch-choice")
    with st.container(key="product-grid"):
        for start in range(0, len(products), 4):
            for col, seed in zip(st.columns(4), products[start:start + 4]):
                with col:
                    if product_card(seed, f"${money(book[(branch, seed)]['price'])}", key=f"product-{seed}"):
                        suggestions = model.recommend(seed)
                        started = datetime.now(timezone.utc)
                        st.session_state.update(stage="offer", branch=branch, seed=seed, hour=now.hour,
                                                suggestions=suggestions, started_utc=started.isoformat(),
                                                deadline_utc=(started + timedelta(seconds=15)).isoformat(),
                                                selected=None, event_id="DEMO-" + uuid4().hex)
                        st.rerun()

elif stage == "offer":
    seed = st.session_state.seed
    branch = st.session_state.branch
    basket_item(seed, money(book[(branch, seed)]["price"]), "Your pick")
    st.html('<div class="section-heading"><h1 class="page-heading">Better together.</h1>'
            '<span class="offer-badge">15% off your add-on</span></div>')

    @st.fragment(run_every="1s")
    def offer_fragment():
        left = (datetime.fromisoformat(st.session_state.deadline_utc) - datetime.now(timezone.utc)).total_seconds()
        if left <= 0:
            st.session_state.stage = "review"
            st.session_state.selected = None
            st.rerun()
        seconds = max(0, int(left + .999))
        remaining = min(100, max(0, left / 15 * 100))
        st.html(
            f'<div class="timer-label"><span>Pick a little extra</span><strong>{seconds}s</strong></div>'
            f'<div class="timer-track" role="progressbar" aria-label="Time remaining" '
            f'aria-valuemin="0" aria-valuemax="15" aria-valuenow="{seconds}">'
            f'<div class="timer-fill" style="--remaining:{remaining:.3f}%;--duration:{left:.3f}s;'
            f'animation-name:drain-{seconds}"></div></div>'
            f'<style>@keyframes drain-{seconds} {{ from {{ width:var(--remaining); }} to {{ width:0; }} }}</style>'
        )
        with st.container(key="offer-grid"):
            cols = st.columns(2)
            for col, suggestion in zip(cols, st.session_state.suggestions):
                with col:
                    item = suggestion.product
                    e = add_on_economics(book[(branch, item)]["price"], book[(branch, item)]["cost"])
                    price = f"~~\\${e['price']}~~  **\\${e['discounted_price']}**  ＋"
                    if product_card(item, price, key=f"choose-{item}"):
                        if datetime.now(timezone.utc) < datetime.fromisoformat(st.session_state.deadline_utc):
                            st.session_state.selected = item
                        else:
                            st.session_state.selected = None
                        st.session_state.stage = "review"
                        st.rerun()
        if st.button("Continue without add-on", key="skip-offer", use_container_width=True):
            st.session_state.selected = None
            st.session_state.stage = "review"
            st.rerun()

    offer_fragment()

elif stage == "review":
    seed, branch, selected = st.session_state.seed, st.session_state.branch, st.session_state.selected
    first = book[(branch, seed)]
    subtotal = money(first["price"])
    gp = money(first["price"] - first["cost"])
    st.html('<h1 class="page-heading">Your good little break.</h1>')
    basket_item(seed, subtotal, "Your pick")
    if selected:
        e = add_on_economics(book[(branch, selected)]["price"], book[(branch, selected)]["cost"])
        subtotal += e["discounted_price"]
        gp += e["discounted_gross_profit"]
        basket_item(selected, e["discounted_price"], "Your add-on · 15% off")
    st.html(f'<div class="receipt-total"><span>Total</span><strong>${subtotal}</strong></div>')
    if st.button("Confirm demo purchase", type="primary", use_container_width=True):
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
    st.button("Start over", key="start-over", on_click=reset)

else:
    st.html('<div class="success-mark" aria-hidden="true">✓</div>'
            '<h1 class="page-heading">A lovely choice.</h1>'
            '<p class="page-note">Demo purchase recorded.</p>')
    st.button("New order", key="new-order", on_click=reset)

st.html('<footer class="page-footer"><span>Stories Coffee · Demo checkout · No real payment</span>'
        '<a href="https://unsplash.com" target="_blank" rel="noopener noreferrer">Photography via Unsplash &amp; web sources</a></footer>')
