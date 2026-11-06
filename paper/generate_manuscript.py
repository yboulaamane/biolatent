"""Generate the public BioLatent manuscript from committed result artifacts.

The existing ``BioLatent_methods.docx`` is used only as a style and page-layout
template. The source document is never overwritten. Every result table and all
headline counts are computed from JSON so prose cannot silently drift after a
rerun.
"""

import csv
import json
import os
import re
from collections import Counter
from pathlib import Path

import numpy as np
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = Path(os.environ.get(
    "BIOLATENT_MANUSCRIPT_TEMPLATE", ROOT / "BioLatent_methods.docx"
))
OUTPUT = ROOT / "paper" / "BioLatent_methods_revised.docx"
SUPPLEMENTARY_OUTPUT = ROOT / "paper" / "BioLatent_supplementary.docx"
FIGURE_DIR = ROOT / "paper" / "figures"
FIGURE_LEGENDS_PATH = ROOT / "paper" / "FIGURE_LEGENDS.md"
PAPER_TITLE = (
    "BioLatent: A Registry and Standardized Benchmark for Molecular and "
    "Biological Representations"
)
ZENODO_DOI = None
REPOSITORY_URL = "https://github.com/yboulaamane/biolatent"
WEBSITE_URL = "https://biolatent.vercel.app"
REGISTRY_ENTRY_COUNT = 50
REGISTRY_MODALITY_COUNTS = {
    "molecular": 16,
    "protein": 21,
    "complex": 3,
    "nucleic-acid": 9,
    "reaction": 1,
}
REGISTRY_TYPE_COUNTS = {"learned": 45, "fixed": 3, "hybrid": 2}
REGISTRY_CODE_COUNT = 46
REGISTRY_WEIGHTS_COUNT = 26
REGISTRY_ANY_ARTIFACT_COUNT = 48
COUNT_WORDS = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
    6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
    11: "eleven", 12: "twelve", 14: "fourteen", 15: "fifteen",
    16: "sixteen", 19: "nineteen", 21: "twenty-one", 26: "twenty-six",
    28: "twenty-eight", 30: "thirty", 45: "forty-five", 46: "forty-six",
    48: "forty-eight", 50: "fifty", 66: "sixty-six", 86: "eighty-six",
}
TASK_ORDER = ["BBBP", "ClinTox", "BACE", "ESOL", "Lipophilicity", "CYP3A4",
              "DeepLoc", "Fluorescence", "Promoters"]
MODEL_LABELS = {
    "ecfp4": "ECFP4", "rdkit2d": "RDKit2D",
    "chemberta_77m": "ChemBERTa-77M", "chemberta_zinc": "ChemBERTa-ZINC",
    "molformer_xl": "MoLFormer-XL", "unimol_v1": "Uni-Mol v1",
    "molclr_gin": "MolCLR GIN", "grover_base": "GROVER Base",
    "grover_large": "GROVER Large", "kmer3_protein": "3-mer frequency",
    "esm2_8m": "ESM-2 8M", "esm2_35m": "ESM-2 35M",
    "esm2_150m": "ESM-2 150M", "esm2_650m": "ESM-2 650M",
    "protbert": "ProtBERT", "esm1v_650m": "ESM-1v 650M",
    "esmc_300m": "ESM-C 300M", "unirep_1900": "UniRep 1900-unit",
    "proteinbert": "ProteinBERT", "carp_640m": "CARP 640M",
    "protrek_650m": "ProTrek 650M", "kmer5_dna": "5-mer frequency",
    "nucleotide_transformer": "Nucleotide Transformer 500M",
    "hyenadna": "HyenaDNA-tiny", "caduceus": "Caduceus-PS 131K",
    "gena_lm": "GENA-LM BERT Large", "grover_dna": "GROVER DNA",
    "evo2_7b": "Evo 2 7B", "dnabert2": "DNABERT-2 117M",
    "evo1_7b": "Evo 1 7B",
}
TASK_DETAILS = {
    "BBBP": ("Blood–brain barrier penetration", "MoleculeNet scaffold", "ROC-AUC"),
    "ClinTox": ("FDA approval and clinical toxicity", "MoleculeNet scaffold", "Mean ROC-AUC"),
    "BACE": ("BACE-1 inhibition", "MoleculeNet scaffold", "ROC-AUC"),
    "ESOL": ("Aqueous solubility", "MoleculeNet scaffold", "Spearman correlation"),
    "Lipophilicity": ("Lipophilicity", "MoleculeNet scaffold", "Spearman correlation"),
    "CYP3A4": ("CYP3A4 substrate status", "TDC scaffold", "ROC-AUC"),
    "DeepLoc": ("Protein subcellular localization", "Published homology split", "Mean ROC-AUC"),
    "Fluorescence": ("Protein fluorescence", "Published extrapolation split", "Spearman correlation"),
    "Promoters": ("Promoter recognition", "Published chromosome split", "ROC-AUC"),
}
REPRESENTATION_DETAILS = {
    "ecfp4": ("Molecular graph", "Circular substructure fingerprint", "Conventional baseline"),
    "rdkit2d": ("Molecular graph", "Physicochemical and topological descriptors", "Conventional baseline"),
    "chemberta_77m": ("SMILES", "Pretrained chemical language model", "Learned representation"),
    "chemberta_zinc": ("SMILES", "Pretrained chemical language model", "Learned representation"),
    "molformer_xl": ("SMILES", "Pretrained chemical language model", "Learned representation"),
    "unimol_v1": ("Three-dimensional molecular structure", "Pretrained 3D molecular model", "Learned representation"),
    "molclr_gin": ("Molecular graph", "Contrastive graph neural network", "Learned representation"),
    "grover_base": ("Molecular graph", "Pretrained graph transformer", "Learned representation"),
    "grover_large": ("Molecular graph", "Pretrained graph transformer", "Learned representation"),
    "kmer3_protein": ("Protein sequence", "Amino-acid triplet frequencies", "Conventional baseline"),
    "esm2_8m": ("Protein sequence", "Pretrained protein language model", "Learned representation"),
    "esm2_35m": ("Protein sequence", "Pretrained protein language model", "Learned representation"),
    "esm2_150m": ("Protein sequence", "Pretrained protein language model", "Learned representation"),
    "esm2_650m": ("Protein sequence", "Pretrained protein language model", "Learned representation"),
    "protbert": ("Protein sequence", "Pretrained protein language model", "Learned representation"),
    "esm1v_650m": ("Protein sequence", "Pretrained protein language model", "Learned representation"),
    "esmc_300m": ("Protein sequence", "Pretrained protein language model", "Learned representation"),
    "unirep_1900": ("Protein sequence", "Pretrained recurrent sequence model", "Learned representation"),
    "proteinbert": ("Protein sequence", "Pretrained protein language model", "Learned representation"),
    "carp_640m": ("Protein sequence", "Pretrained convolutional sequence model", "Learned representation"),
    "protrek_650m": ("Protein sequence", "Pretrained trimodal sequence encoder", "Learned representation"),
    "kmer5_dna": ("DNA sequence", "Nucleotide 5-mer frequencies", "Conventional baseline"),
    "nucleotide_transformer": ("DNA sequence", "Pretrained genomic sequence model", "Learned representation"),
    "hyenadna": ("DNA sequence", "Pretrained long-range sequence model", "Learned representation"),
    "caduceus": ("DNA sequence", "Pretrained bidirectional sequence model", "Learned representation"),
    "gena_lm": ("DNA sequence", "Pretrained genomic language model", "Learned representation"),
    "grover_dna": ("DNA sequence", "Pretrained genomic language model", "Learned representation"),
    "evo2_7b": ("DNA sequence", "Pretrained genomic foundation model", "Learned representation"),
    "dnabert2": ("DNA sequence", "Pretrained genomic language model", "Learned representation"),
    "evo1_7b": ("DNA sequence", "Pretrained genomic foundation model", "Learned representation"),
}

LITERATURE_REFERENCE_NUMBERS = {
    "https://doi.org/10.48550/arXiv.2209.01712": 25,
    "https://doi.org/10.1039/C7SC02664A": 9,
    "https://doi.org/10.48550/arXiv.2007.02835": 6,
    "https://doi.org/10.1038/s42256-022-00580-7": 3,
    "https://doi.org/10.1038/s42256-022-00447-x": 5,
    "https://openreview.net/forum?id=6K2RM6wVqKu": 4,
    "https://tdcommons.ai/benchmark/admet_group/15cyp3a4s/": 10,
    "https://doi.org/10.48550/arXiv.2506.06443": 26,
}


def load_json(name):
    path = ROOT / "results" / name
    if not path.exists():
        raise FileNotFoundError(f"Required result artifact is missing: {path}")
    return json.loads(path.read_text())


def load_csv(name):
    path = ROOT / "results" / name
    if not path.exists():
        raise FileNotFoundError(f"Required result artifact is missing: {path}")
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def prose_count(value):
    """Spell out the small counts used in narrative prose."""
    return COUNT_WORDS.get(value, str(value))


def clear_body(document):
    body = document._body._element
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)


def set_cell_shading(cell, fill):
    properties = cell._tc.get_or_add_tcPr()
    shade = properties.find(qn("w:shd"))
    if shade is None:
        shade = OxmlElement("w:shd")
        properties.append(shade)
    shade.set(qn("w:fill"), fill)


def repeat_header(row):
    properties = row._tr.get_or_add_trPr()
    element = OxmlElement("w:tblHeader")
    element.set(qn("w:val"), "true")
    properties.append(element)


def prevent_row_split(row):
    properties = row._tr.get_or_add_trPr()
    properties.append(OxmlElement("w:cantSplit"))


def add_hyperlink(paragraph, text, url):
    relationship = paragraph.part.relate_to(
        url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), relationship)
    run = OxmlElement("w:r")
    properties = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "365F91")
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    size = OxmlElement("w:sz")
    size.set(qn("w:val"), "24")
    complex_script_size = OxmlElement("w:szCs")
    complex_script_size.set(qn("w:val"), "24")
    fonts = OxmlElement("w:rFonts")
    for attribute in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn(f"w:{attribute}"), "Times New Roman")
    properties.extend([fonts, color, underline, size, complex_script_size])
    run.append(properties)
    text_element = OxmlElement("w:t")
    text_element.text = text
    run.append(text_element)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def add_heading(document, text, level):
    paragraph = document.add_heading(text, level=level)
    paragraph.paragraph_format.keep_with_next = True
    for run in paragraph.runs:
        run.font.name = "Times New Roman"
        run.font.bold = True
        run.font.color.rgb = RGBColor(0, 0, 0)
    return paragraph


