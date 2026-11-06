"""Generate the label-efficiency and chemical-space figures.

The main figure reports original-space neighborhood measurements.  The UMAP
atlas is supplementary and is explicitly treated as visualization: projection
quality is reported in the source table, and no inference is based on apparent
two-dimensional separation.
"""

from __future__ import annotations

from pathlib import Path
import sys

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from paper.generate_figures import (
    BLUE, DARK, GOLD, GREEN, LIGHT, MID, PURPLE, RED, TEAL,
    apply_style, clean_axes, panel_label, save_figure,
)


RESULTS = ROOT / "results"
FIGURE_DATA = ROOT / "paper" / "figure_data"
MODEL_LABELS = {
    "ecfp4": "ECFP4",
    "rdkit2d": "RDKit2D",
    "chemberta_77m": "ChemBERTa-77M",
    "chemberta_zinc": "ChemBERTa-ZINC",
    "molformer_xl": "MoLFormer-XL",
    "unimol_v1": "Uni-Mol v1",
    "molclr_gin": "MolCLR GIN",
    "grover_base": "GROVER Base",
    "grover_large": "GROVER Large",
}
MODEL_ORDER = list(MODEL_LABELS)
TASK_ORDER = ["BBBP", "ClinTox", "BACE", "ESOL", "Lipophilicity", "CYP3A4"]
TASK_COLORS = {
    "BBBP": PURPLE,
    "BACE": TEAL,
    "ESOL": BLUE,
    "Lipophilicity": ORANGE if "ORANGE" in globals() else GOLD,
    "CYP3A4": RED,
}
MODEL_MARKERS = {
    "chemberta_77m": "o",
    "chemberta_zinc": "s",
    "molformer_xl": "^",
}


def source_tables():
    scarcity = pd.read_csv(RESULTS / "sample_efficiency_summary.csv")
    scarcity = scarcity[scarcity["variant"] == "canonical"].copy()
    modality = (scarcity.groupby(["modality", "fraction"], as_index=False)
                ["change_from_full"]
                .agg(n_cells="count", median_change="median",
                     q1_change=lambda x: x.quantile(0.25),
                     q3_change=lambda x: x.quantile(0.75)))

    augmentation = pd.read_csv(RESULTS / "smiles_augmentation_summary.csv")
    neighborhoods = pd.read_csv(RESULTS / "chemical_space_neighborhoods.csv")
    canonical = neighborhoods[
        (neighborhoods["variant"] == "canonical") &
        (neighborhoods["k"] == 10)]
    augmented = neighborhoods[
        (neighborhoods["variant"] == "smiles_mean10") &
        (neighborhoods["k"] == 10)]
    geometry = canonical.merge(
        augmented, on=["task", "model_id"],
        suffixes=("_canonical", "_augmented"), validate="one_to_one")
    for metric in ("endpoint_coherence", "ecfp_neighbor_recall",
                   "scaffold_coherence"):
        geometry[f"delta_{metric}"] = (
            geometry[f"{metric}_augmented"] -
            geometry[f"{metric}_canonical"])
    paired = augmentation.merge(
        geometry, on=["task", "model_id"], validate="many_to_one")
    paired["endpoint_type"] = np.where(
        paired["task_type_canonical"] == "regression",
        "Regression", "Classification")

    correlations = pd.read_csv(RESULTS / "chemical_space_correlations.csv")
    scarcity_rho = correlations[
        (correlations["analysis"] == "label_efficiency") &
        (correlations["fraction"] == 0.10) &
        (correlations["geometry_metric"] == "endpoint_coherence")].copy()

    FIGURE_DATA.mkdir(parents=True, exist_ok=True)
    modality.to_csv(
        FIGURE_DATA / "figure6_scarcity_by_modality.csv", index=False)
    paired.to_csv(
        FIGURE_DATA / "figure6_smiles_augmentation_geometry.csv", index=False)
    scarcity_rho.to_csv(
        FIGURE_DATA / "figure6_label_efficiency_correlations.csv", index=False)
    return scarcity, modality, paired, scarcity_rho


