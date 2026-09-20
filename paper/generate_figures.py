"""Generate publication figures and their source-data tables from release JSON.

The visual style follows the conventions commonly used in GraphPad Prism:
white backgrounds, restrained colour, visible individual estimates, exact
numeric labels, outward ticks, and no decorative effects.  Both vector SVG and
300-dpi PNG outputs are produced.  No value is manually transcribed.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch
from matplotlib.ticker import MaxNLocator, PercentFormatter


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "results"
FIGURE_DIR = ROOT / "paper" / "figures"
DATA_DIR = ROOT / "paper" / "figure_data"

TASK_ORDER = [
    "BBBP", "ClinTox", "BACE", "ESOL", "Lipophilicity", "CYP3A4",
    "DeepLoc", "Fluorescence", "Promoters",
]
MOLECULE_TASKS = TASK_ORDER[:6]
PROTEIN_GENOMIC_TASKS = TASK_ORDER[6:]
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
    "kmer3_protein": "3-mer frequency",
    "esm2_8m": "ESM-2 8M",
    "esm2_35m": "ESM-2 35M",
    "esm2_150m": "ESM-2 150M",
    "esm2_650m": "ESM-2 650M",
    "protbert": "ProtBERT",
    "kmer5_dna": "5-mer frequency",
    "nucleotide_transformer": "Nucleotide Transformer 500M",
    "hyenadna": "HyenaDNA-tiny",
}
MODEL_ORDER = {
    "molecule": [
        "ecfp4", "rdkit2d", "chemberta_77m", "chemberta_zinc",
        "molformer_xl", "unimol_v1", "molclr_gin", "grover_base",
        "grover_large",
    ],
    "protein": [
        "kmer3_protein", "esm2_8m", "esm2_35m", "esm2_150m",
        "esm2_650m", "protbert",
    ],
    "genomics": ["kmer5_dna", "nucleotide_transformer", "hyenadna"],
}

PURPLE = "#6F4BF2"
TEAL = "#168C78"
BLUE = "#2F6DB2"
ORANGE = "#D97706"
RED = "#C24156"
GOLD = "#D4A017"
GREEN = "#2F855A"
DARK = "#172033"
MID = "#657189"
LIGHT = "#DCE2EC"
PALE = "#F5F7FB"


def load_json(name: str):
    return json.loads((RESULTS_DIR / name).read_text())


def apply_style():
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "font.weight": "normal",
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlepad": 8,
        "axes.labelsize": 12.5,
        "axes.labelweight": "bold",
        "axes.labelcolor": DARK,
        "axes.edgecolor": DARK,
        "axes.linewidth": 1.25,
        "xtick.labelsize": 10.8,
        "ytick.labelsize": 10.8,
        "xtick.color": DARK,
        "ytick.color": DARK,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.size": 4.5,
        "ytick.major.size": 4.5,
        "xtick.major.width": 1.15,
        "ytick.major.width": 1.15,
        "legend.fontsize": 10.8,
        "legend.title_fontsize": 11,
        "lines.linewidth": 2.2,
        "lines.markersize": 7,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "svg.fonttype": "none",
    })


def clean_axes(ax, grid="x"):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(1.25)
    ax.spines["bottom"].set_linewidth(1.25)
    if grid:
        ax.grid(axis=grid, color="#E7EBF2", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for label in [*ax.get_xticklabels(), *ax.get_yticklabels()]:
        label.set_fontweight("bold")


def panel_label(ax, label, y=1.08):
    ax.text(-0.22, y, label, transform=ax.transAxes, fontsize=15.5,
            fontweight="bold", color=DARK, va="top")


def save_figure(fig, stem):
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    png_path = FIGURE_DIR / f"{stem}.png"
    svg_path = FIGURE_DIR / f"{stem}.svg"
    fig.savefig(png_path, dpi=300, bbox_inches="tight",
                pad_inches=0.08)
    fig.savefig(svg_path, bbox_inches="tight", pad_inches=0.08)
    # Matplotlib writes inconsequential spaces at the ends of SVG path lines.
    # Normalising them keeps generated assets clean under ``git diff --check``.
    svg_path.write_text("\n".join(
        line.rstrip() for line in svg_path.read_text().splitlines()
    ) + "\n")
    plt.close(fig)


def write_csv(name, rows, fieldnames):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (DATA_DIR / name).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def make_scope_figure(results, paired):
    modalities = [
        ("Molecules", "molecule", 6, "Murcko-scaffold splits", "#EFEAFF", PURPLE),
        ("Proteins", "protein", 2, "Published sequence splits", "#E8F7F1", GREEN),
        ("Genomics", "genomics", 1, "Published chromosome split", "#FFF6DC", GOLD),
    ]
    rows = []
    for label, modality, tasks, split, _, _ in modalities:
        task_ids = [task for task in TASK_ORDER
                    if results[task]["modality"] == modality]
        models = {model for task in task_ids for model in results[task]["models"]}
        cells = sum(len(results[task]["models"]) for task in task_ids)
        comparisons = [comparison for task in task_ids
                       for comparison in paired[task]["comparisons"].values()
                       if comparison.get("inferential", True)]
        resolved = sum(bool(item.get("significant_global", item["significant"]))
                       for item in comparisons)
        rows.append({
            "modality": label,
            "tasks": tasks,
            "representations": len(models),
            "measured_cells": cells,
            "resolved_comparisons": resolved,
            "total_comparisons": len(comparisons),
            "split_policy": split,
        })
    write_csv("figure1_benchmark_scope.csv", rows, list(rows[0]))

    overall_tasks = sum(row["tasks"] for row in rows)
    overall_representations = sum(row["representations"] for row in rows)
    overall_cells = sum(row["measured_cells"] for row in rows)
    overall_resolved = sum(row["resolved_comparisons"] for row in rows)
    overall_comparisons = sum(row["total_comparisons"] for row in rows)

    # Figure 1 is maintained as native, editable Draw.io artwork.  Keep the
    # data table generated above, verify that the artwork contains the current
    # release totals, and preserve its publication exports on regeneration.
    drawio_path = FIGURE_DIR / "figure1_study_design.drawio"
    if drawio_path.exists():
        exports = [
            FIGURE_DIR / "figure1_study_design.png",
            FIGURE_DIR / "figure1_study_design.svg",
        ]
        missing_exports = [path.name for path in exports if not path.exists()]
        if missing_exports:
            raise FileNotFoundError(
                "Export the Draw.io Figure 1 source before generating the "
                f"manuscript; missing: {', '.join(missing_exports)}"
            )

        cell_values = {
            cell.attrib.get("value", "")
            for cell in ElementTree.parse(drawio_path).iter("mxCell")
        }
        expected_values = {
            *(f"{row['tasks']} {'task' if row['tasks'] == 1 else 'tasks'} · "
              f"{row['representations']} representations" for row in rows),
            *(f"{row['measured_cells']} evaluations" for row in rows),
            str(overall_tasks),
            str(overall_representations),
            str(overall_cells),
            f"{overall_resolved}/{overall_comparisons}",
        }
        missing_values = sorted(expected_values - cell_values)
        if missing_values:
            raise ValueError(
                "Draw.io Figure 1 is out of sync with the benchmark results; "
                f"missing labels: {', '.join(missing_values)}"
            )
        # Regenerate the publication exports below from the same data. The
        # Draw.io source remains editable and is checked for matching totals.

    fig, ax = plt.subplots(figsize=(7.2, 5.4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.02, 0.97, "BioLatent measured benchmark", fontsize=16,
            fontweight="bold", color=DARK, va="top")
    ax.text(0.02, 0.915,
            "Real datasets · fixed representations · standardised prediction · paired statistics",
            fontsize=9.2, color=MID, va="top")

    x_positions = [0.02, 0.345, 0.67]
    for x, row, (_, _, _, _, fill, colour) in zip(x_positions, rows, modalities):
        box = FancyBboxPatch((x, 0.66), 0.305, 0.20,
                             boxstyle="round,pad=0.012,rounding_size=0.018",
                             linewidth=1.2, edgecolor=colour, facecolor=fill)
        ax.add_patch(box)
        ax.text(x + 0.018, 0.825, row["modality"], fontsize=11,
                fontweight="bold", color=colour)
        ax.text(x + 0.018, 0.775,
                f"{row['tasks']} tasks  ·  {row['representations']} representations",
                fontsize=8.5, color=DARK)
        ax.text(x + 0.018, 0.735,
                f"{row['measured_cells']} evaluations",
                fontsize=9, fontweight="bold", color=DARK)
        ax.text(x + 0.018, 0.695, row["split_policy"], fontsize=7.7, color=MID)

    pipeline = [
        ("1", "Calculate once", "Verified inputs;\nfixed model version"),
        ("2", "Select comparison", "Validation data;\nsame procedure"),
        ("3", "Score test set", "Predictions and\nendpoint measure"),
        ("4", "Quantify uncertainty", "Bootstrap and\nadjusted tests"),
    ]
    px = [0.02, 0.27, 0.52, 0.77]
    for i, (num, title, subtitle) in enumerate(pipeline):
        box = FancyBboxPatch((px[i], 0.34), 0.205, 0.20,
                             boxstyle="round,pad=0.012,rounding_size=0.015",
                             linewidth=1.0, edgecolor="#AAB3C3", facecolor="white")
        ax.add_patch(box)
        ax.text(px[i] + 0.018, 0.495, num, fontsize=9, color="white",
                fontweight="bold", ha="center", va="center",
                bbox=dict(boxstyle="circle,pad=0.25", facecolor=PURPLE,
                          edgecolor=PURPLE))
        ax.text(px[i] + 0.052, 0.49, title, fontsize=7.2,
                fontweight="bold", color=DARK, va="center")
        ax.text(px[i] + 0.018, 0.425, subtitle, fontsize=7.7,
                color=MID, va="center", linespacing=1.35)
        if i < len(pipeline) - 1:
            ax.add_patch(FancyArrowPatch((px[i] + 0.21, 0.44),
                                         (px[i + 1] - 0.01, 0.44),
                                         arrowstyle="-|>", mutation_scale=10,
                                         linewidth=1.0, color="#8C96A8"))

    ax.text(0.02, 0.265, "Validated release", fontsize=9.5,
            fontweight="bold", color=DARK)
    summary = [
        ("9", "real-data tasks"),
        (str(overall_representations), "representations"),
        (str(overall_cells), "model–dataset\nevaluations"),
        (f"{overall_resolved}/{overall_comparisons}", "statistically distinguishable\ncomparisons"),
    ]
    for i, (value, label) in enumerate(summary):
        x = 0.02 + i * 0.245
        ax.text(x, 0.19, value, fontsize=17, fontweight="bold", color=PURPLE)
        ax.text(x, 0.145, label, fontsize=7.6, color=MID, va="top", linespacing=1.2)
    ax.text(0.02, 0.07,
            "Distinguishable = study-wide adjusted p < 0.05 for eligible formal comparisons; Fluorescence is descriptive.",
            fontsize=7.8, color=MID)
    save_figure(fig, "figure1_study_design")


def score_rows(results, paired, tasks, model_order):
    rows = []
    for task in tasks:
        task_result = results[task]
        comparison = paired[task]
        for model in model_order:
            cell = task_result["models"].get(model)
            inference = comparison["comparisons"].get(model)
            rows.append({
                "task": task,
                "modality": task_result["modality"],
                "model_id": model,
                "representation": MODEL_LABELS[model],
                "metric": (cell["linear"]["metric"] if cell else "N/A"),
                "score": (cell["linear"]["score"] if cell else ""),
                "ci_low": (cell["linear"].get("ci_low", "") if cell else ""),
                "ci_high": (cell["linear"].get("ci_high", "") if cell else ""),
                "n_test": task_result["n_test"],
                "validation_reference": model == comparison["reference"],
                "numerical_test_best": model == comparison["observed_test_best"],
                "inference_status": comparison.get("inference_status", "primary"),
                "significant_global": bool(
                    inference and inference.get("inferential", True)
                    and inference.get("significant_global", inference["significant"])
                ),
                "p_holm_global": ((inference.get("p_holm_global", inference["p_holm"])
                                   if inference else "") or ""),
            })
    return rows


def plot_task_scores(ax, task, results, paired, order):
    task_result = results[task]
    pair = paired[task]
    y = np.arange(len(order))
    available = []
    for yi, model in zip(y, order):
        cell = task_result["models"].get(model)
        if cell is None:
            continue
        linear = cell["linear"]
        available.append((yi, model, linear))
    lows = [item[2].get("ci_low", item[2]["score"]) for item in available]
    highs = [item[2].get("ci_high", item[2]["score"]) for item in available]
    span = max(max(highs) - min(lows), 0.03)
    xmin = max(-1.0, min(lows) - 0.10 * span)
    xmax = min(1.12, max(highs) + 0.50 * span)
    if xmax - xmin < 0.08:
        xmax = min(1.12, xmin + 0.08)
    ref_score = pair["reference_test_score"]
    ax.axvline(ref_score, color=PURPLE, linewidth=1.5, linestyle=(0, (3, 2)),
               alpha=0.58, zorder=1)
    for yi, model in zip(y, order):
        cell = task_result["models"].get(model)
        if cell is None:
            ax.text(xmin + 0.02 * (xmax - xmin), yi, "N/A", color=MID,
                    fontsize=10, fontweight="bold", va="center")
            continue
        linear = cell["linear"]
        score = linear["score"]
        low = linear.get("ci_low", score)
        high = linear.get("ci_high", score)
        is_ref = model == pair["reference"]
        is_best = model == pair["observed_test_best"]
        comp = pair["comparisons"].get(model)
        sig = bool(comp and comp.get("inferential", True)
                   and comp.get("significant_global", comp["significant"]))
        if is_ref and is_best:
            marker, face, edge = "D", TEAL, PURPLE
        elif is_ref:
            marker, face, edge = "D", PURPLE, PURPLE
        elif is_best:
            marker, face, edge = "s", TEAL, TEAL
        else:
            marker, face, edge = "o", BLUE, RED if sig else BLUE
        ax.errorbar(score, yi, xerr=[[score - low], [high - score]], fmt=marker,
                    markersize=7.2, markerfacecolor=face, markeredgecolor=edge,
                    markeredgewidth=1.7 if sig else 1.1, ecolor="#718096",
                    elinewidth=1.5, capsize=3.2, capthick=1.35, zorder=3)
        label = f"{score:.3f}{'*' if sig else ''}"
        ax.text(high + 0.025 * (xmax - xmin), yi, label, fontsize=9.8,
                fontweight="bold", va="center",
                color=RED if sig else DARK)
    ax.set_xlim(xmin, xmax)
    ax.set_yticks(y, [MODEL_LABELS[model] for model in order])
    ax.invert_yaxis()
    metric = next(iter(task_result["models"].values()))["linear"]["metric"]
    inference_label = (" · descriptive only"
                       if pair.get("inference_status") == "descriptive_only" else "")
    ax.set_title(
        f"{task}{inference_label}\n{metric}\nTest set: n = {task_result['n_test']:,}",
        pad=5, linespacing=1.05,
    )
    ax.set_xlabel(metric)
    ax.xaxis.set_major_locator(MaxNLocator(4))
    clean_axes(ax)


def score_legend(fig, y=0.01):
    handles = [
        Line2D([0], [0], marker="D", color="none", markerfacecolor=PURPLE,
               markeredgecolor=PURPLE, markersize=7.5,
               label="Preselected comparison"),
        Line2D([0], [0], marker="s", color="none", markerfacecolor=TEAL,
               markeredgecolor=TEAL, markersize=7.5, label="Highest observed score"),
        Line2D([0], [0], marker="o", color="#718096", linewidth=1.7,
               markerfacecolor=BLUE, markeredgecolor=BLUE, markersize=6.5,
               label="Estimate and 95% CI"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor="white",
               markeredgecolor=RED, markeredgewidth=1.6, markersize=7.5,
               label="* adjusted p < 0.05 vs comparison"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=2, frameon=False,
               bbox_to_anchor=(0.5, y), columnspacing=1.6, handletextpad=0.7,
               prop={"size": 10.5, "weight": "bold"})


def make_score_figures(results, paired):
    molecule_rows = score_rows(results, paired, MOLECULE_TASKS,
                               MODEL_ORDER["molecule"])
    write_csv("figure2_molecular_scores.csv", molecule_rows,
              list(molecule_rows[0]))
    fig, axes = plt.subplots(3, 2, figsize=(7.4, 10.8))
    for idx, (ax, task) in enumerate(zip(axes.flat, MOLECULE_TASKS)):
        plot_task_scores(ax, task, results, paired, MODEL_ORDER["molecule"])
        panel_label(ax, chr(65 + idx), y=1.20)
    score_legend(fig, y=0.002)
    fig.suptitle("Molecular property-prediction performance", fontsize=17,
                 fontweight="bold", color=DARK, y=0.995)
    fig.tight_layout(rect=(0, 0.07, 1, 0.97), h_pad=1.45, w_pad=1.9)
    save_figure(fig, "figure2_molecular_performance")

    other_order = MODEL_ORDER["protein"] + MODEL_ORDER["genomics"]
    other_rows = []
    for task in PROTEIN_GENOMIC_TASKS:
        order = MODEL_ORDER[results[task]["modality"]]
        other_rows.extend(score_rows(results, paired, [task], order))
    write_csv("figure3_protein_genomic_scores.csv", other_rows,
              list(other_rows[0]))
    fig, axes = plt.subplots(3, 1, figsize=(7.4, 9.8))
    for idx, (ax, task) in enumerate(zip(axes, PROTEIN_GENOMIC_TASKS)):
        plot_task_scores(ax, task, results, paired,
                         MODEL_ORDER[results[task]["modality"]])
        panel_label(ax, chr(65 + idx), y=1.20)
    score_legend(fig, y=0.002)
    fig.suptitle("Protein and genomic extension", fontsize=17,
                 fontweight="bold", color=DARK, y=0.995)
    fig.tight_layout(rect=(0, 0.08, 1, 0.965), h_pad=2.5)
    save_figure(fig, "figure3_protein_genomic_performance")


def make_inference_sensitivity_figure(results, paired, sensitivity):
    modality_color = {"molecule": PURPLE, "protein": GREEN, "genomics": GOLD}
    summary_rows = []
    for task in TASK_ORDER:
        entry = paired[task]
        comparisons = [item for item in entry["comparisons"].values()
                       if item.get("inferential", True)]
        resolved = sum(bool(item.get("significant_global", item["significant"]))
                       for item in comparisons)
        split_entry = sensitivity["tasks"].get(task)
        if split_entry:
            winners = [run["order"][0] for run in split_entry["runs"]]
            common, frequency = Counter(winners).most_common(1)[0]
            max_model, max_values = max(
                split_entry["models"].items(), key=lambda item: item[1]["range"]
            )
            max_range = max_values["range"]
        else:
            common, frequency, max_model, max_range = "", "", "", ""
        summary_rows.append({
            "task": task,
            "modality": results[task]["modality"],
            "resolved": resolved,
            "unresolved": len(comparisons) - resolved,
            "total": len(comparisons),
            "inference_status": entry.get("inference_status", "primary"),
            "validation_reference": MODEL_LABELS[entry["reference"]],
            "numerical_test_best": MODEL_LABELS[entry["observed_test_best"]],
            "reference_differs_from_test_best": entry["reference"] != entry["observed_test_best"],
            "most_frequent_split_winner": MODEL_LABELS.get(common, ""),
            "split_winner_frequency": frequency,
            "maximum_score_range": max_range,
            "maximum_range_model": MODEL_LABELS.get(max_model, ""),
        })
    write_csv("figure4_inference_sensitivity_summary.csv", summary_rows,
              list(summary_rows[0]))
    run_rows = []
    for task, entry in sensitivity["tasks"].items():
        for run in entry["runs"]:
            for rank, model in enumerate(run["order"], start=1):
                run_rows.append({
                    "task": task, "seed": run["seed"], "rank": rank,
                    "model_id": model, "representation": MODEL_LABELS[model],
                    "score": run["scores"][model],
                })
    write_csv("figure4_split_seed_source_data.csv", run_rows, list(run_rows[0]))

    fig, axes = plt.subplots(
        3, 1, figsize=(7.4, 10.7),
        gridspec_kw={"height_ratios": [1.28, 1.0, 1.0]},
    )
    tasks = TASK_ORDER[::-1]
    y = np.arange(len(tasks))
    row_by_task = {row["task"]: row for row in summary_rows}

    ax = axes[0]
    resolved = [row_by_task[t]["resolved"] for t in tasks]
    unresolved = [row_by_task[t]["unresolved"] for t in tasks]
    colours = [modality_color[row_by_task[t]["modality"]] for t in tasks]
    ax.barh(y, resolved, color=colours, edgecolor="white", linewidth=0.55,
            height=0.68,
            label="Resolved")
    ax.barh(y, unresolved, left=resolved, color=LIGHT, edgecolor="white",
            linewidth=0.55, height=0.68, label="Unresolved")
    for yi, task, r, u in zip(y, tasks, resolved, unresolved):
        label = ("descriptive" if row_by_task[task]["inference_status"] == "descriptive_only"
                 else f"{r}/{r + u}")
        ax.text(r + u + 0.15, yi, label, va="center",
                fontsize=10.2, fontweight="bold", color=DARK)
    ax.set_yticks(y, tasks)
    ax.set_xlabel("Eligible formal comparisons")
    ax.set_title("Statistically distinguishable eligible comparisons")
    handles = [
        Patch(facecolor=PURPLE, label="Molecules: distinguishable"),
        Patch(facecolor=GREEN, label="Proteins: distinguishable"),
        Patch(facecolor=GOLD, label="Genomics: distinguishable"),
        Patch(facecolor=LIGHT, label="Not distinguishable"),
    ]
    ax.legend(handles=handles, frameon=False, loc="upper center", ncol=2,
              bbox_to_anchor=(0.5, -0.17),
              prop={"size": 10.0, "weight": "bold"},
              columnspacing=1.3, handletextpad=0.6)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    clean_axes(ax)
    panel_label(ax, "A")

    ax = axes[1]
    n_splits = len(sensitivity["seeds"])
    mol_tasks = MOLECULE_TASKS[::-1]
    y2 = np.arange(len(mol_tasks))
    freq = [row_by_task[t]["split_winner_frequency"] for t in mol_tasks]
    same = [row_by_task[t]["most_frequent_split_winner"] ==
            row_by_task[t]["numerical_test_best"] for t in mol_tasks]
    ax.barh(y2, freq, color=[TEAL if item else ORANGE for item in same],
            edgecolor="white", linewidth=0.55, height=0.62)
    for yi, task, count in zip(y2, mol_tasks, freq):
        row = row_by_task[task]
        ax.text(count + 0.08, yi,
                f"{row['most_frequent_split_winner']}  ({count}/{n_splits})",
                va="center", fontsize=10.0, fontweight="bold", color=DARK)
    ax.set_xlim(0, n_splits * 1.38)
    ax.set_yticks(y2, mol_tasks)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=6))
    ax.set_xlabel(f"Scaffold partitions led (of {n_splits})")
    ax.set_title("Consistency of the leading representation across scaffold partitions")
    handles = [
        Line2D([0], [0], color=TEAL, lw=6, label="Matches primary-partition leader"),
        Line2D([0], [0], color=ORANGE, lw=6, label="Different from primary-partition leader"),
    ]
    ax.legend(handles=handles, frameon=False, loc="upper center", ncol=2,
              bbox_to_anchor=(0.5, -0.24),
              prop={"size": 9.8, "weight": "bold"},
              columnspacing=1.3, handletextpad=0.6)
    clean_axes(ax)
    panel_label(ax, "B")

    ax = axes[2]
    ranges = [row_by_task[t]["maximum_score_range"] for t in mol_tasks]
    ax.barh(y2, ranges, color=BLUE, edgecolor="white", linewidth=0.55,
            height=0.62)
    for yi, task, value in zip(y2, mol_tasks, ranges):
        row = row_by_task[task]
        ax.text(value + 0.006, yi,
                f"{value:.3f}  ({row['maximum_range_model']})",
                va="center", fontsize=10.0, fontweight="bold", color=DARK)
    ax.set_xlim(0, max(ranges) * 1.75)
    ax.set_yticks(y2, mol_tasks)
    ax.set_xlabel(f"Maximum score range across {n_splits} seeds")
    ax.set_title("Largest observed split sensitivity within each task")
    clean_axes(ax)
    panel_label(ax, "C")
    fig.suptitle("Statistical comparisons and scaffold-partition sensitivity",
                 fontsize=17, fontweight="bold", color=DARK, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.97), h_pad=2.8)
    save_figure(fig, "figure4_inference_and_split_sensitivity")


def make_resolution_figure(results, resolution):
    rows = []
    aggregate = defaultdict(lambda: defaultdict(list))
    for task, task_entry in resolution["tasks"].items():
        for model, comparison in task_entry["comparisons"].items():
            for point in comparison["curve"]:
                row = {
                    "task": task,
                    "modality": results[task]["modality"],
                    "comparison_model_id": model,
                    "comparison_representation": MODEL_LABELS[model],
                    **point,
                }
                rows.append(row)
                aggregate[task][point["requested_n"]].append(point)
    write_csv("figure5_resolution_curve_source_data.csv", rows, list(rows[0]))
    aggregate_rows = []
    for task, by_n in aggregate.items():
        for requested_n, points in sorted(by_n.items()):
            aggregate_rows.append({
                "task": task,
                "modality": results[task]["modality"],
                "requested_n": requested_n,
                "median_effective_n": float(np.median(
                    [point["median_effective_n"] for point in points])),
                "median_central_95_width": float(np.median(
                    [point["central_95_width"] for point in points])),
                "n_comparisons": len(points),
            })
    write_csv("figure5_resolution_curve_summary.csv", aggregate_rows,
              list(aggregate_rows[0]))

    task_colours = [PURPLE, TEAL, BLUE, ORANGE, RED, GOLD]
    fig, axes = plt.subplots(3, 1, figsize=(7.4, 9.7))
    groups = [MOLECULE_TASKS, ["DeepLoc", "Fluorescence"], ["Promoters"]]
    titles = ["Molecular tasks", "Protein tasks", "Genomic task"]
    for idx, (ax, tasks, title) in enumerate(zip(axes, groups, titles)):
        for colour, task in zip(task_colours, tasks):
            task_rows = sorted((row for row in aggregate_rows if row["task"] == task),
                               key=lambda row: row["median_effective_n"])
            ax.plot([row["median_effective_n"] for row in task_rows],
                    [row["median_central_95_width"] for row in task_rows],
                    marker="o", markersize=6.5, linewidth=2.2, color=colour,
                    markeredgecolor="white", markeredgewidth=0.7,
                    label=task)
        ax.set_xscale("log")
        ax.set_xlabel("Median number of test observations (log scale)")
        ax.set_ylabel("Median width of 95% range")
        ax.set_title(title)
        ax.legend(frameon=False, ncol=3 if idx == 0 else 2,
                  loc="upper right",
                  prop={"size": 10.5, "weight": "bold"},
                  handlelength=2.0, columnspacing=1.2)
        clean_axes(ax, grid="both")
        panel_label(ax, chr(65 + idx))
    fig.suptitle("Precision across test-set sizes",
                 fontsize=17, fontweight="bold", color=DARK, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.97), h_pad=2.35)
    save_figure(fig, "figure5_subsampling_resolution")


def make_exposure_figure(exposure):
    rows = []
    measures = ["exact_identity", "near_duplicate", "shared_scaffold",
                "any_proxy_hit"]
    for task in MOLECULE_TASKS:
        entry = exposure["tasks"][task]
        for corpus in ("zinc", "pubchem"):
            for measure in measures:
                value = entry["empirical"][corpus]["measures"][measure]
                rows.append({
                    "task": task,
                    "corpus": corpus,
                    "measure": measure,
                    "n_flagged": value["n_flagged"],
                    "fraction": value["fraction"],
                    "basis": value["basis"],
                })
    write_csv("figureS1_exposure_proxy_source_data.csv", rows, list(rows[0]))

    fig, axes = plt.subplots(2, 1, figsize=(7.4, 7.4), sharex=True)
    plot_measures = ["exact_identity", "near_duplicate", "shared_scaffold"]
    labels = ["Exact identity", "Near duplicate", "Shared scaffold"]
    colours = ["#8290A6", ORANGE, BLUE]
    task_y = np.arange(len(MOLECULE_TASKS))
    height = 0.22
    row_lookup = {(row["task"], row["corpus"], row["measure"]): row
                  for row in rows}
    for idx, (ax, corpus) in enumerate(zip(axes, ["zinc", "pubchem"])):
        for offset_idx, (measure, label, colour) in enumerate(
                zip(plot_measures, labels, colours)):
            values = [row_lookup[(task, corpus, measure)]["fraction"]
                      for task in MOLECULE_TASKS]
            offsets = task_y + (offset_idx - 1) * height
            ax.barh(offsets, values, height=height, color=colour, label=label,
                    edgecolor="white", linewidth=0.45)
            for yi, value in zip(offsets, values):
                if value > 0:
                    label_x = value + 0.008
                    # Separate the two tiny Lipophilicity annotations rather
                    # than letting their labels visually merge near zero.
                    if value < 0.02:
                        label_x += 0.028 * offset_idx
                    ax.text(label_x, yi, f"{100 * value:.1f}%",
                            fontsize=9.8, fontweight="bold",
                            va="center", color=DARK)
        ax.set_yticks(task_y, MOLECULE_TASKS)
        ax.invert_yaxis()
        ax.set_xlim(0, 1.02)
        ax.xaxis.set_major_formatter(PercentFormatter(1.0))
        ax.set_title(f"{corpus.upper()} 200,000-molecule sample")
        clean_axes(ax)
        panel_label(ax, chr(65 + idx))
    axes[1].set_xlabel("Fraction of benchmark test molecules flagged")
    handles = [Patch(facecolor=colour, label=label)
               for colour, label in zip(colours, labels)]
    fig.legend(handles=handles, frameon=False, ncol=3, loc="lower center",
               bbox_to_anchor=(0.5, 0.005),
               prop={"size": 10.5, "weight": "bold"},
               columnspacing=1.8, handletextpad=0.7)
    fig.suptitle("Molecular overlap with sampled pretraining sources",
                 fontsize=17, fontweight="bold", color=DARK, y=0.995)
    fig.tight_layout(rect=(0, 0.08, 1, 0.97), h_pad=2.0)
    save_figure(fig, "figureS1_exposure_proxies")


def write_legends():
    legends = """# BioLatent figure legends