def add_body(document, text, style=None):
    paragraph = document.add_paragraph(text, style=style)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    paragraph.paragraph_format.space_after = Pt(6)
    paragraph.paragraph_format.line_spacing = 1.5
    for run in paragraph.runs:
        run.font.name = "Times New Roman"
        run.font.size = Pt(12)
    return paragraph


def available_style(document, preferred, fallback="Normal"):
    """Use a template style when present without making it a requirement."""
    try:
        document.styles[preferred]
        return preferred
    except KeyError:
        return fallback


def add_caption(document, text):
    paragraph = document.add_paragraph(
        text, style=available_style(document, "Caption")
    )
    paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    paragraph.paragraph_format.keep_with_next = True
    paragraph.paragraph_format.line_spacing = 1.0
    for run in paragraph.runs:
        run.font.name = "Times New Roman"
        run.font.size = Pt(9)
    return paragraph


def load_figure_legends():
    """Read the single source of truth for manuscript figure captions."""
    if not FIGURE_LEGENDS_PATH.exists():
        raise FileNotFoundError(
            f"Missing {FIGURE_LEGENDS_PATH}; run paper/generate_figures.py first"
        )
    text = FIGURE_LEGENDS_PATH.read_text()
    sections = re.findall(
        r"^## (Figure[^\n]+)\n\n(.*?)(?=\n## Figure|\Z)", text, flags=re.MULTILINE | re.DOTALL
    )
    return {
        title.split(".", 1)[0]: f"{title}. {body.strip()}"
        for title, body in sections
    }


def add_publication_figure(document, filename, legend, width):
    """Insert a centred, publication-resolution figure and its full legend."""
    path = FIGURE_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}; run paper/generate_figures.py first")
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.keep_with_next = True
    paragraph.add_run().add_picture(str(path), width=Inches(width))
    add_caption(document, legend)


def add_table(document, headers, rows, widths=None, font_size=10):
    # Journal-facing tables use a consistent readable size, irrespective of
    # the legacy per-table size hints retained at call sites.
    font_size = 10
    table = document.add_table(rows=1, cols=len(headers))
    # The retained manuscript template was exported without Word's built-in
    # ``Table Grid`` style. Prefer it when present, but fall back to the
    # template's own table style rather than making generation depend on a
    # hidden style that may not exist in another DOCX.
    try:
        table.style = "Table Grid"
    except KeyError:
        table.style = "Table"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    header = table.rows[0]
    repeat_header(header)
    for index, text in enumerate(headers):
        cell = header.cells[index]
        cell.text = str(text)
        set_cell_shading(cell, "D9E2F3")
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        for run in cell.paragraphs[0].runs:
            run.bold = True
            run.font.name = "Times New Roman"
            run.font.size = Pt(font_size)
    for values in rows:
        row = table.add_row()
        prevent_row_split(row)
        for index, value in enumerate(values):
            cell = row.cells[index]
            cell.text = str(value)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_after = Pt(0)
                for run in paragraph.runs:
                    run.font.name = "Times New Roman"
                    run.font.size = Pt(font_size)
    if widths:
        for row in table.rows:
            for index, width in enumerate(widths):
                row.cells[index].width = Inches(width)
    document.add_paragraph().paragraph_format.space_after = Pt(2)
    return table


def score_summary(results, tasks):
    models = []
    for task in tasks:
        models.extend(results[task]["models"])
    return len(set(models)), sum(len(results[task]["models"]) for task in tasks)


def inference_summary(results, paired):
    out = {}
    for modality in ("molecule", "protein", "genomics"):
        tasks = [task for task in TASK_ORDER if results[task]["modality"] == modality]
        all_comparisons = [comparison for task in tasks
                           for comparison in paired[task]["comparisons"].values()]
        comparisons = [comparison for comparison in all_comparisons
                       if comparison.get("inferential", True)]
        out[modality] = {
            "tasks": len(tasks), "total": len(comparisons),
            "descriptive": len(all_comparisons) - len(comparisons),
            "significant": sum(bool(item.get("significant_global", item["significant"]))
                               for item in comparisons),
        }
    out["all"] = {
        "total": sum(out[modality]["total"] for modality in out),
        "significant": sum(out[modality]["significant"] for modality in out),
    }
    return out


def readable_result_rows(results, paired, tasks):
    """Format the main score tables with three decimals and visible leaders."""
    models = []
    for task in tasks:
        for model in results[task]["models"]:
            if model not in models:
                models.append(model)
    rows = []
    for model in models:
        values = [MODEL_LABELS.get(model, model)]
        for task in tasks:
            cell = results[task]["models"].get(model)
            if cell is None:
                values.append("—")
                continue
            marker = "†" if model == paired[task]["observed_test_best"] else ""
            values.append(f"{float(cell['linear']['score']):.3f}{marker}")
        rows.append(values)
    return rows


def compact_target_summary(summary):
    """Readable class prevalence or regression moments for split diagnostics."""
    if "mean" in summary:
        return f"mean {summary['mean']:.2f}; SD {summary['standard_deviation']:.2f}"
    if "positive_fraction" in summary:
        return f"{100 * summary['positive_fraction']:.1f}% positive"
    return "; ".join(
        f"{label.replace('target_', '', 1)}: {100 * values['positive_fraction']:.1f}%"
        for label, values in summary.items()
    )


def add_page_number(section):
    paragraph = section.footer.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = " PAGE "
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instruction, end])


