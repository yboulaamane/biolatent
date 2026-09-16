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
        "font.size": 8.5,
        "axes.titlesize": 10,
        "axes.titleweight": "bold",
        "axes.labelsize": 9,
        "axes.labelcolor": DARK,
        "axes.edgecolor": DARK,
        "axes.linewidth": 0.9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "xtick.color": DARK,
        "ytick.color": DARK,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.width": 0.8,
        "ytick.major.width": 0.8,
        "legend.fontsize": 8,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "svg.fonttype": "none",
    })


def clean_axes(ax, grid="x"):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if grid:
        ax.grid(axis=grid, color="#E8ECF2", linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)


def panel_label(ax, label):
    ax.text(-0.15, 1.06, label, transform=ax.transAxes, fontsize=12,
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
                       for comparison in paired[task]["comparisons"].values()]
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

    fig, ax = plt.subplots(figsize=(7.2, 5.4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.02, 0.97, "BioLatent measured benchmark", fontsize=16,
            fontweight="bold", color=DARK, va="top")
    ax.text(0.02, 0.915,
            "Real datasets · frozen representations · one standardised probe · paired inference",
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
                f"{row['measured_cells']} measured cells",
                fontsize=9, fontweight="bold", color=DARK)
        ax.text(x + 0.018, 0.695, row["split_policy"], fontsize=7.7, color=MID)

    pipeline = [
        ("1", "Embed once", "Pinned checkpoint\nand input hash"),
        ("2", "Select comparator", "Validation data; same\nprobe and tuning grid"),
        ("3", "Fixed-test score", "Saved predictions\nand ranked metric"),
        ("4", "Paired inference", "Bootstrap, randomisation\nand study-wide Holm"),
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

    overall_cells = sum(row["measured_cells"] for row in rows)
    overall_resolved = sum(row["resolved_comparisons"] for row in rows)
    overall_comparisons = sum(row["total_comparisons"] for row in rows)
    ax.text(0.02, 0.265, "Validated release", fontsize=9.5,
            fontweight="bold", color=DARK)
    summary = [
        ("9", "real-data tasks"),
        ("18", "representations"),
        (str(overall_cells), "model-task cells"),
        (f"{overall_resolved}/{overall_comparisons}", "resolved comparisons"),
    ]
    for i, (value, label) in enumerate(summary):
        x = 0.02 + i * 0.245
        ax.text(x, 0.19, value, fontsize=17, fontweight="bold", color=PURPLE)
        ax.text(x, 0.145, label, fontsize=8.2, color=MID)
    ax.text(0.02, 0.07,
            "Resolved = study-wide Holm-adjusted p < 0.05 against the validation-selected reference.",
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
                "significant_global": bool(
                    inference and inference.get("significant_global", inference["significant"])
                ),
                "p_holm_global": (inference.get("p_holm_global", inference["p_holm"])
                                  if inference else ""),
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
    xmax = min(1.12, max(highs) + 0.38 * span)
    if xmax - xmin < 0.08:
        xmax = min(1.12, xmin + 0.08)
    ref_score = pair["reference_test_score"]
    ax.axvline(ref_score, color=PURPLE, linewidth=1.0, linestyle=(0, (3, 2)),
               alpha=0.55, zorder=1)
    for yi, model in zip(y, order):
        cell = task_result["models"].get(model)
        if cell is None:
            ax.text(xmin + 0.02 * (xmax - xmin), yi, "N/A", color=MID,
                    fontsize=7.6, va="center")
            continue
        linear = cell["linear"]
        score = linear["score"]
        low = linear.get("ci_low", score)
        high = linear.get("ci_high", score)
        is_ref = model == pair["reference"]
        is_best = model == pair["observed_test_best"]
        comp = pair["comparisons"].get(model)
        sig = bool(comp and comp.get("significant_global", comp["significant"]))
        if is_ref and is_best:
            marker, face, edge = "D", TEAL, PURPLE
        elif is_ref:
            marker, face, edge = "D", PURPLE, PURPLE
        elif is_best:
            marker, face, edge = "s", TEAL, TEAL
        else:
            marker, face, edge = "o", BLUE, RED if sig else BLUE
        ax.errorbar(score, yi, xerr=[[score - low], [high - score]], fmt=marker,
                    markersize=5.7, markerfacecolor=face, markeredgecolor=edge,
                    markeredgewidth=1.3 if sig else 0.9, ecolor="#718096",
                    elinewidth=1.1, capsize=2.4, capthick=1.0, zorder=3)
        label = f"{score:.3f}{'*' if sig else ''}"
        ax.text(high + 0.025 * (xmax - xmin), yi, label, fontsize=7.3,
                va="center", color=RED if sig else DARK)
    ax.set_xlim(xmin, xmax)
    ax.set_yticks(y, [MODEL_LABELS[model] for model in order])
    ax.invert_yaxis()
    metric = next(iter(task_result["models"].values()))["linear"]["metric"]
    ax.set_title(f"{task}\n{metric}; test n = {task_result['n_test']:,}", pad=5)
    ax.set_xlabel(metric)
    ax.xaxis.set_major_locator(MaxNLocator(4))
    clean_axes(ax)


def score_legend(fig, y=0.01):
    handles = [
        Line2D([0], [0], marker="D", color="none", markerfacecolor=PURPLE,
               markeredgecolor=PURPLE, markersize=6,
               label="Validation-selected reference"),
        Line2D([0], [0], marker="s", color="none", markerfacecolor=TEAL,
               markeredgecolor=TEAL, markersize=6, label="Numerical test best"),
        Line2D([0], [0], marker="o", color="#718096", markerfacecolor=BLUE,
               markeredgecolor=BLUE, markersize=5, label="Estimate and 95% CI"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor="white",
               markeredgecolor=RED, markersize=6,
               label="* study-wide Holm p < 0.05 vs reference"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=2, frameon=False,
               bbox_to_anchor=(0.5, y), columnspacing=1.5, handletextpad=0.6)


def make_score_figures(results, paired):
    molecule_rows = score_rows(results, paired, MOLECULE_TASKS,
                               MODEL_ORDER["molecule"])
    write_csv("figure2_molecular_scores.csv", molecule_rows,
              list(molecule_rows[0]))
    fig, axes = plt.subplots(3, 2, figsize=(7.2, 10.2))
    for idx, (ax, task) in enumerate(zip(axes.flat, MOLECULE_TASKS)):
        plot_task_scores(ax, task, results, paired, MODEL_ORDER["molecule"])
        panel_label(ax, chr(65 + idx))
    score_legend(fig, y=0.002)
    fig.suptitle("Molecular frozen-embedding performance", fontsize=14,
                 fontweight="bold", color=DARK, y=0.995)
    fig.tight_layout(rect=(0, 0.055, 1, 0.98), h_pad=2.1, w_pad=1.5)
    save_figure(fig, "figure2_molecular_performance")

    other_order = MODEL_ORDER["protein"] + MODEL_ORDER["genomics"]
    other_rows = []
    for task in PROTEIN_GENOMIC_TASKS:
        order = MODEL_ORDER[results[task]["modality"]]
        other_rows.extend(score_rows(results, paired, [task], order))
    write_csv("figure3_protein_genomic_scores.csv", other_rows,
              list(other_rows[0]))
    fig, axes = plt.subplots(3, 1, figsize=(7.2, 8.4))
    for idx, (ax, task) in enumerate(zip(axes, PROTEIN_GENOMIC_TASKS)):
        plot_task_scores(ax, task, results, paired,
                         MODEL_ORDER[results[task]["modality"]])
        panel_label(ax, chr(65 + idx))
    score_legend(fig, y=0.002)
    fig.suptitle("Protein and genomic frozen-embedding performance", fontsize=14,
                 fontweight="bold", color=DARK, y=0.995)
    fig.tight_layout(rect=(0, 0.07, 1, 0.975), h_pad=2.0)
    save_figure(fig, "figure3_protein_genomic_performance")


def make_inference_sensitivity_figure(results, paired, sensitivity):
    modality_color = {"molecule": PURPLE, "protein": GREEN, "genomics": GOLD}
    summary_rows = []
    for task in TASK_ORDER:
        entry = paired[task]
        comparisons = list(entry["comparisons"].values())
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

    fig, axes = plt.subplots(3, 1, figsize=(7.2, 9.1))
    tasks = TASK_ORDER[::-1]
    y = np.arange(len(tasks))
    row_by_task = {row["task"]: row for row in summary_rows}

    ax = axes[0]
    resolved = [row_by_task[t]["resolved"] for t in tasks]
    unresolved = [row_by_task[t]["unresolved"] for t in tasks]
    colours = [modality_color[row_by_task[t]["modality"]] for t in tasks]
    ax.barh(y, resolved, color=colours, edgecolor="none", height=0.68,
            label="Resolved")
    ax.barh(y, unresolved, left=resolved, color=LIGHT, edgecolor="none",
            height=0.68, label="Unresolved")
    for yi, task, r, u in zip(y, tasks, resolved, unresolved):
        ax.text(r + u + 0.15, yi, f"{r}/{r + u}", va="center",
                fontsize=7.5, color=DARK)
    ax.set_yticks(y, tasks)
    ax.set_xlabel("Reference comparisons")
    ax.set_title("Study-wide statistically resolved comparisons")
    handles = [
        Patch(facecolor=PURPLE, label="Molecules: resolved"),
        Patch(facecolor=GREEN, label="Proteins: resolved"),
        Patch(facecolor=GOLD, label="Genomics: resolved"),
        Patch(facecolor=LIGHT, label="Unresolved"),
    ]
    ax.legend(handles=handles, frameon=False, loc="upper center", ncol=4,
              bbox_to_anchor=(0.5, -0.18), fontsize=7.3,
              columnspacing=1.1, handletextpad=0.5)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    clean_axes(ax)
    panel_label(ax, "A")

    ax = axes[1]
    mol_tasks = MOLECULE_TASKS[::-1]
    y2 = np.arange(len(mol_tasks))
    freq = [row_by_task[t]["split_winner_frequency"] for t in mol_tasks]
    same = [row_by_task[t]["most_frequent_split_winner"] ==
            row_by_task[t]["numerical_test_best"] for t in mol_tasks]
    ax.barh(y2, freq, color=[TEAL if item else ORANGE for item in same],
            height=0.62)
    for yi, task, count in zip(y2, mol_tasks, freq):
        row = row_by_task[task]
        ax.text(count + 0.08, yi,
                f"{row['most_frequent_split_winner']}  ({count}/5)",
                va="center", fontsize=7.2, color=DARK)
    ax.set_xlim(0, 8.2)
    ax.set_yticks(y2, mol_tasks)
    ax.set_xticks(range(0, 6))
    ax.set_xlabel("Scaffold seeds won (of 5)")
    ax.set_title("Consistency of the numerical leader across scaffold splits")
    handles = [
        Line2D([0], [0], color=TEAL, lw=6, label="Matches fixed-test best"),
        Line2D([0], [0], color=ORANGE, lw=6, label="Different from fixed-test best"),
    ]
    ax.legend(handles=handles, frameon=False, loc="lower right")
    clean_axes(ax)
    panel_label(ax, "B")

    ax = axes[2]
    ranges = [row_by_task[t]["maximum_score_range"] for t in mol_tasks]
    ax.barh(y2, ranges, color=BLUE, height=0.62)
    for yi, task, value in zip(y2, mol_tasks, ranges):
        row = row_by_task[task]
        ax.text(value + 0.006, yi,
                f"{value:.3f}  ({row['maximum_range_model']})",
                va="center", fontsize=7.2, color=DARK)
    ax.set_xlim(0, max(ranges) * 1.75)
    ax.set_yticks(y2, mol_tasks)
    ax.set_xlabel("Maximum score range across five seeds")
    ax.set_title("Largest observed split sensitivity within each task")
    clean_axes(ax)
    panel_label(ax, "C")
    fig.suptitle("Inferential resolution and molecular split sensitivity",
                 fontsize=14, fontweight="bold", color=DARK, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.975), h_pad=2.1)
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
    fig, axes = plt.subplots(3, 1, figsize=(7.2, 8.5))
    groups = [MOLECULE_TASKS, ["DeepLoc", "Fluorescence"], ["Promoters"]]
    titles = ["Molecular tasks", "Protein tasks", "Genomic task"]
    for idx, (ax, tasks, title) in enumerate(zip(axes, groups, titles)):
        for colour, task in zip(task_colours, tasks):
            task_rows = sorted((row for row in aggregate_rows if row["task"] == task),
                               key=lambda row: row["median_effective_n"])
            ax.plot([row["median_effective_n"] for row in task_rows],
                    [row["median_central_95_width"] for row in task_rows],
                    marker="o", markersize=4.5, linewidth=1.6, color=colour,
                    label=task)
        ax.set_xscale("log")
        ax.set_xlabel("Median effective subset size (log scale)")
        ax.set_ylabel("Median central 95% range width")
        ax.set_title(title)
        ax.legend(frameon=False, ncol=3 if idx == 0 else 2, loc="upper right")
        clean_axes(ax, grid="both")
        panel_label(ax, chr(65 + idx))
    fig.suptitle("Fixed-test-set subsampling precision",
                 fontsize=14, fontweight="bold", color=DARK, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.975), h_pad=2.0)
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

    fig, axes = plt.subplots(2, 1, figsize=(7.2, 6.5), sharex=True)
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
            ax.barh(offsets, values, height=height, color=colour, label=label)
            for yi, value in zip(offsets, values):
                if value > 0:
                    ax.text(value + 0.008, yi, f"{100 * value:.1f}%",
                            fontsize=6.9, va="center", color=DARK)
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
               bbox_to_anchor=(0.5, 0.005))
    fig.suptitle("Molecular pretraining input-exposure proxies",
                 fontsize=14, fontweight="bold", color=DARK, y=0.995)
    fig.tight_layout(rect=(0, 0.07, 1, 0.975), h_pad=1.8)
    save_figure(fig, "figureS1_exposure_proxies")


def write_legends():
    legends = """# BioLatent figure legends

## Figure 1. Study design and validated benchmark scope

BioLatent evaluates frozen molecular, protein and genomic representations on nine externally published tasks. Each representation is embedded once, evaluated with the same modality-appropriate linear-probe protocol, and compared with a reference selected using validation data before fixed-test evaluation. Difference intervals use paired bootstrap resampling; p-values use paired randomisation and the primary correction is Holm adjustment across all 59 reference comparisons. Counts describe compatible measured cells; unavailable cross-modality cells are not imputed.

## Figure 2. Molecular frozen-embedding performance

Linear-probe scores and model-wise 95% bootstrap confidence intervals for the six molecular tasks. BBBP, BACE and CYP3A4 use ROC-AUC; ClinTox uses macro ROC-AUC across its two endpoints; ESOL and Lipophilicity use Spearman rho. Diamonds identify validation-selected references, squares identify numerical test bests, and a teal diamond with purple outline indicates both. Asterisks mark comparisons with the task reference that survived the study-wide Holm correction. The vertical dashed line is the task reference score. MolCLR–ClinTox is N/A because the official featurizer cannot represent every structure; no row was removed or rewritten.

## Figure 3. Protein and genomic frozen-embedding performance

Linear-probe scores and model-wise 95% bootstrap confidence intervals for DeepLoc 2.0, Fluorescence and Promoters. DeepLoc uses macro ROC-AUC, Fluorescence uses Spearman rho and Promoters uses ROC-AUC. Symbols, dashed reference lines and asterisks follow Figure 2. Confidence intervals describe each model score; significance markers derive from the paired reference comparison after study-wide correction.

## Figure 4. Inferential resolution and molecular split sensitivity

(A) Number of reference comparisons statistically resolved after the primary study-wide Holm correction; labels show resolved/total. Bar colours identify modality and grey segments are unresolved comparisons. (B) Frequency with which the most common numerical leader ranked first across five pre-specified balanced-scaffold seeds. Teal indicates agreement with the fixed-test numerical best and orange indicates disagreement. (C) Largest score range observed for any representation across the five seeds in each molecular task; parenthetical labels identify the representation with that range. Split sensitivity is diagnostic and does not replace the primary fixed partition.

## Figure 5. Fixed-test-set subsampling precision

Median central 95% range width across each task's validation-reference comparisons as saved fixed-test predictions are repeatedly subsampled without replacement. Molecular subsamples retain whole Murcko-scaffold groups, so effective n may differ from requested n. Lines summarize 400 repeated subsets per comparison and sample-size target. The curves are conditional on the observed test sets and do not estimate the causal effect of collecting additional data.

## Figure S1. Molecular pretraining input-exposure proxies

Fractions of molecular test items with exact canonical identity, ECFP4 Tanimoto similarity of at least 0.9, or a shared Murcko scaffold in random 200,000-molecule ZINC and PubChem samples. These database samples are proxies rather than exact dated checkpoint training subsets. GROVER's additional declared ChEMBL exposure is unmeasured because no pinned local ChEMBL snapshot was available. Input familiarity does not establish downstream-label leakage.
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
