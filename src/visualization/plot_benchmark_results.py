#!/usr/bin/env python3
"""Create a bar chart from benchmark_flat_vs_normalized.py output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot MedCorp benchmark results."
    )
    parser.add_argument("results_json", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/figures/benchmark_comparison.png"),
    )
    args = parser.parse_args()

    try:
        import matplotlib.pyplot as plt
    except ImportError as error:
        parser.error(
            "This script requires matplotlib. Install it with: "
            "python -m pip install matplotlib"
        )

    if not args.results_json.exists():
        parser.error(f"Results file not found: {args.results_json}")

    with args.results_json.open("r", encoding="utf-8") as file:
        results = json.load(file)

    labels = ["Flat legacy", "Normalized"]
    memory = [
        results["memory_mb"]["flat"],
        results["memory_mb"]["normalized"],
    ]
    mutation = [
        results["mutation_ms"]["flat_median_ms"],
        results["mutation_ms"]["normalized_median_ms"],
    ]
    read_latency = [
        results["read_latency_ms"]["flat_median_ms"],
        results["read_latency_ms"]["normalized_median_ms"],
    ]

    figure, axes = plt.subplots(1, 3, figsize=(13, 4.5))

    charts = [
        (axes[0], memory, "Memory footprint", "MB"),
        (axes[1], mutation, "Doctor phone mutation", "Milliseconds"),
        (axes[2], read_latency, "1,000-patient read", "Milliseconds"),
    ]

    for axis, values, title, ylabel in charts:
        bars = axis.bar(labels, values, color=["#6baed6", "#2171b5"])
        axis.set_title(title)
        axis.set_ylabel(ylabel)
        axis.tick_params(axis="x", rotation=20)
        axis.grid(axis="y", alpha=0.25)

        for bar, value in zip(bars, values):
            axis.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{value:.3f}",
                ha="center",
                va="bottom",
                fontsize=9,
            )

    figure.suptitle("MedCorp Flat versus BCNF-Oriented Structures")
    figure.tight_layout()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, dpi=200, bbox_inches="tight")
    print(f"Saved figure to: {args.output}")


if __name__ == "__main__":
    main()