## Figure 1. Study design and validated benchmark scope

BioLatent evaluates fixed molecular, protein and genomic representations on nine public datasets. For a given endpoint, every representation is assessed with the same regularised linear prediction procedure. One comparison method is selected using validation data before the test set is examined. Molecular confidence intervals resample Bemis–Murcko scaffolds and DeepLoc intervals resample MMseqs2 homology clusters. Statistical evidence is adjusted across 54 eligible study comparisons; the five Fluorescence comparisons are descriptive because its test variants form one connected homology component at the prespecified threshold. Counts include only representations applicable to each chemical or biological domain.

## Figure 2. Molecular property-prediction performance

Performance and 95% bootstrap confidence intervals for the six molecular datasets. BBBP, BACE and CYP3A4 use ROC-AUC; ClinTox uses mean ROC-AUC across its two endpoints; ESOL and Lipophilicity use Spearman correlation. Diamonds identify the comparison method selected from validation data, squares identify the highest observed test score, and a teal diamond with a purple border indicates both. Asterisks mark representations that differed from the comparison method after adjustment across the complete study. The dashed line shows the score of the comparison method. MolCLR–ClinTox is unavailable because the published molecular featurisation cannot process every retained structure.

## Figure 3. Protein and genomic extension

Performance and 95% intervals for DeepLoc 2.0, Fluorescence and Promoters. DeepLoc uses mean ROC-AUC with homology-cluster inference, Fluorescence uses Spearman correlation with descriptive item-resampling intervals, and Promoters uses ROC-AUC. Symbols and dashed comparison lines follow Figure 2; asterisks appear only for eligible formal comparisons. These extension datasets illustrate the behaviour of the same evaluation procedure outside molecular property prediction; their absolute scores are not compared across biological domains.