def make_main_figure():
    scarcity, modality, paired, scarcity_rho = source_tables()
    apply_style()
    fig, axes = plt.subplots(2, 2, figsize=(10.6, 7.5))
    ax_a, ax_b, ax_c, ax_d = axes.ravel()

    modality_style = {
        "molecule": (PURPLE, "Molecules"),
        "protein": (GREEN, "Proteins"),
        "genomics": (GOLD, "Genomics"),
    }
    x_values = np.array([10, 25, 50, 100])
    for modality_name, (color, label) in modality_style.items():
        rows = modality[modality["modality"] == modality_name].sort_values(
            "fraction")
        x = rows["fraction"].to_numpy() * 100
        y = rows["median_change"].to_numpy()
        ax_a.fill_between(
            x, rows["q1_change"], rows["q3_change"], color=color,
            alpha=0.14, linewidth=0)
        ax_a.plot(x, y, marker="o", color=color, label=label, zorder=3)
    ax_a.axhline(0, color=MID, linewidth=1.1)
    ax_a.set_xticks(x_values)
    ax_a.set_xlabel("Labeled training data (%)")
    ax_a.set_ylabel("Change from full-data score")
    ax_a.set_title("Performance under label scarcity")
    ax_a.legend(frameon=False, loc="lower right")
    clean_axes(ax_a, grid="y")
    panel_label(ax_a, "A", y=1.10)

    active = paired[paired["fraction"] == 0.10].copy()
    task_positions = {task: index for index, task in enumerate(TASK_ORDER)}
    model_offsets = {
        "chemberta_77m": -0.18,
        "chemberta_zinc": 0,
        "molformer_xl": 0.18,
    }
    type_colors = {"Classification": RED, "Regression": BLUE}
    for row in active.itertuples():
        x = task_positions[row.task] + model_offsets[row.model_id]
        ax_b.scatter(
            x, row.mean_change, s=50,
            marker=MODEL_MARKERS[row.model_id],
            facecolor=type_colors[row.endpoint_type], edgecolor="white",
            linewidth=0.7, zorder=3)
    ax_b.axhline(0, color=MID, linewidth=1.1)
    ax_b.set_xticks(range(len(TASK_ORDER)))
    ax_b.set_xticklabels(
        ["Lipo." if task == "Lipophilicity" else task for task in TASK_ORDER],
        rotation=28, ha="right")
    ax_b.set_ylabel("Score change with view averaging")
    ax_b.set_title("Randomized-SMILES effect at 10% labels")
    legend = [
        Line2D([0], [0], marker=marker, linestyle="none", color=DARK,
               markerfacecolor="white", label=MODEL_LABELS[model],
               markersize=7)
        for model, marker in MODEL_MARKERS.items()
    ]
    ax_b.legend(handles=legend, frameon=False, fontsize=9,
                loc="lower left")
    clean_axes(ax_b, grid="y")
    panel_label(ax_b, "B", y=1.10)

    for endpoint_type, group in active.groupby("endpoint_type"):
        ax_c.scatter(
            group["delta_endpoint_coherence"], group["mean_change"],
            s=60, color=type_colors[endpoint_type], alpha=0.9,
            edgecolor="white", linewidth=0.7, label=endpoint_type, zorder=3)
    ax_c.axhline(0, color=MID, linewidth=1.0)
    ax_c.axvline(0, color=MID, linewidth=1.0)
    rho = active[["delta_endpoint_coherence", "mean_change"]].corr(
        method="spearman").iloc[0, 1]
    classification_rho = active[
        active["endpoint_type"] == "Classification"
    ][["delta_endpoint_coherence", "mean_change"]].corr(
        method="spearman").iloc[0, 1]
    ax_c.text(
        0.04, 0.95,
        f"All: ρ = {rho:.2f}\nClassification: ρ = {classification_rho:.2f}",
        transform=ax_c.transAxes,
        va="top", color=DARK, fontweight="bold")
    ax_c.set_xlabel("Change in endpoint-neighborhood coherence")
    ax_c.set_ylabel("Change in predictive score")
    ax_c.set_title("Geometry tracks the augmentation response")
    ax_c.legend(frameon=False, loc="lower right")
    clean_axes(ax_c, grid="both")
    panel_label(ax_c, "C", y=1.10)

    scarcity_rho["task_order"] = scarcity_rho["task"].map(
        {task: index for index, task in enumerate(TASK_ORDER)})
    scarcity_rho = scarcity_rho.sort_values("task_order")
    colors = [BLUE if task in ("ESOL", "Lipophilicity") else RED
              for task in scarcity_rho["task"]]
    bars = ax_d.bar(
        np.arange(len(scarcity_rho)), scarcity_rho["spearman_rho"],
        color=colors, edgecolor="white", linewidth=0.8, width=0.72)
    ax_d.axhline(0, color=MID, linewidth=1.0)
    ax_d.set_xticks(np.arange(len(scarcity_rho)))
    ax_d.set_xticklabels(
        ["Lipo." if task == "Lipophilicity" else task
         for task in scarcity_rho["task"]], rotation=28, ha="right")
    ax_d.set_ylim(-0.1, 1.0)
    ax_d.set_ylabel("Spearman ρ across representations")
    ax_d.set_title("Endpoint coherence versus 10% performance")
    for bar, value in zip(bars, scarcity_rho["spearman_rho"]):
        ax_d.text(
            bar.get_x() + bar.get_width() / 2, value + 0.035,
            f"{value:.2f}", ha="center", va="bottom", fontsize=9,
            fontweight="bold", color=DARK)
    clean_axes(ax_d, grid="y")
    panel_label(ax_d, "D", y=1.10)

    fig.subplots_adjust(left=0.09, right=0.98, bottom=0.10, top=0.94,
                        wspace=0.32, hspace=0.42)
    save_figure(fig, "figure6_label_efficiency_and_chemical_space")


