"""Chronological neural-model selection and final six-month refit."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .data import Basket
from .evaluate import evaluate_model
from .online_nn import OnlineNeuralRecommender, basket_examples


def split_baskets(baskets: list[Basket]):
    train = [b for b in baskets if b.timestamp.date() < date(2026, 4, 1)]
    validation = [b for b in baskets if date(2026, 4, 1) <= b.timestamp.date() < date(2026, 5, 1)]
    test = [b for b in baskets if b.timestamp.date() >= date(2026, 5, 1)]
    assert len(train) + len(validation) + len(test) == len(baskets)
    return train, validation, test


def train_and_select(baskets: list[Basket], categories: dict[str, str],
                     figures: Path, artifact: Path) -> dict:
    train, validation, test = split_baskets(baskets)
    vocabulary = sorted({p for basket in train for p in basket.products})
    candidates = []
    trained = []
    for hidden in [16, 32]:
        model = OnlineNeuralRecommender(vocabulary, hidden=hidden, seed=490)
        history = model.fit(train, validation, epochs=40, learning_rate=.01,
                            batch_size=512, weight_decay=.0001, patience=6, seed=490)
        val_metrics = evaluate_model(model, validation, categories)
        candidates.append({"hidden_units": hidden, "best_epoch": model.best_epoch,
                           "epochs_run": len(history), "validation_loss": min(x["validation_loss"] for x in history),
                           "validation_metrics": val_metrics, "history": history})
        trained.append(model)
    # Validation chooses architecture. Test is read once after selection.
    selected_idx = max(range(len(candidates)), key=lambda i:
                       (candidates[i]["validation_metrics"]["hit_at_2"],
                        -candidates[i]["validation_loss"], -candidates[i]["hidden_units"]))
    selected = trained[selected_idx]
    test_metrics = evaluate_model(selected, test, categories)
    selected_info = candidates[selected_idx]

    fig, ax = plt.subplots(figsize=(9, 3.8))
    for candidate in candidates:
        h = candidate["hidden_units"]
        ax.plot([e["epoch"] for e in candidate["history"]],
                [e["validation_loss"] for e in candidate["history"]],
                label=f"{h} hidden - validation", linewidth=2)
        ax.plot([e["epoch"] for e in candidate["history"]],
                [e["train_loss"] for e in candidate["history"]],
                label=f"{h} hidden - training", linestyle="--", linewidth=1)
    ax.set(xlabel="Epoch", ylabel="Weighted cross-entropy", title="Neural training and validation loss")
    ax.legend(frameon=False, fontsize=8)
    fig.savefig(figures / "08_neural_training.png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    # After test reporting, train a fresh deployable model on all six months
    # for the preselected number of epochs. This model has no untouched test.
    deployed = OnlineNeuralRecommender(sorted({p for b in baskets for p in b.products}),
                                        hidden=selected_info["hidden_units"], seed=490)
    deployed.fit(baskets, None, epochs=selected_info["best_epoch"], learning_rate=.01,
                 batch_size=512, weight_decay=.0001, patience=selected_info["best_epoch"], seed=490)
    deployed.save(artifact)
    train_examples = basket_examples(train, selected.index)
    val_examples = basket_examples(validation, selected.index)
    test_examples = basket_examples(test, selected.index)
    return {
        "architecture": f"{len(selected.products)} one-hot inputs -> {selected_info['hidden_units']} tanh hidden units -> {len(selected.products)} softmax outputs",
        "input_fields": ["Product"], "output": "Two highest-scoring distinct other products",
        "loss": "Transaction-weighted categorical cross-entropy over co-purchased products",
        "optimizer": "Adam for initial training; SGD for each completed online order",
        "hyperparameters": {"learning_rate": .01, "batch_size": 512, "weight_decay": .0001,
                            "max_epochs": 40, "patience": 6, "random_seed": 490,
                            "online_learning_rate": selected.online_learning_rate},
        "split": {"train": "2026-01-01 to 2026-03-31", "validation": "2026-04-01 to 2026-04-30",
                  "test": "2026-05-01 to 2026-06-30",
                  "train_transactions": len(train), "validation_transactions": len(validation),
                  "test_transactions": len(test),
                  "train_multi_product_transactions": train_examples[3],
                  "validation_multi_product_transactions": val_examples[3],
                  "test_multi_product_transactions": test_examples[3]},
        "candidates": candidates,
        "selected_hidden_units": selected_info["hidden_units"],
        "selected_epoch": selected_info["best_epoch"],
        "test_metrics": test_metrics,
        "deployed_retrained_on_all_six_months": True,
        "model_artifact": str(artifact.name),
    }