## Figure 4. Statistical comparisons and scaffold-partition sensitivity

(A) Number of eligible representations that were statistically distinguishable from the preselected comparison method after study-wide adjustment; labels show distinguishable/eligible total, while Fluorescence is marked descriptive. Colours identify molecular, protein and genomic datasets, and grey segments indicate eligible differences that were not distinguishable. (B) Number of 20 balanced scaffold partitions led by the most frequent top-ranked molecular representation. Teal indicates agreement with the leader in the primary partition. (C) Largest score range observed for any representation across the 20 partitions in each molecular dataset; parenthetical labels identify the corresponding representation. The repeated partitions assess robustness and do not replace the primary analysis.

## Figure 5. Precision across test-set sizes

Median width of the empirical 95% range when the observed test predictions are repeatedly evaluated on smaller subsets. Molecular subsets retain complete Bemis–Murcko scaffold groups and DeepLoc subsets retain complete MMseqs2 homology clusters, so the number of observations can differ slightly from the target. Lines summarise 400 repeated subsets for each comparison and target size. Fluorescence curves are descriptive for its fixed variant panel. The curves describe precision within the present test sets and do not predict the exact benefit of collecting additional observations.

## Figure S1. Molecular overlap with sampled pretraining sources

Fractions of molecular test compounds with an exact canonical structure match, an ECFP4 Tanimoto similarity of at least 0.9, or a shared Bemis–Murcko scaffold in random samples of 200,000 ZINC and PubChem structures. These samples provide structural-overlap context rather than exact reconstructions of model training collections. GROVER also reports ChEMBL pretraining, which was not measured because a dated local ChEMBL release was unavailable. Structural similarity does not establish that property labels were available during pretraining.
"""
    (ROOT / "paper" / "FIGURE_LEGENDS.md").write_text(legends)


def main():
    apply_style()
    results = load_json("benchmark_results.json")
    paired = load_json("paired_comparisons.json")
    sensitivity = load_json("split_seed_sensitivity.json")
    resolution = load_json("resolution_curves.json")
    exposure = load_json("exposure_report.json")
    make_scope_figure(results, paired)
    make_score_figures(results, paired)
    make_inference_sensitivity_figure(results, paired, sensitivity)
    make_resolution_figure(results, resolution)
    make_exposure_figure(exposure)
    write_legends()
    print(f"Wrote figures to {FIGURE_DIR}")
    print(f"Wrote source data to {DATA_DIR}")


if __name__ == "__main__":
    main()