def build():
    results = load_json("benchmark_results.json")
    paired = load_json("paired_comparisons.json")
    exposure = load_json("exposure_report.json")
    sensitivity = load_json("split_seed_sensitivity.json")
    resolution = load_json("resolution_curves.json")
    split_diagnostics = load_json("split_diagnostics.json")
    literature_comparison = load_json("literature_measured_comparison.json")
    sample_efficiency = load_csv("sample_efficiency_summary.csv")
    smiles_augmentation = load_csv("smiles_augmentation_summary.csv")
    chemical_neighborhoods = load_csv("chemical_space_neighborhoods.csv")
    chemical_correlations = load_csv("chemical_space_correlations.csv")
    chemical_mapping = load_csv("chemical_space_mapping_summary.csv")
    figure_legends = load_figure_legends()
    missing = [task for task in TASK_ORDER if task not in results or task not in paired]
    if missing:
        raise RuntimeError(f"Incomplete study artifacts; missing tasks: {missing}")

    model_count, cell_count = score_summary(results, TASK_ORDER)
    inference = inference_summary(results, paired)
    canonical_efficiency = [
        row for row in sample_efficiency if row["variant"] == "canonical"
    ]
    scarcity_10 = [
        row for row in canonical_efficiency
        if np.isclose(float(row["fraction"]), 0.10)
    ]
    scarcity_10_medians = {
        modality: float(np.median([
            float(row["change_from_full"]) for row in scarcity_10
            if row["modality"] == modality
        ]))
        for modality in ("molecule", "protein", "genomics")
    }
    scarcity_negative = {
        fraction: sum(
            float(row["change_from_full"]) < 0
            for row in canonical_efficiency
            if np.isclose(float(row["fraction"]), fraction)
        )
        for fraction in (0.10, 0.25, 0.50)
    }
    task_types = {
        row["task"]: row["task_type"] for row in canonical_efficiency
    }
    augmentation_10 = [
        row for row in smiles_augmentation
        if np.isclose(float(row["fraction"]), 0.10)
    ]
    augmentation_25 = [
        row for row in smiles_augmentation
        if np.isclose(float(row["fraction"]), 0.25)
    ]
    augmentation_by_type = {
        label: [
            float(row["mean_change"]) for row in augmentation_10
            if (task_types[row["task"]] == "regression") == (label == "regression")
        ]
        for label in ("classification", "regression")
    }
    neighborhood_index = {
        (row["task"], row["model_id"], row["variant"]): row
        for row in chemical_neighborhoods
        if int(row["k"]) == 10
    }
    geometry_changes = {"classification": [], "regression": []}
    for task in TASK_ORDER[:6]:
        for model in ("chemberta_77m", "chemberta_zinc", "molformer_xl"):
            canonical = neighborhood_index.get((task, model, "canonical"))
            augmented = neighborhood_index.get((task, model, "smiles_mean10"))
            if canonical is None or augmented is None:
                continue
            endpoint_type = (
                "regression" if task_types[task] == "regression" else "classification"
            )
            geometry_changes[endpoint_type].append(
                float(augmented["endpoint_coherence"])
                - float(canonical["endpoint_coherence"])
            )
    augmentation_correlations = {
        row["task"]: row for row in chemical_correlations
        if row["analysis"] == "smiles_augmentation"
        and np.isclose(float(row["fraction"]), 0.10)
        and row["geometry_metric"] == "delta_endpoint_coherence"
    }
    dataset_coherence = {
        row["model_id"]: float(row["dataset_coherence_at_15"])
        for row in chemical_mapping
    }
    projection_recall = [
        float(row["projection_neighbor_recall_at_15"])
        for row in chemical_mapping
    ]
    # The local house-style template is optional and intentionally not part of
    # the public repository. A clean clone must still be able to generate the
    # complete manuscript with python-docx's standard document styles.
    document = Document(TEMPLATE) if TEMPLATE.exists() else Document()
    clear_body(document)
    for style_name in (
        "Normal", "Abstract", "Bibliography", "List Paragraph", "Caption",
        "Author", "Subtitle",
    ):
        try:
            style = document.styles[style_name]
        except KeyError:
            continue
        style.font.name = "Times New Roman"
        style.font.size = Pt(9 if style_name == "Caption" else 12)
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    for style_name in ("Title", "Heading 1", "Heading 2", "Heading 3", "Abstract Title"):
        try:
            style = document.styles[style_name]
        except KeyError:
            continue
        style.font.name = "Times New Roman"
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    document.core_properties.title = PAPER_TITLE
    document.core_properties.author = (
        "Yassir Boulaamane; Michael Fernandez; Christopher M. Baker; Lea Talmann; "
        "Jean-Didier Maréchal"
    )
    document.core_properties.last_modified_by = "Yassir Boulaamane"
    document.core_properties.subject = "BioLatent representation registry and benchmark"
    document.core_properties.keywords = (
        "representation registry, molecular property prediction, chemical fingerprints, "
        "scaffold split, protein language models, benchmark reproducibility")

    title = document.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title.add_run(PAPER_TITLE)
    title_run.font.name = "Times New Roman"
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor(0, 0, 0)
    author = document.add_paragraph(
        "Yassir Boulaamane¹*, Michael Fernandez², Christopher M. Baker², Lea Talmann³, "
        "Jean-Didier Maréchal¹",
        style=available_style(document, "Author", "Subtitle"),
    )
    author.alignment = WD_ALIGN_PARAGRAPH.CENTER
    affiliation = document.add_paragraph(
        "¹InSiliChem, Departament de Química, Universitat Autònoma de Barcelona, "
        "08193, Bellaterra (Barcelona), Spain")
    affiliation.alignment = WD_ALIGN_PARAGRAPH.CENTER
    affiliation_2 = document.add_paragraph(
        "²Syngenta, Jealott's Hill International Research Centre, Bracknell, "
        "RG42 6EY, UK"
    )
    affiliation_2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    affiliation_3 = document.add_paragraph(
        "³Syngenta Crop Protection, Schaffhauserstrasse 101, 4332 Stein, Switzerland"
    )
    affiliation_3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    email = document.add_paragraph("*E-mail:")
    email.alignment = WD_ALIGN_PARAGRAPH.CENTER

    abstract_heading = document.add_paragraph(
        "Abstract", style=available_style(document, "Abstract Title", "Heading 1")
    )
    for run in abstract_heading.runs:
        run.font.name = "Times New Roman"
        run.font.bold = True
        run.font.color.rgb = RGBColor(0, 0, 0)
    registry_summary = literature_comparison["registry_summary"]
    matched_summary = literature_comparison["matched_summary"]
    rank_concordance = literature_comparison["rank_concordance"]
    abstract = (
        f"The growing number of molecular and biological representations makes method selection "
        f"difficult, while published benchmark results are scattered across studies that use "
        f"different datasets, partitions and prediction models. BioLatent addresses these problems "
        f"through two connected resources. First, a curated registry records "
        f"{REGISTRY_ENTRY_COUNT} representations across five modalities and "
        f"{registry_summary['benchmark_records']} source-verified performance results together "
        f"with model, dataset, metric, partition and artifact provenance. Second, a standardized "
        f"benchmark evaluates {model_count} compatible representations on "
        f"{prose_count(len(TASK_ORDER))} public "
        f"datasets using fixed vectors and a common regularized linear prediction procedure. The "
        f"two layers were linked only when the named representation family, endpoint and metric "
        f"matched. {prose_count(matched_summary['pairs']).capitalize()} literature–measured pairs "
        f"met these criteria. Although "
        f"all {matched_summary['documented_scaffold_pairs']} literature values used documented "
        f"scaffold splits, the measured score was higher in "
        f"{prose_count(matched_summary['measured_higher'])} pairs and the literature score in "
        f"{prose_count(matched_summary['literature_higher'])}; ranking agreement "
        f"was weak for BBBP and negative for CYP3A4. In the controlled benchmark, no representation "
        f"led every molecular endpoint, conventional fingerprints and descriptors remained "
        f"competitive, and the leading method changed across repeated scaffold partitions in all "
        f"six molecular datasets. At 10% of the labeled training data, performance fell in every "
        f"representation–task cell; averaging randomized SMILES improved the molecular regression "
        f"tasks but generally reduced classification performance. "
        f"{prose_count(inference['all']['significant']).capitalize()} of "
        f"{inference['all']['total']} formal comparisons were statistically distinguishable after "
        f"correction, including {inference['molecule']['significant']} of "
        f"{inference['molecule']['total']} molecular comparisons, "
        f"{prose_count(inference['protein']['significant'])} of "
        f"{prose_count(inference['protein']['total'])} DeepLoc comparisons and "
        f"{prose_count(inference['genomics']['significant'])} of "
        f"{prose_count(inference['genomics']['total'])} genomic comparisons. "
        f"BioLatent therefore serves two complementary purposes: the registry organizes published "
        f"evidence and model provenance, while the measured benchmark supports controlled comparison. "
        f"Together, they show why literature scores should be interpreted in their original "
        f"experimental context rather than combined into a single leaderboard.")
    abstract_paragraph = document.add_paragraph(
        abstract, style=available_style(document, "Abstract")
    )
    abstract_paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    abstract_paragraph.paragraph_format.line_spacing = 1.5
    for run in abstract_paragraph.runs:
        run.font.name = "Times New Roman"
        run.font.size = Pt(12)
    add_body(document, "Keywords: representation registry; molecular property prediction; "
             "chemical fingerprints; scaffold split; protein language models; benchmark "
             "reproducibility")

    add_heading(document, "1. Introduction", 1)
    add_body(document, "Computational models for molecular and biological prediction depend on how an "
             "input is represented. Circular fingerprints and calculated descriptors encode "
             "established chemical features [1], whereas newer methods learn representations from "
             "molecular strings, graphs, three-dimensional structures or biological sequences [2-6]. "
             "As the number and diversity of these methods increase, researchers need a practical way "
             "to identify available representations, understand their input and computational "
             "requirements, and examine the evidence reported for them.")
    add_body(document, "Published evidence is difficult to navigate because it is distributed across "
             "papers, repositories and benchmark websites. Even when two studies report the same "
             "endpoint, they may use different dataset versions, partitions, prediction models or "
             "tuning procedures. Comparative studies have consequently reached endpoint-dependent "
             "conclusions, with established fingerprints and descriptors often remaining competitive "
             "[7,8]. A reported score is therefore evidence from a particular experiment, not an "
             "intrinsic property of a representation.")
    add_body(document, "BioLatent was created first as a provenance-aware registry of molecular and "
             "biological representations. It brings together representation metadata, implementation "
             "and weight links, computational requirements, and benchmark results reported by their "
             "original sources. The registry is intended for evidence discovery and method selection; "
             "it does not pool heterogeneous scores into a leaderboard. The variation exposed during "
             "curation motivated a second layer in which compatible representations were evaluated "
             "under one common procedure.")
    add_body(document, "A controlled benchmark requires more than a shared endpoint name. MoleculeNet "
             "and the Therapeutics Data Commons provide widely used molecular datasets [9,10], but "
             "performance can still depend strongly on how compounds are assigned to training and test "
             "sets. Random allocation may place close analogs on both sides of the split, while temporal "
             "or scaffold-based evaluation can better test transfer to new chemical series [11-13]. "
             "Even scaffold-based results can vary with the particular allocation of scaffolds. Dataset "
             "identity, preprocessing and partition provenance must therefore remain attached to every "
             "result.")
    add_body(document, "Uncertainty is equally important. Molecular datasets differ in size, assay "
             "noise, class balance and structural diversity. Although uncertainty estimation is "
             "increasingly used for individual molecular predictions [14], comparisons between "
             "representations also require uncertainty on the difference between their test "
             "performances. Paired analysis is appropriate because methods are evaluated on the same "
             "observations, and adjustment for multiple comparisons is needed when many "
             "representations are examined.")
    add_body(document, "BioLatent therefore combines a curated registry with a standardized measured "
             "benchmark. The registry preserves what has been reported and where it came from. The "
             "measured benchmark asks how compatible representations behave when dataset preparation, "
             "partitioning, model fitting and evaluation are held constant. We used the two layers to "
             "examine whether published magnitudes and rankings transferred to a common protocol, "
             "whether pretrained representations consistently outperformed conventional chemical "
             "features, and whether apparent leaders were robust to scaffold allocation and statistical "
             "uncertainty. The benchmark covers six molecular endpoints and three protein or genomic "
             "tasks. Figure 1 summarizes its design and validated scope.")
    add_publication_figure(
        document, "figure1_study_design.png", figure_legends["Figure 1"], 6.55
    )

    add_heading(document, "2. Methods", 1)
    add_heading(document, "2.1 Registry construction and curation", 2)
    add_body(document, f"The BioLatent registry was designed as a curated, updatable catalog rather "
             f"than a systematic review or exhaustive census. The snapshot analyzed for this study "
             f"was frozen as version 1.3.0 and contained {REGISTRY_ENTRY_COUNT} identifiable "
             "representations spanning molecules, proteins, complexes, nucleic acids and reactions. "
             "Entries were retained when the representation could be traced to a public primary "
             "source, implementation or model artifact. Recorded fields included modality, input "
             "format, representation type, vector dimension, training source, license, computational "
             "profile, and links to available code and weights.")
    add_body(document, f"A published performance value was added only when a primary publication or "
             f"official benchmark source identified the dataset, endpoint, metric and numerical "
             f"result. Each of the {registry_summary['benchmark_records']} retained performance "
             "records includes a direct source link and a row-level note describing the reported "
             "protocol or table location. Values were checked against their sources, and unsupported "
             "or mismatched records were removed rather than estimated. Community submissions can "
             "propose representation metadata through a reviewed pull request, but they cannot add "
             "benchmark claims without separate source verification. Because the literature protocols "
             "are heterogeneous, registry values are presented as an evidence map and are not combined "
             "into a single ranking.")

    add_heading(document, "2.2 Measured benchmark datasets and representations", 2)
    add_body(document, "The measured benchmark comprised six molecular datasets. BBBP, ClinTox, "
             "BACE, ESOL and Lipophilicity were obtained from MoleculeNet [9]. CYP3A4 used the "
             "667-compound Carbon–Mangels substrate dataset distributed through the Therapeutics "
             "Data Commons [10,15]; it was not replaced by the larger CYP3A4 inhibition dataset. "
             "ClinTox retained both its clinical-toxicity and FDA-approval endpoints.")
    add_body(document, "MoleculeNet structures were checked with RDKit while preserving source "
             "records that differed by salt form or stereochemistry. The five MoleculeNet datasets "
             "were divided by a balanced Bemis–Murcko scaffold procedure [13]. CYP3A4 structures "
             "were standardized and deduplicated before applying the scaffold procedure supplied "
             "by the Therapeutics Data Commons. One partition was designated for model fitting, "
             "one for model selection and one for final evaluation.")
    add_body(document, "The extension analysis used DeepLoc 2.0 protein localization, TAPE protein "
             "fluorescence and Nucleotide Transformer promoter recognition [16-18]. Their published "
             "homology, extrapolation or chromosome-based partitions were retained. These datasets "
             "test whether the same comparison framework behaves similarly outside molecular "
             "property prediction; their absolute scores are not compared with molecular scores.")
    task_rows = []
    for task in TASK_ORDER:
        entry = results[task]
        endpoint, split_label, metric_label = TASK_DETAILS[task]
        task_rows.append([
            task, endpoint, entry["n_total"], entry["n_test"], split_label, metric_label,
        ])
    add_body(document, "The datasets, retained partitions and endpoint-specific performance "
             "measures are summarized in Table 1.")
    add_caption(document, "Table 1. Datasets and evaluation measures. Dataset sizes are reported after preprocessing; the test set was not used for model selection.")
    add_table(document, ["Dataset", "Endpoint", "Compounds or sequences", "Test set", "Partition", "Measure"],
              task_rows, widths=[0.75, 1.65, 0.8, 0.6, 1.25, 1.05], font_size=10)

    diagnostic_rows = []
    for task in TASK_ORDER[:6]:
        diagnostic = split_diagnostics["tasks"][task]
        fit = diagnostic["splits"]["non_test_fit"]
        test = diagnostic["splits"]["test"]
        overlap = diagnostic["fit_test_overlap"]
        diagnostic_rows.append([
            task,
            f"{fit['n']:,} / {test['n']:,}",
            f"{fit['n_scaffold_groups']:,} / {test['n_scaffold_groups']:,}",
            compact_target_summary(fit["target"]),
            compact_target_summary(test["target"]),
            f"{overlap['exact_input_count']} / {overlap['scaffold_count']}",
        ])
    add_body(document, "The measured benchmark used the subset of registry entries that matched a "
             "study domain and could be calculated reproducibly from a public implementation or model "
             "artifact. The molecular comparison included ECFP4 circular fingerprints, RDKit2D "
             "descriptors, three SMILES-based models, two pretrained graph families, a contrastive "
             "graph model and a three-dimensional molecular model [2-6]. Fingerprints and "
             "descriptors provide established cheminformatics baselines; the remaining methods "
             "represent structures learned from large unlabeled molecular collections. Each "
             "representation was calculated once and held fixed during property-model fitting.")
    add_body(document, "Uni-Mol v1 inputs were generated from the dataset SMILES with "
             "unimol-tools 0.1.6. For each molecule, explicit hydrogens were added and one RDKit "
             "conformer was generated with a fixed random seed of 42, followed by MMFF optimization "
             "when possible. When three-dimensional generation was unsuccessful, the toolkit used "
             "two-dimensional coordinates or, after an exception, zero coordinates. No "
             "multi-conformer sampling or averaging was performed. Inputs above 256 atoms were "
             "reduced with the toolkit's seeded atom-sampling procedure; this affected one entry in "
             "BBBP and one in ClinTox. The final representation was the mean of the non-special atom "
             "vectors.")
    add_body(document, "The protein benchmark combined amino-acid triplet frequencies with ESM-2 at "
             "four sizes, ProtBERT, ESM-1v, ESM-C, UniRep, ProteinBERT, CARP and the ProTrek sequence "
             "encoder [19,20,27-31,38]. The promoter benchmark combined nucleotide 5-mer frequencies "
             "with Nucleotide Transformer, HyenaDNA, Caduceus, GENA-LM, GROVER DNA, DNABERT-2, Evo 1 "
             "and Evo 2 [18,21,32-37]. A representation was evaluated "
             "only on its corresponding molecular or sequence domain. MolCLR could not process all "
             "ClinTox structures with its published molecular featurization and is therefore shown "
             "as unavailable rather than estimated from a reduced dataset.")
    model_rows = [
        [MODEL_LABELS[model], *REPRESENTATION_DETAILS[model]]
        for model in MODEL_LABELS
    ]
    add_body(document, "The molecular, protein and genomic representations selected for the measured "
             "benchmark are listed in Table 2.")
    add_caption(document, "Table 2. Representations included in the measured benchmark. Detailed model versions and software provenance are provided in the public run manifest.")
    add_table(document, ["Representation", "Input", "Approach", "Comparison role"],
              model_rows, widths=[1.35, 1.35, 2.2, 1.25], font_size=10)

    add_heading(document, "2.3 Prediction models and statistical analysis", 2)
    add_body(document, "For each dataset, representation values were standardized using the "
             "training compounds or sequences only. Binary and multi-endpoint outcomes were modeled "
             "with L2-regularized logistic regression; continuous outcomes were modeled with ridge "
             "regression. The regularization strength was selected by three-fold cross-validation "
             "within the training data and the selected model was then refitted using all available "
             "non-test observations.")
    add_body(document, "Classification performance was measured by area under the receiver operating "
             "characteristic curve (ROC-AUC). ClinTox and DeepLoc were summarized by the mean ROC-AUC "
             "across their endpoints. ESOL, Lipophilicity and Fluorescence were evaluated by Spearman "
             "correlation. The same measure was used for model selection and final evaluation. "
             "Sensitivity to predictor capacity was examined with a fixed one-hidden-layer neural "
             "network containing 256 ReLU units (L2 penalty 10⁻⁴, batch size 256, learning rate "
             "10⁻³, seed 42 and early stopping). This nonlinear probe was diagnostic: its "
             "hyperparameters were not optimized for individual representations, and it did not "
             "contribute to rankings or statistical comparisons.")

    add_body(document, "One comparison representation was selected for each dataset using validation "
             "performance before the final test results were examined. Promoters lacked a published "
             "validation set, so 10% of its training data was reserved for this purpose. The highest "
             "test score is also reported descriptively, but it was not used to choose the comparison "
             "representation.")
    add_body(document, "Differences between representations were evaluated from paired predictions on "
             "the same test observations. Confidence intervals were obtained by bootstrap resampling. "
             "For molecular datasets, complete Bemis–Murcko scaffold groups were resampled together "
             "to preserve dependence within a chemical series; individual acyclic compounds were kept "
             "as separate groups. DeepLoc test sequences were clustered with MMseqs2 at 30% identity "
             "and 80% bidirectional coverage, and complete homology clusters were resampled [22]. "
             "Promoter observations were resampled individually conditional on the fixed published "
             "chromosome split. At 90% identity and 90% coverage, all Fluorescence test variants "
             "formed one connected component; those differences were therefore reported descriptively "
             "without p-values or population-level claims. Statistical evidence for eligible tests "
             "was estimated by paired randomization with 2,000 repetitions [23]. Holm adjustment "
             f"controlled the family-wise error rate across all {inference['all']['total']} eligible comparisons [24]. A "
             "difference was considered statistically "
             "distinguishable when the adjusted p-value was below 0.05.")

    add_heading(document, "2.4 Robustness, label efficiency and overlap analyses", 2)
    add_body(document, "The six molecular analyses were repeated with 20 prespecified balanced "
             "scaffold partitions. This analysis examined whether the leading representation and "
             "the magnitude of its score depended on the particular allocation of chemical series. "
             "The original partition remained the primary analysis.")
    add_body(document, "To examine measurement precision, the saved test predictions were repeatedly "
             "evaluated on smaller subsets. Molecular subsets retained complete scaffold groups, and "
             "DeepLoc subsets retained complete MMseqs2 homology clusters. The "
             "resulting ranges describe how precisely the present test sets distinguish the methods; "
             "they do not predict the exact benefit of collecting additional compounds.")

    add_body(document, "Label efficiency was examined by refitting the same prediction procedure with "
             "10%, 25%, 50% or 100% of the labeled non-test fitting pool while leaving each test set "
             "fixed. Ten deterministic subsamples were evaluated at each reduced fraction; "
             "the full training set was evaluated once. Molecular subsamples retained complete "
             "Bemis–Murcko scaffold groups so that close chemical series were not divided during label "
             "reduction. Protein and genomic observations were sampled within their published training "
             "partitions. Regularization was selected again within each reduced training set. Results "
             "were summarized as within-cell changes from full-data performance rather than by pooling "
             "scores from different endpoint measures.")
    add_body(document, "For the three SMILES encoders, we also tested an identity-preserving view "
             "averaging procedure. Each source string and nine independently randomized SMILES were "
             "verified to encode the same isomeric structure, embedded separately and averaged to one "
             "vector per molecule before model fitting. This procedure does not create extra labeled "
             "observations and therefore avoids treating alternative strings for the same molecule as "
             "independent samples. It evaluates representation stability to SMILES syntax rather than "
             "synthetic-molecule generation or end-to-end model fine-tuning.")
    add_body(document, "To relate label efficiency to representation geometry, the same deterministic "
             "sample of at most 1,000 molecules per endpoint was used for every available molecular "
             "representation. Neighborhoods were evaluated at k = 5, 10 and 20 using Tanimoto distance "
             "for ECFP4, standardized Euclidean distance for RDKit2D and cosine distance for dense "
             "representations. Endpoint coherence measured local agreement in class labels or local "
             "smoothness of continuous properties after adjustment against random pairs. Scaffold "
             "coherence and recovery of ECFP4 neighbors were recorded as complementary structural "
             "descriptors, not as definitions of a correct representation. Spearman associations were "
             "treated as exploratory and Holm-adjusted within the complete chemical-space analysis "
             "family. UMAP projections used the same compounds in every panel and were included only "
             "for visualization; neighborhood conclusions were based on the original spaces, and map "
             "fidelity was quantified by neighbor recall.")

    add_body(document, f"Molecular test compounds were compared with random samples of "
             f"{exposure['sample_size']:,} structures from ZINC and PubChem. We recorded exact "
             "canonical structure matches, close ECFP4 neighbors (Tanimoto similarity at least "
             "0.9) and shared Bemis–Murcko scaffolds. These database samples approximate possible "
             "structural familiarity; they are not the exact dated training collections of every "
             "model and therefore cannot establish training-set membership or label leakage. "
             "Protein sequences were compared with Swiss-Prot by sequence identity and coverage. "
             "The promoter sequences derive from the human reference genome used by genomic "
             "pretraining collections.")

    add_heading(document, "2.5 Literature alignment and computational reproducibility", 2)
    add_body(document, "Registry records were matched to the measured benchmark only when the named "
             "representation family, endpoint and performance measure were the same. Literature and "
             "measured values were not pooled because dataset processing, the exact scaffold "
             "allocation, model fitting and tuning could still differ. For each eligible pair, we "
             "recorded the direction of the score difference and calculated the Spearman rank "
             "correlation within endpoints containing at least two matches. These correlations are "
             "descriptive; no cross-study significance test or causal attribution to partition "
             "strategy was made. The matching script and its complete output are included in the "
             "public release.")

    add_body(document, "All pretrained model versions and source revisions were fixed before "
             "evaluation. Molecular strings used a maximum model input length of 256; protein and "
             "DNA sequences were limited to 510 biological characters before encoding. Sequence "
             "representations were averaged across valid sequence positions, Uni-Mol across atoms, "
             "and graph representations according to their published implementations. Input files, "
             "representation matrices and software environments were recorded with cryptographic "
             "checksums. The complete provenance record, predictions and analysis code are provided "
             "with the public release.")

    add_heading(document, "3. Results", 1)
    add_heading(document, "3.1 Registry coverage and literature alignment", 2)
    add_body(document, f"The analyzed registry contained {REGISTRY_ENTRY_COUNT} representation "
             f"entries: {REGISTRY_MODALITY_COUNTS['molecular']} molecular, "
             f"{REGISTRY_MODALITY_COUNTS['protein']} protein, "
             f"{prose_count(REGISTRY_MODALITY_COUNTS['complex'])} complex, "
             f"{prose_count(REGISTRY_MODALITY_COUNTS['nucleic-acid'])} nucleic-acid and "
             f"{prose_count(REGISTRY_MODALITY_COUNTS['reaction'])} reaction representation. "
             f"{prose_count(REGISTRY_TYPE_COUNTS['learned']).capitalize()} were learned "
             f"representations, {prose_count(REGISTRY_TYPE_COUNTS['fixed'])} were fixed descriptors "
             f"and {prose_count(REGISTRY_TYPE_COUNTS['hybrid'])} combined learned and fixed "
             f"components. {prose_count(REGISTRY_CODE_COUNT).capitalize()} entries linked executable "
             f"code, "
             f"{REGISTRY_WEIGHTS_COUNT} linked public weights, and "
             f"{REGISTRY_ANY_ARTIFACT_COUNT} provided at least one implementation or "
             f"weight artifact. "
             "These fields allow users to filter representations by scientific domain and practical "
             "requirements without interpreting availability as evidence of predictive superiority.")
    add_body(document, f"The registry contained {registry_summary['benchmark_records']} "
             f"literature-performance records: {registry_summary['molecular_records']} molecular, "
             "14 protein, three complex, two nucleic-acid and one reaction result. Every record "
             "retained a direct source and a protocol note. Six registry entries had no curated "
             "performance record, and those absences were left explicit rather than filled from "
             "secondary summaries. The resulting evidence map established the need to keep the "
             "literature registry separate from the controlled benchmark.")

    add_body(document, f"Among the {registry_summary['molecular_records']} molecular literature "
             f"records, "
             f"{registry_summary['molecular_documented_partition_counts']['scaffold']} were "
             "documented as scaffold-split and four used another or unstated partition; none was "
             "documented as random-split. Matching the registry to the measured benchmark by "
             "representation family, endpoint and "
             f"metric yielded {matched_summary['pairs']} pairs: seven for BBBP and four for CYP3A4. "
             f"All {matched_summary['documented_scaffold_pairs']} matched literature values used "
             "scaffold splits.")
    add_body(document, f"The direction of the difference was mixed: the measured value was higher "
             f"in {prose_count(matched_summary['measured_higher'])} pairs and the literature value in "
             f"{prose_count(matched_summary['literature_higher'])}. Ranking agreement was weak for BBBP "
             f"(Spearman rho = {rank_concordance['BBBP']['spearman_rho']:.2f}, n = "
             f"{rank_concordance['BBBP']['n']}) and negative for CYP3A4 (rho = "
             f"{rank_concordance['CYP3A4']['spearman_rho']:.2f}, n = "
             f"{rank_concordance['CYP3A4']['n']}). These small matched sets do not demonstrate "
             "random-split inflation because all 11 literature results used documented scaffold "
             "splits. Instead, they show that scores and rankings did not transfer consistently when "
             "the broader evaluation protocol changed. The individual matches "
             "and their source-level partition notes are reported in Supplementary Table S2.")

    add_heading(document, "3.2 Molecular-property prediction", 2)
    add_body(document, "The identity of the highest-scoring representation varied across the six "
             "chemical endpoints. ChemBERTa-ZINC produced the highest observed scores for BBBP "
             "(0.971) and ClinTox (0.985), ECFP4 for BACE (0.890), GROVER Large for ESOL "
             "(0.915), GROVER Base for Lipophilicity (0.781), and ChemBERTa-77M for CYP3A4 "
             "substrate classification (0.729). Thus, neither a single pretrained architecture nor "
             "pretraining in general produced the highest score in every dataset.")
    add_body(document, "The conventional baselines remained informative. ECFP4 led the BACE "
             "evaluation, and RDKit2D approached the leading score for ESOL. Conversely, "
             "some pretrained representations performed well on one endpoint and poorly on another. "
             "These results favor endpoint-specific assessment over a global ranking of molecular "
             "representations.")
    add_body(document, "Split diagnostics found no exact-structure or Bemis–Murcko scaffold overlap "
             "between the complete fit and test sets for any molecular endpoint (Supplementary "
             "Table S1). The high "
             "BBBP and ClinTox values therefore cannot be attributed to direct scaffold leakage in "
             "this implementation. They should nevertheless be interpreted with their test-set "
             "sizes and class balances: BBBP contained 205 test compounds across 133 scaffold "
             "groups, whereas each ClinTox endpoint contained only 11 observations in its minority "
             "class among 148 test compounds. The paired intervals and repeated scaffold partitions "
             "are consequently more informative than the point estimates alone.")
    add_body(document, "The molecular performance estimates obtained under the common evaluation "
             "procedure are reported in Table 3.")
    add_caption(document, "Table 3. Molecular-property performance under the common evaluation procedure. BBBP, BACE and CYP3A4 are reported as ROC-AUC; ClinTox as mean ROC-AUC; and ESOL and Lipophilicity as Spearman correlation. † indicates the highest observed score in that dataset; it does not by itself imply a statistically supported difference.")
    add_table(document, ["Representation", "BBBP", "ClinTox", "BACE", "ESOL", "Lipo", "CYP3A4"],
              readable_result_rows(results, paired, TASK_ORDER[:6]),
              widths=[1.55, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7], font_size=10)
    esol_rmse = min(
        (entry["linear"]["rmse"], model)
        for model, entry in results["ESOL"]["models"].items()
    )
    lipo_rmse = min(
        (entry["linear"]["rmse"], model)
        for model, entry in results["Lipophilicity"]["models"].items()
    )
    add_body(document, "Complementary regression errors are reported in Supplementary Table S4. "
             f"RDKit2D had the lowest ESOL RMSE ({esol_rmse[0]:.3f}), whereas GROVER Large had "
             "the highest ESOL rank correlation. GROVER Base had both the lowest Lipophilicity "
             f"RMSE ({lipo_rmse[0]:.3f}) and the highest rank correlation. The ESOL result therefore "
             "illustrates that the numerical leader can depend on whether absolute error or rank "
             "ordering is emphasized.")
    add_body(document, "The corresponding molecular point estimates and confidence intervals are "
             "shown in Figure 2.")
    add_publication_figure(
        document, "figure2_molecular_performance.png", figure_legends["Figure 2"], 5.55
    )

    add_heading(document, "3.3 Protein and genomic extensions", 2)
    add_body(document, "The expanded sequence benchmark was strongly endpoint-dependent. ProTrek "
             "achieved the highest DeepLoc mean ROC-AUC (0.959), followed by ESM-2 650M (0.892) "
             "and CARP (0.887). On Fluorescence, amino-acid triplet frequencies were numerically "
             "highest (Spearman rho = 0.674), followed by ProtBERT (0.662). For promoter recognition, "
             "Caduceus (ROC-AUC = 0.945) and the validation-selected GENA-LM reference (0.944) were "
             "nearly tied; the remaining methods ranged from 0.842 to 0.938.")
    add_body(document, "The numerical results for the protein and genomic extensions are reported "
             "in Table 4.")
    add_caption(document, "Table 4. Performance on the protein and genomic extension datasets. DeepLoc is reported as mean ROC-AUC, Fluorescence as Spearman correlation and Promoters as ROC-AUC. † indicates the highest observed score within a dataset; an em dash denotes a representation from another biological domain.")
    add_table(document, ["Representation", "DeepLoc", "Fluorescence", "Promoters"],
              readable_result_rows(results, paired, ["DeepLoc", "Fluorescence", "Promoters"]),
              widths=[2.3, 1.1, 1.15, 1.1], font_size=10)
    add_body(document, "The extension results and their uncertainty intervals are shown in Figure 3.")
    add_publication_figure(
        document, "figure3_protein_genomic_performance.png",
        figure_legends["Figure 3"], 6.15
    )

    add_heading(document, "3.4 Statistical support, label efficiency and robustness", 2)
    add_body(document, "Statistical support was evaluated relative to the comparison representation "
             "selected using validation data. The dataset-specific results are summarized in Table 5 "
             "and Figure 4A.")
    inference_rows = []
    for task in TASK_ORDER:
        entry = paired[task]
        eligible = [value for value in entry["comparisons"].values()
                    if value.get("inferential", True)]
        significant = sum(bool(value.get("significant_global", value["significant"]))
                          for value in eligible)
        verdict = ("Descriptive only" if entry.get("inference_status") == "descriptive_only"
                   else f"{significant} of {len(eligible)}")
        inference_rows.append([
            task,
            MODEL_LABELS.get(entry["reference"], entry["reference"]),
            MODEL_LABELS.get(entry["observed_test_best"], entry["observed_test_best"]),
            verdict,
        ])
    add_caption(document, f"Table 5. Statistical comparison with the representation selected from validation data. The highest observed test score is descriptive. The final column reports how many eligible alternatives differed after correction across all {inference['all']['total']} formal study comparisons; Fluorescence is descriptive only.")
    add_table(document, ["Dataset", "Preselected comparison", "Highest observed representation", "Statistically distinguishable"],
              inference_rows, widths=[1.0, 1.8, 1.8, 1.35], font_size=10)
    add_body(document, f"Only {inference['molecule']['significant']} of "
             f"{inference['molecule']['total']} molecular comparisons were statistically "
             "distinguishable after correction across the study. Evidence varied markedly by "
             "endpoint: seven of eight comparisons were distinguishable for Lipophilicity, four "
             "of seven for ClinTox, two of eight for ESOL and one of eight for BBBP; none were "
             "distinguishable for BACE or CYP3A4. Numerical ordering alone therefore overstated "
             "the separation among molecular representations in several datasets.")
    fluorescence_comparisons = len(paired["Fluorescence"]["comparisons"])
    add_body(document, f"All {inference['protein']['significant']} of "
             f"{inference['protein']['total']} eligible DeepLoc comparisons remained distinguishable "
             f"when complete homology clusters were resampled. {inference['genomics']['significant']} "
             f"of {inference['genomics']['total']} promoter comparisons remained distinguishable. "
             f"The {fluorescence_comparisons} Fluorescence differences describe the fixed variant "
             "panel and were not included in the formal multiplicity family. Sample size is not the "
             "only determinant of precision: endpoint noise, effect size and dependence among "
             "observations also matter.")
    mlp_cells = [
        (task, model, entry["linear"]["score"], entry["mlp"]["score"],
         entry["linear_mlp_gap"])
        for task in TASK_ORDER
        for model, entry in results[task]["models"].items()
        if "mlp" in entry
    ]
    mlp_higher = sum(gap > 0 for *_, gap in mlp_cells)
    same_leader_tasks = 0
    same_leader_molecular = 0
    for task in TASK_ORDER:
        task_cells = [row for row in mlp_cells if row[0] == task]
        linear_leader = max(task_cells, key=lambda row: row[2])[1]
        mlp_leader = max(task_cells, key=lambda row: row[3])[1]
        if linear_leader == mlp_leader:
            same_leader_tasks += 1
            if results[task]["modality"] == "molecule":
                same_leader_molecular += 1
    add_body(document, "The fixed nonlinear probe is reported in Supplementary Table S3. It exceeded "
             f"the linear score in {mlp_higher} of {len(mlp_cells)} representation–dataset cells; "
             f"the median nonlinear-minus-linear difference was {np.median([row[4] for row in mlp_cells]):+.3f}. "
             f"The leading representation was unchanged in {same_leader_tasks} of nine tasks, "
             f"including {same_leader_molecular} of six molecular tasks. Predictor capacity can "
             "therefore change the exact numerical leader, but the broader conclusions remained: "
             "performance was endpoint-dependent and no representation led every molecular task. "
             "Because the nonlinear probe was fixed rather than tuned per representation, these "
             "comparisons are descriptive and were excluded from formal inference.")
    add_body(document, "Scaffold-partition sensitivity was assessed from the frequency of each "
             "leading representation and the largest score spread across 20 partitions. These "
             "results are summarized in Table 6 and Figure 4B–C.")
    split_rows = []
    for task, entry in sensitivity["tasks"].items():
        ranges = {model: values["range"] for model, values in entry["models"].items()}
        winners = [run["order"][0] for run in entry["runs"]]
        common, frequency = Counter(winners).most_common(1)[0]
        max_model, max_range = max(ranges.items(), key=lambda item: item[1])
        split_rows.append([
            task, MODEL_LABELS.get(common, common), f"{frequency} of {len(winners)}",
            f"{max_range:.3f} ({MODEL_LABELS.get(max_model, max_model)})",
        ])
    n_splits = len(sensitivity["seeds"])
    add_caption(document, f"Table 6. Sensitivity of molecular results to {n_splits} balanced scaffold partitions. Score spread is the largest range observed for any representation within the dataset.")
    add_table(document, ["Dataset", "Most frequent leader", "Partitions led", "Largest score spread"],
              split_rows, widths=[1.0, 1.8, 1.1, 2.15], font_size=10)
    add_publication_figure(
        document, "figure4_inference_and_split_sensitivity.png",
        figure_legends["Figure 4"], 5.65
    )
    winner_frequencies = []
    score_spreads = []
    for task, entry in sensitivity["tasks"].items():
        winners = [run["order"][0] for run in entry["runs"]]
        winner_frequencies.append(Counter(winners).most_common(1)[0][1])
        score_spreads.append((max(values["range"] for values in entry["models"].values()), task))
    min_spread, min_spread_task = min(score_spreads)
    max_spread, max_spread_task = max(score_spreads)
    completely_stable = sum(value == n_splits for value in winner_frequencies)
    add_body(document, f"The same leading representation occurred in all {n_splits} partitions for "
             f"{completely_stable} of six molecular datasets. Across tasks, the most frequent leader "
             f"prevailed in {min(winner_frequencies)} to {max(winner_frequencies)} partitions, and "
             f"the largest within-method score spread ranged from {min_spread:.3f} for "
             f"{min_spread_task} to {max_spread:.3f} for {max_spread_task}. This variation shows "
             "that conclusions based on a single scaffold allocation can be unstable even when "
             "every method is evaluated consistently.")
    add_body(document, "Within the ESM-2 series, larger models improved DeepLoc at each consecutive "
             "step under homology-cluster inference. The fixed Fluorescence panel was non-monotonic: "
             "ESM-2 35M exceeded 8M, 150M fell below 35M, and 650M exceeded 150M. These Fluorescence "
             "differences are descriptive, but together the two endpoints show that model size alone "
             "does not determine observed performance.")

    widths_100, widths_1000 = [], []
    for task in resolution["tasks"].values():
        for comparison in task["comparisons"].values():
            for point in comparison["curve"]:
                if point["requested_n"] == 100:
                    widths_100.append(point["central_95_width"])
                if point["requested_n"] == 1000:
                    widths_1000.append(point["central_95_width"])
    if widths_100:
        text = (f"Across available comparisons, the median width of the empirical 95% range at "
                f"a test-set size of 100 was {np.median(widths_100):.3f}.")
        if widths_1000:
            text += (f" At a test-set size of 1,000 it was {np.median(widths_1000):.3f}. "
                     "Larger test sets generally narrowed the range, although substantial "
                     "differences remained among endpoints.")
        add_body(document, text)
    add_body(document, "The effect of test-set size on the precision of the measured differences "
             "is shown in Figure 5.")
    add_publication_figure(
        document, "figure5_subsampling_resolution.png", figure_legends["Figure 5"], 5.95
    )

    add_body(document, f"Reducing the labeled training set lowered performance in all "
             f"{scarcity_negative[0.10]} representation–task cells at 10% labels and in "
             f"{scarcity_negative[0.25]} of {cell_count} cells at both 25% and 50% labels. "
             f"At 10%, the median within-cell change was "
             f"{scarcity_10_medians['molecule']:+.3f} for molecular tasks, "
             f"{scarcity_10_medians['protein']:+.3f} for protein tasks and "
             f"{scarcity_10_medians['genomics']:+.3f} for the genomic task (Figure 6A). "
             "These modality summaries are descriptive: equal fractions retained different absolute "
             "numbers of observations, and the promoter dataset remained comparatively large even at "
             "10%. The analysis therefore supports within-task label-efficiency comparisons but not a "
             "claim that one biological modality is intrinsically more data-efficient.")
    classification_changes = augmentation_by_type["classification"]
    regression_changes = augmentation_by_type["regression"]
    classification_25 = [
        float(row["mean_change"]) for row in augmentation_25
        if task_types[row["task"]] != "regression"
    ]
    add_body(document, "Randomized-SMILES averaging had an endpoint-dependent effect (Figure 6B). "
             f"At 10% labels, all {len(regression_changes)} encoder–task cases for ESOL and "
             f"Lipophilicity improved, with a median change of "
             f"{np.median(regression_changes):+.3f}. In contrast, only "
             f"{sum(value > 0 for value in classification_changes)} of "
             f"{len(classification_changes)} classification cases improved, and their median change "
             f"was {np.median(classification_changes):+.3f}. All "
             f"{len(classification_25)} classification cases declined at 25% labels. Thus, alternative "
             "SMILES views cannot be treated as a generally beneficial augmentation; their value "
             "depends on the endpoint and performance measure.")
    all_geometry = augmentation_correlations["all"]
    classification_geometry = augmentation_correlations["classification"]
    add_body(document, "The neighborhood analysis provided a possible explanation for this contrast "
             "(Figure 6C–D). View averaging increased endpoint coherence in all six regression "
             f"encoder–task cases (mean change {np.mean(geometry_changes['regression']):+.3f}) but "
             "reduced it across the classification cases on average "
             f"({np.mean(geometry_changes['classification']):+.3f}), driven mainly by ClinTox and "
             "BBBP. Across all 18 augmentation cases at 10% labels, the change in endpoint coherence "
             f"tracked the change in predictive score (Spearman rho = "
             f"{float(all_geometry['spearman_rho']):.2f}; Holm-adjusted p = "
             f"{float(all_geometry['holm_p_value']):.4f}); the association was also retained within "
             f"classification alone (rho = {float(classification_geometry['spearman_rho']):.2f}; "
             f"adjusted p = {float(classification_geometry['holm_p_value']):.4f}). These exploratory "
             "associations do not establish that neighborhood geometry causes predictive performance, "
             "but they show that structural invariance is useful only when endpoint-relevant local "
             "organization is preserved.")
    add_body(document, "The supplementary chemical-space atlas used the same compounds in every panel "
             "(Supplementary Figure S2). The three SMILES language models showed the strongest local "
             f"separation by dataset origin (dataset coherence {min(dataset_coherence[model] for model in ('chemberta_77m', 'chemberta_zinc', 'molformer_xl')):.3f}–"
             f"{max(dataset_coherence[model] for model in ('chemberta_77m', 'chemberta_zinc', 'molformer_xl')):.3f}). "
             "This separation may reflect genuine differences in dataset chemistry, dataset-specific "
             "SMILES conventions or both. Because the two-dimensional maps retained only "
             f"{min(projection_recall):.2f}–{max(projection_recall):.2f} of original-space neighbors "
             "at k = 15, visual clusters were not used for statistical conclusions.")
    add_publication_figure(
        document, "figure6_label_efficiency_and_chemical_space.png",
        figure_legends["Figure 6"], 6.25
    )

    add_heading(document, "3.5 Structural overlap with sampled pretraining sources", 2)
    add_body(document, "Exact molecular matches were rare in the sampled databases: none occurred "
             "in the ZINC sample and one Lipophilicity compound occurred in the PubChem sample. "
             "Close ECFP4 neighbors were also uncommon. Shared scaffolds were more frequent and "
             "strongly endpoint-dependent, ranging from 1.3% for BACE in ZINC to 86.0% for ESOL "
             "in PubChem. Structural familiarity may therefore differ substantially among benchmark "
             "datasets even when exact compound overlap is minimal.")
    add_body(document, "These comparisons use random database samples rather than the exact dated "
             "pretraining collections. They should be interpreted as chemical-overlap context, not "
             "as evidence that test compounds or property labels were memorized during pretraining. "
             "The resulting structural-overlap fractions are shown in Supplementary Figure S1.")

    add_heading(document, "4. Discussion", 1)
    add_body(document, "BioLatent addresses two related but distinct needs. The registry makes a "
             "fragmented representation landscape searchable and preserves the provenance of published "
             "evidence. The measured benchmark provides the controlled comparison that the literature "
             "alone cannot supply. Keeping these layers separate is central to the resource: a "
             "literature value documents what a study reported, whereas a measured value supports "
             "comparison under the BioLatent protocol.")
    add_body(document, "The controlled molecular results did not identify a universal representation. "
             "Chemical language models led BBBP, ClinTox and CYP3A4; ECFP4 led BACE; and pretrained "
             "graph models led ESOL and Lipophilicity. Conventional fingerprints and descriptors "
             "remained strong comparators despite their lower computational cost and greater "
             "familiarity. These findings support endpoint-specific evaluation rather than selecting a "
             "representation from its architecture, scale or published headline score alone.")
    add_body(document, "The label-efficiency analysis reached the same practical conclusion from a "
             "different direction. Performance declined as labels were removed, but no representation "
             "was uniformly most resistant to scarcity. Randomized-SMILES averaging improved both "
             "regression endpoints yet generally harmed classification. Its benefit followed the "
             "preservation of endpoint-relevant neighborhoods rather than increased agreement with "
             "ECFP4 or scaffold grouping alone. A chemically familiar local organization is therefore "
             "not sufficient if it obscures distinctions relevant to the measured property. This "
             "result favors endpoint-specific validation of augmentation choices instead of adopting "
             "them as architecture-wide defaults.")
    add_body(document, "The exact scaffold allocation had a substantial effect on apparent performance. "
             "The leading representation changed across the repeated partitions in every molecular "
             "dataset, with particularly large score variation for ESOL and CYP3A4. A single scaffold "
             "split can therefore favor the chemical series assigned to its test set. Reporting "
             "repeated partitions and uncertainty provides a more reliable basis for method selection "
             "than naming the winner of one split.")
    add_body(document, "The protein and genomic tasks showed why biological dependence must also be "
             "considered. DeepLoc provided clear separation among the evaluated methods when related "
             "sequences were resampled together. Fluorescence formed one connected homology component "
             "at the prespecified threshold and was therefore limited to description of the observed "
             "panel. The promoter methods were numerically close and statistically indistinguishable. "
             "Sample size influenced precision, but sequence relatedness, endpoint noise and effect "
             "magnitude were also important.")
    add_body(document, "The matched literature analysis connects the two BioLatent layers. Even though "
             "all matched literature results used scaffold splits, score differences occurred in both "
             "directions and method rankings changed. The discrepancy cannot be assigned to random "
             "rather than scaffold partitioning. It can arise from the exact scaffold allocation, "
             "dataset processing, endpoint definition, representation extraction, predictor or tuning "
             "procedure. The registry is therefore most useful for discovering methods and tracing "
             "evidence, while the measured benchmark is the appropriate layer for controlled "
             "performance claims.")

    add_heading(document, "5. Limitations", 1)
    add_body(document, "The registry is curated rather than systematic and should not be interpreted "
             "as a complete census of available representations. Coverage differs among scientific "
             "domains, and metadata depend on what authors and artifact repositories report. Links, "
             "licenses and model availability may also change over time. The measured benchmark covers "
             "a selective set of datasets and evaluates each pretrained representation in one fixed "
             "form with a common linear predictor. Its findings describe information accessible under "
             "this protocol, not the maximum performance attainable through alternative layers, pooling "
             "strategies or end-to-end fine-tuning. Statistical inference is further limited by fixed "
             "test sets, a finite set of scaffold partitions and low power in small datasets, "
             "particularly CYP3A4. Uni-Mol was evaluated from one seeded RDKit conformer per molecule; "
             "multi-conformer averaging, alternative force fields and higher-level geometries were "
             "not examined, so its result remains conditional on that conformer-generation protocol.")
    add_body(document, "The sequence, overlap and external-validity analyses also require caution. "
             "Fluorescence describes a fixed panel because the test variants formed one homology "
             "component and therefore does not support a population-level claim. Comparisons with "
             "sampled ZINC, PubChem and Swiss-Prot records indicate possible structural or sequence "
             "familiarity but do not reconstruct model-training data. Generalization was not tested on "
             "an independent external benchmark, and the small, protocol-heterogeneous set of "
             "literature matches supports descriptive comparison only.")
    add_body(document, "The label-efficiency and chemical-space analyses are exploratory extensions. "
             "Fractions do not correspond to equal absolute training sizes across datasets, and the "
             "sequence subsamples were drawn within published training partitions rather than newly "
             "constructed homology groups. SMILES augmentation was limited to averaging ten equivalent "
             "string views for three frozen encoders; it does not cover synthetic-molecule generation, "
             "protein or DNA augmentation, or fine-tuning. ECFP4 neighborhoods are a conventional "
             "structural reference rather than ground truth, and UMAP projections can distort local "
             "relationships. Accordingly, inference was based on original-space metrics and the maps "
             "were used only as visual summaries. The observed correlations do not establish a causal "
             "mechanism and should be tested prospectively on additional endpoints.")

    add_heading(document, "6. Conclusion", 1)
    add_body(document, "BioLatent combines a curated registry of molecular and biological "
             "representations with a standardized benchmark designed for fair comparison. The registry "
             "organizes source-verified evidence and practical model information without treating "
             "heterogeneous literature scores as a common leaderboard. The measured study shows that "
             "molecular performance is endpoint-dependent, conventional features remain competitive, "
             "apparent leaders can change with scaffold allocation, and neither label efficiency nor "
             "SMILES augmentation has a universal winner. Published scores and rankings "
             "did not consistently transfer even among matched scaffold-split studies. BioLatent "
             "therefore provides both a navigable evidence resource and a reproducible experimental "
             "framework for choosing and evaluating representations with appropriate attention to "
             "provenance, uncertainty and dataset partitioning.")

    add_heading(document, "Data and code availability", 1)
    if ZENODO_DOI:
        paragraph = add_body(document, "The benchmark results, test-set predictions and figure "
                             "source data are archived in Zenodo at ")
        add_hyperlink(paragraph, ZENODO_DOI, ZENODO_DOI)
        paragraph.add_run(".")
    else:
        add_body(document, "The benchmark results, test-set predictions and figure source data "
                 "will be deposited in Zenodo; the DOI will be inserted after publication of the "
                 "final versioned record.")
    paragraph = add_body(document, "Source code and manuscript-generation scripts are available in "
                         "the "
                         "BioLatent repository at ")
    add_hyperlink(paragraph, REPOSITORY_URL, REPOSITORY_URL)
    paragraph.add_run(".")
    paragraph = add_body(document, "Raw benchmark datasets and representation matrices are regenerated from "
             "their documented public sources and are not redistributed in the repository. The "
             "release manifest records source checksums, model versions, structure or sequence "
             "processing and software versions. The BioLatent website presents literature-reported "
             "values separately from results generated under the common evaluation procedure and is "
             "available at ")
    add_hyperlink(paragraph, WEBSITE_URL, WEBSITE_URL)
    paragraph.add_run(".")

    add_heading(document, "Declarations", 1)
    add_heading(document, "Funding", 2)
    add_body(document, "This research received no specific grant from any funding agency in the "
             "public, commercial or not-for-profit sectors.")
    add_heading(document, "Author contributions", 2)
    add_body(document, "Yassir Boulaamane conceived and designed the study, developed the "
             "software, curated the data, performed and interpreted the analyses, prepared the "
             "figures, and wrote and revised the manuscript. Michael Fernandez, Christopher M. "
             "Baker, Lea Talmann and Jean-Didier Maréchal reviewed the manuscript and approved "
             "its final version.")
    add_heading(document, "Competing interests", 2)
    add_body(document, "The authors declare no competing interests.")
    add_heading(document, "Acknowledgments", 2)
    add_body(document, "The authors have no acknowledgments to declare.")
    add_heading(document, "Ethics approval and consent to participate", 2)
    add_body(document, "Not applicable. This computational study analyzed public, "
             "non-identifiable benchmark datasets and did not recruit human participants or "
             "use animals.")
    add_heading(document, "Consent for publication", 2)
    add_body(document, "Not applicable.")

    add_heading(document, "References", 1)
    references = [
        ("[1] Rogers D, Hahn M. Extended-connectivity fingerprints. Journal of Chemical Information and Modeling. 2010;50:742-754. ", "https://doi.org/10.1021/ci100050t"),
        ("[2] Chithrananda S, Grand G, Ramsundar B. ChemBERTa: large-scale self-supervised pretraining for molecular property prediction. 2020. ", "https://doi.org/10.48550/arXiv.2010.09885"),
        ("[3] Ross J et al. Large-scale chemical language representations capture molecular structure and properties. Nature Machine Intelligence. 2022;4:1256-1264. ", "https://doi.org/10.1038/s42256-022-00580-7"),
        ("[4] Zhou G et al. Uni-Mol: a universal 3D molecular representation learning framework. ICLR. 2023. ", "https://openreview.net/forum?id=6K2RM6wVqKu"),
        ("[5] Wang Y et al. Molecular contrastive learning of representations via graph neural networks. Nature Machine Intelligence. 2022;4:279-287. ", "https://doi.org/10.1038/s42256-022-00447-x"),
        ("[6] Rong Y et al. Self-supervised graph transformer on large-scale molecular data. NeurIPS. 2020;33:12559-12571. ", "https://doi.org/10.48550/arXiv.2007.02835"),
        ("[7] Yang K et al. Analyzing learned molecular representations for property prediction. Journal of Chemical Information and Modeling. 2019;59:3370-3388. ", "https://doi.org/10.1021/acs.jcim.9b00237"),
        ("[8] Jiang D et al. Could graph neural networks learn better molecular representation for drug discovery? A comparison study of descriptor-based and graph-based models. Journal of Cheminformatics. 2021;13:12. ", "https://doi.org/10.1186/s13321-020-00479-8"),
        ("[9] Wu Z et al. MoleculeNet: a benchmark for molecular machine learning. Chemical Science. 2018;9:513-530. ", "https://doi.org/10.1039/C7SC02664A"),
        ("[10] Huang K et al. Therapeutics Data Commons: machine learning datasets and tasks for therapeutics. NeurIPS Datasets and Benchmarks. 2021. ", "https://doi.org/10.48550/arXiv.2102.09548"),
        ("[11] Sheridan RP. Time-split cross-validation as a method for estimating the goodness of prospective prediction. Journal of Chemical Information and Modeling. 2013;53:783-790. ", "https://doi.org/10.1021/ci400084k"),
        ("[12] Wallach I, Heifets A. Most ligand-based classification benchmarks reward memorization rather than generalization. Journal of Chemical Information and Modeling. 2018;58:916-932. ", "https://doi.org/10.1021/acs.jcim.7b00403"),
        ("[13] Bemis GW, Murcko MA. The properties of known drugs. 1. Molecular frameworks. Journal of Medicinal Chemistry. 1996;39:2887-2893. ", "https://doi.org/10.1021/jm9602928"),
        ("[14] Scalia G et al. Evaluating scalable uncertainty estimation methods for deep learning-based molecular property prediction. Journal of Chemical Information and Modeling. 2020;60:2697-2717. ", "https://doi.org/10.1021/acs.jcim.9b00975"),
        ("[15] Carbon-Mangels M, Hutter MC. Selecting relevant descriptors for classification by Bayesian estimates: a comparison with decision trees and support vector machines approaches for discrimination of CYP3A4 substrates. Molecular Informatics. 2011;30:885-895. ", "https://doi.org/10.1002/minf.201100069"),
        ("[16] Thumuluri V et al. DeepLoc 2.0: multi-label subcellular localization prediction using protein language models. Nucleic Acids Research. 2022;50:W228-W234. ", "https://doi.org/10.1093/nar/gkac278"),
        ("[17] Rao R et al. Evaluating protein transfer learning with TAPE. NeurIPS. 2019. ", "https://doi.org/10.48550/arXiv.1906.08230"),
        ("[18] Dalla-Torre H et al. Nucleotide Transformer: building and evaluating robust foundation models for human genomics. Nature Methods. 2025;22:287-297. ", "https://doi.org/10.1038/s41592-024-02523-z"),
        ("[19] Lin Z et al. Evolutionary-scale prediction of atomic-level protein structure with a language model. Science. 2023;379:1123-1130. ", "https://doi.org/10.1126/science.ade2574"),
        ("[20] Elnaggar A et al. ProtTrans: toward understanding the language of life through self-supervised learning. IEEE TPAMI. 2022;44:7112-7127. ", "https://doi.org/10.1109/TPAMI.2021.3095381"),
        ("[21] Nguyen E et al. HyenaDNA: long-range genomic sequence modeling at single nucleotide resolution. NeurIPS. 2023. ", "https://doi.org/10.48550/arXiv.2306.15794"),
        ("[22] Steinegger M, Söding J. MMseqs2 enables sensitive protein sequence searching for the analysis of massive data sets. Nature Biotechnology. 2017;35:1026-1028. ", "https://doi.org/10.1038/nbt.3988"),
        ("[23] Phipson B, Smyth GK. Permutation p-values should never be zero. Statistical Applications in Genetics and Molecular Biology. 2010;9:Article 39. ", "https://doi.org/10.2202/1544-6115.1585"),
        ("[24] Holm S. A simple sequentially rejective multiple test procedure. Scandinavian Journal of Statistics. 1979;6:65-70. ", "https://www.jstor.org/stable/4615733"),
        ("[25] Ahmad W, Simon E, Chithrananda S, Grand G, Ramsundar B. ChemBERTa-2: towards chemical foundation models. 2022. ", "https://doi.org/10.48550/arXiv.2209.01712"),
        ("[26] Pinto L. Superior molecular representations from intermediate encoder layers. 2025. ", "https://doi.org/10.48550/arXiv.2506.06443"),
        ("[27] Alley EC et al. Unified rational protein engineering with sequence-based deep representation learning. Nature Methods. 2019;16:1315-1322. ", "https://doi.org/10.1038/s41592-019-0598-1"),
        ("[28] Meier J et al. Language models enable zero-shot prediction of the effects of mutations on protein function. NeurIPS. 2021;34. ", "https://proceedings.neurips.cc/paper/2021/hash/f51338d736f95dd42427296047067694-Abstract.html"),
        ("[29] Brandes N et al. ProteinBERT: a universal deep-learning model of protein sequence and function. Bioinformatics. 2022;38:2102-2110. ", "https://doi.org/10.1093/bioinformatics/btac020"),
        ("[30] Yang KK, Fusi N, Lu AX. Convolutions are competitive with transformers for protein sequence pretraining. Cell Systems. 2024;15:286-294. ", "https://doi.org/10.1016/j.cels.2024.01.008"),
        ("[31] Su J et al. A trimodal protein language model enables advanced protein searches. Nature Biotechnology. 2026;44:1310-1316. ", "https://doi.org/10.1038/s41587-025-02836-0"),
        ("[32] Schiff Y et al. Caduceus: bi-directional equivariant long-range DNA sequence modeling. 2024. ", "https://doi.org/10.48550/arXiv.2403.03234"),
        ("[33] Fishman V et al. GENA-LM: a family of open-source foundational DNA language models for long sequences. Nucleic Acids Research. 2025;53:gkae1310. ", "https://doi.org/10.1093/nar/gkae1310"),
        ("[34] Sanabria M et al. DNA language model GROVER learns sequence context in the human genome. Nature Machine Intelligence. 2024;6:911-923. ", "https://doi.org/10.1038/s42256-024-00872-0"),
        ("[35] Zhou Z et al. DNABERT-2: efficient foundation model and benchmark for multi-species genome. 2023. ", "https://doi.org/10.48550/arXiv.2306.15006"),
        ("[36] Nguyen E et al. Sequence modeling and design from molecular to genome scale with Evo. Science. 2024;386:eado9336. ", "https://doi.org/10.1126/science.ado9336"),
        ("[37] Brixi G et al. Genome modelling and design across all domains of life with Evo 2. Nature. 2026;652:1349-1361. ", "https://doi.org/10.1038/s41586-026-10176-5"),
        ("[38] Candido S et al. Language Modeling Materializes a World Model of Protein Biology. bioRxiv. 2026. ", "https://doi.org/10.64898/2026.06.03.729735"),
    ]
    for text, url in references:
        paragraph = document.add_paragraph(
            style=available_style(document, "Bibliography")
        )
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        paragraph.paragraph_format.line_spacing = 1.5
        reference_run = paragraph.add_run(text)
        reference_run.font.name = "Times New Roman"
        reference_run.font.size = Pt(12)
        add_hyperlink(paragraph, url.replace("https://doi.org/", "doi:"), url)

    for section in document.sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)
        add_page_number(section)
    normal = document.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    document.save(OUTPUT)

    supplement = Document()
    clear_body(supplement)
    supplement.core_properties.title = f"Supplementary Information for {PAPER_TITLE}"
    supplement.core_properties.author = (
        "Yassir Boulaamane; Michael Fernandez; Christopher M. Baker; Lea Talmann; "
        "Jean-Didier Maréchal"
    )
    supplement.core_properties.last_modified_by = "Yassir Boulaamane"
    supplement.core_properties.subject = (
        "Supplementary information for the BioLatent registry and measured benchmark"
    )
    supplement.core_properties.keywords = (
        "representation registry, molecular representations, benchmark, supplementary information"
    )
    supplement.core_properties.comments = ""
    for style_name in ("Normal", "Caption"):
        style = supplement.styles[style_name]
        style.font.name = "Times New Roman"
        style.font.size = Pt(9 if style_name == "Caption" else 12)
        style.font.color.rgb = RGBColor(0, 0, 0)
        if style_name == "Caption":
            style.font.bold = False
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    supplement_title = supplement.add_paragraph()
    supplement_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    supplement_title_run = supplement_title.add_run(
        f"Supplementary Information for {PAPER_TITLE}"
    )
    supplement_title_run.font.name = "Times New Roman"
    supplement_title_run.font.size = Pt(14)
    supplement_title_run.bold = True
    supplement_title_run.font.color.rgb = RGBColor(0, 0, 0)
    add_body(
        supplement,
        "This supplement provides molecular split diagnostics, the complete matched comparison "
        "between literature-reported and measured results, diagnostic nonlinear-probe results, "
        "complementary regression errors, structural-overlap analysis and the common-sample "
        "chemical-space atlas. Detailed label-efficiency and neighborhood values are supplied as "
        "machine-readable source data. Reference numbers "
        "follow the main manuscript.",
    )
    add_body(
        supplement,
        "Molecular split composition and fit–test overlap are reported in Table S1.",
    )
    add_caption(
        supplement,
        "Table S1. Molecular split diagnostics. Counts and target summaries are "
        "shown as non-test fit/test. The final column reports exact-structure/scaffold "
        "overlap between the complete fit and test sets.",
    )
    add_table(
        supplement,
        ["Dataset", "n", "Scaffolds", "Fit target", "Test target", "Overlap"],
        diagnostic_rows,
        widths=[0.7, 0.85, 0.9, 1.65, 1.65, 0.75],
    )
    literature_rows = [
        [
            row["representation"],
            row["dataset"],
            row["metric"],
            f"{row['literature_score']:.3f}",
            f"{row['measured_score']:.3f}",
            f"{row['difference_measured_minus_literature']:+.3f}",
            f"{row['literature_source']} "
            f"[{LITERATURE_REFERENCE_NUMBERS[row['literature_source_url']]}]",
        ]
        for row in literature_comparison["matches"]
    ]
    add_caption(
        supplement,
        "Table S2. Descriptive alignment of literature-reported and measured results. "
        "Rows share the same named representation family, endpoint and measure; all literature "
        "records "
        "were documented as scaffold-split. Delta is measured minus literature. Values are "
        "not estimates from the same experiment and were not subjected to cross-study "
        "significance testing.",
    )
    add_table(
        supplement,
        ["Representation", "Endpoint", "Measure", "Literature", "Measured", "Delta", "Source"],
        literature_rows,
        widths=[1.2, 0.75, 0.75, 0.7, 0.7, 0.6, 1.35],
    )
    mlp_rows = [
        [
            task,
            MODEL_LABELS.get(model, model),
            entry["linear"]["metric"],
            f"{entry['linear']['score']:.3f}",
            f"{entry['mlp']['score']:.3f}",
            f"{entry['linear_mlp_gap']:+.3f}",
        ]
        for task in TASK_ORDER
        for model, entry in results[task]["models"].items()
        if "mlp" in entry
    ]
    add_caption(
        supplement,
        "Table S3. Diagnostic comparison of the primary linear probe and a fixed nonlinear "
        "probe. The nonlinear probe contained one hidden layer with 256 ReLU units and identical "
        "hyperparameters for every representation. Delta is nonlinear minus linear performance "
        "on the primary endpoint measure. These values are descriptive and were not used for model "
        "selection, ranking or statistical inference.",
    )
    add_table(
        supplement,
        ["Dataset", "Representation", "Measure", "Linear", "Nonlinear", "Delta"],
        mlp_rows,
        widths=[0.8, 1.55, 1.15, 0.7, 0.8, 0.65],
    )
    regression_rows = [
        [
            task,
            MODEL_LABELS.get(model, model),
            f"{entry['linear']['score']:.3f}",
            f"{entry['linear']['rmse']:.3f}",
            f"{entry['linear']['r2']:.3f}",
        ]
        for task in ("ESOL", "Lipophilicity")
        for model, entry in results[task]["models"].items()
    ]
    add_caption(
        supplement,
        "Table S4. Complementary error measures for the molecular regression datasets under the "
        "primary linear-probe protocol. Spearman correlation is the prespecified ranking measure; "
        "RMSE and R² describe absolute prediction error and explained variance on each endpoint's "
        "native target scale.",
    )
    add_table(
        supplement,
        ["Dataset", "Representation", "Spearman rho", "RMSE", "R²"],
        regression_rows,
        widths=[0.9, 1.8, 1.15, 0.85, 0.7],
    )
    supplement.add_page_break()
    add_publication_figure(
        supplement,
        "figureS1_exposure_proxies.png",
        figure_legends["Figure S1"],
        5.95,
    )
    add_body(
        supplement,
        "The common-compound chemical-space projections are shown in Figure S2; the original-space "
        "neighborhood measurements, rather than apparent two-dimensional separation, support the "
        "analysis in the main text.",
    )
    add_publication_figure(
        supplement,
        "figureS2_chemical_space_atlas.png",
        figure_legends["Figure S2"],
        6.35,
    )
    for section in supplement.sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)
    supplement.save(SUPPLEMENTARY_OUTPUT)
    print(f"Wrote {OUTPUT}")
    print(f"Wrote {SUPPLEMENTARY_OUTPUT}")


if __name__ == "__main__":
    build()
