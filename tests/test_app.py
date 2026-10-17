"""Checkout regressions using isolated prices and a temporary order database.

The private transaction CSV is not needed for these UI and state tests.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.online_nn import OnlineNeuralRecommender
from src.product_images import _OTHER_PHOTOS, _PHOTOS, product_image_url


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def checkout(monkeypatch, tmp_path):
    products = OnlineNeuralRecommender.load(ROOT / "models" / "nn_recommender.npz").products
    prices = pd.DataFrame([
        {"Branch": branch, "Product": product, "Unit Price (USD)": price, "Unit Cost (USD)": 2.0}
        for branch, price in [("Garden", 10.0), ("Harbour", 12.0)]
        for product in products
    ])
    monkeypatch.setattr("src.data.load_lines", lambda _: prices)
    original_connect = sqlite3.connect
    database = tmp_path / "orders.sqlite3"

    def isolated_connect(path, *args, **kwargs):
        if Path(path).name == "demo_state.sqlite3":
            path = database
        return original_connect(path, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", isolated_connect)
    updates = []
    original_update = OnlineNeuralRecommender.update

    def track_update(self, basket):
        updates.append(basket.transaction_id)
        return original_update(self, basket)

    monkeypatch.setattr(OnlineNeuralRecommender, "update", track_update)
    st.cache_resource.clear()
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=15).run()
    assert not app.exception
    yield app, database, updates
    st.cache_resource.clear()


def choose_first(app):
    app.button(key="product-Americano").click().run()
    assert not app.exception
    assert app.session_state.stage == "offer"
    return app.session_state.suggestions[0].product


def confirm(app):
    next(button for button in app.button if button.label == "Confirm demo purchase").click().run()
    assert not app.exception
    assert app.session_state.stage == "done"


def test_image_menu_preserves_branch_selection_and_fifteen_second_offer(checkout):
    app, database, updates = checkout
    assert not app.selectbox
    assert len(app.button) == 45
    assert all("![" in button.label and "https://" in button.label for button in app.button)
    app.radio[0].set_value("Harbour").run()
    choose_first(app)
    assert app.session_state.branch == "Harbour"
    started = datetime.fromisoformat(app.session_state.started_utc)
    deadline = datetime.fromisoformat(app.session_state.deadline_utc)
    assert (deadline - started).total_seconds() == 15
    suggestions = app.session_state.suggestions
    assert len(suggestions) == 2
    assert len({suggestion.product for suggestion in suggestions}) == 2
    assert all(suggestion.product != "Americano" for suggestion in suggestions)
    assert sum(button.key.startswith("choose-") for button in app.button) == 2
    assert not updates
    with sqlite3.connect(database) as con:
        assert con.execute("SELECT COUNT(*) FROM completed_orders").fetchone()[0] == 0


def test_timed_add_on_preserves_discount_totals_and_exactly_once_update(checkout):
    app, database, updates = checkout
    selected = choose_first(app)
    app.button(key=f"choose-{selected}").click().run()
    assert not app.exception
    assert app.session_state.stage == "review"
    assert app.session_state.selected == selected
    assert not updates
    event_id = app.session_state.event_id
    confirm(app)
    with sqlite3.connect(database) as con:
        row = con.execute("SELECT seed, selected, discounted_price, revenue, gross_profit FROM completed_orders").fetchone()
    assert row == ("Americano", selected, 8.5, 18.5, 14.5)
    assert updates == [event_id]
    # A repeated confirmation of the same event must remain idempotent.
    app.session_state.stage = "review"
    app.run()
    confirm(app)
    assert updates == [event_id]
    with sqlite3.connect(database) as con:
        assert con.execute("SELECT COUNT(*) FROM completed_orders").fetchone()[0] == 1
    next(button for button in app.button if button.label == "New order").click().run()
    assert not app.exception
    assert "stage" not in app.session_state
    assert "event_id" not in app.session_state
    assert len(app.button) == 45


@pytest.mark.parametrize("expired", [False, True], ids=["skip", "expired-click"])
def test_skip_and_expired_click_keep_full_price_first_product(checkout, expired):
    app, database, _ = checkout
    selected = choose_first(app)
    if expired:
        app.session_state.deadline_utc = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        app.button(key=f"choose-{selected}").click().run()
    else:
        app.button(key="skip-offer").click().run()
    assert not app.exception
    assert app.session_state.stage == "review"
    assert app.session_state.selected is None
    confirm(app)
    with sqlite3.connect(database) as con:
        row = con.execute("SELECT selected, discounted_price, revenue, gross_profit FROM completed_orders").fetchone()
    assert row == (None, None, 10.0, 8.0)


def test_countdown_expiry_advances_without_a_selection(checkout):
    app, _, updates = checkout
    choose_first(app)
    app.session_state.deadline_utc = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    app.run()
    assert not app.exception
    assert app.session_state.stage == "review"
    assert app.session_state.selected is None
    assert not updates


def test_every_trained_product_has_an_explicit_internet_image():
    products = OnlineNeuralRecommender.load(ROOT / "models" / "nn_recommender.npz").products
    assert set(products) == set(_PHOTOS) | set(_OTHER_PHOTOS)
    assert all(product_image_url(product).startswith("https://") for product in products)