def make_atlas():
    apply_style()
    coordinates = pd.read_csv(
        RESULTS / "chemical_space_map_coordinates.csv.gz")
    mapping = pd.read_csv(RESULTS / "chemical_space_mapping_summary.csv")
    mapping.to_csv(
        FIGURE_DATA / "figureS2_chemical_space_mapping_summary.csv",
        index=False)
    coordinates.to_csv(
        FIGURE_DATA / "figureS2_chemical_space_coordinates.csv.gz",
        index=False, compression="gzip")

    colors = {
        "BBBP": PURPLE,
        "BACE": TEAL,
        "ESOL": BLUE,
        "Lipophilicity": GOLD,
        "CYP3A4": RED,
    }
    fig, axes = plt.subplots(3, 3, figsize=(10.4, 9.3))
    for panel_index, (ax, model_id) in enumerate(
            zip(axes.ravel(), MODEL_ORDER)):
        panel = coordinates[coordinates["model_id"] == model_id]
        for task in colors:
            points = panel[panel["task"] == task]
            ax.scatter(
                points["umap_1"], points["umap_2"], s=6,
                color=colors[task], alpha=0.60, linewidth=0,
                rasterized=True)
        ax.set_title(MODEL_LABELS[model_id], fontsize=12.2,
                     fontweight="bold")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color(LIGHT)
            spine.set_linewidth(0.9)
        panel_label(ax, chr(ord("A") + panel_index), y=1.08)
    handles = [
        Line2D([0], [0], marker="o", linestyle="none", color=color,
               label=("Lipophilicity" if task == "Lipophilicity" else task),
               markersize=7)
        for task, color in colors.items()
    ]
    fig.legend(handles=handles, loc="lower center", ncol=5,
               frameon=False, bbox_to_anchor=(0.5, 0.012))
    fig.text(0.5, 0.045, "UMAP 1", ha="center", fontweight="bold",
             color=DARK)
    fig.text(0.018, 0.52, "UMAP 2", va="center", rotation="vertical",
             fontweight="bold", color=DARK)
    fig.subplots_adjust(left=0.06, right=0.99, bottom=0.085, top=0.97,
                        wspace=0.12, hspace=0.18)
    save_figure(fig, "figureS2_chemical_space_atlas")


if __name__ == "__main__":
    make_main_figure()
    make_atlas()
