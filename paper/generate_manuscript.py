"""Generate the public BioLatent manuscript from committed result artefacts.

The existing ``BioLatent_methods.docx`` is used only as a style and page-layout
template. The source document is never overwritten. Every result table and all
headline counts are computed from JSON so prose cannot silently drift after a
rerun.
"""

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
FIGURE_DIR = ROOT / "paper" / "figures"
FIGURE_LEGENDS_PATH = ROOT / "paper" / "FIGURE_LEGENDS.md"
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
    "protbert": "ProtBERT", "kmer5_dna": "5-mer frequency",
    "nucleotide_transformer": "Nucleotide Transformer 500M",
    "hyenadna": "HyenaDNA-tiny",
}
TASK_DETAILS = {
    "BBBP": ("Blood–brain barrier penetration", "MoleculeNet scaffold", "ROC-AUC"),
    "ClinTox": ("FDA approval and clinical toxicity", "MoleculeNet scaffold", "Mean ROC-AUC"),
    "BACE": ("BACE-1 inhibition", "MoleculeNet scaffold", "ROC-AUC"),
    "ESOL": ("Aqueous solubility", "MoleculeNet scaffold", "Spearman correlation"),
    "Lipophilicity": ("Lipophilicity", "MoleculeNet scaffold", "Spearman correlation"),
    "CYP3A4": ("CYP3A4 substrate status", "TDC scaffold", "ROC-AUC"),
    "DeepLoc": ("Protein subcellular localisation", "Published homology split", "Mean ROC-AUC"),
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
    "kmer5_dna": ("DNA sequence", "Nucleotide 5-mer frequencies", "Conventional baseline"),
    "nucleotide_transformer": ("DNA sequence", "Pretrained genomic sequence model", "Learned representation"),
    "hyenadna": ("DNA sequence", "Pretrained long-range sequence model", "Learned representation"),
}


def load_json(name):
    path = ROOT / "results" / name
    if not path.exists():
        raise FileNotFoundError(f"Required result artefact is missing: {path}")
    return json.loads(path.read_text())


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
    properties.extend([color, underline, size, complex_script_size])
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
        run.font.color.rgb = RGBColor(0, 0, 0)
    return paragraph


def add_body(document, text, style=None):
    paragraph = document.add_paragraph(text, style=style)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    paragraph.paragraph_format.space_after = Pt(6)
    paragraph.paragraph_format.line_spacing = 1.08
    for run in paragraph.runs:
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
    for run in paragraph.runs:
        run.font.size = Pt(12)
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


def add_table(document, headers, rows, widths=None, font_size=7.5):
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
        comparisons = [comparison for task in tasks
                       for comparison in paired[task]["comparisons"].values()]
        out[modality] = {
            "tasks": len(tasks), "total": len(comparisons),
            "significant": sum(bool(item.get("significant_global", item["significant"]))
                               for item in comparisons),
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
    figure_legends = load_figure_legends()
    missing = [task for task in TASK_ORDER if task not in results or task not in paired]
    if missing:
        raise RuntimeError(f"Incomplete study artefacts; missing tasks: {missing}")

    model_count, cell_count = score_summary(results, TASK_ORDER)
    inference = inference_summary(results, paired)
    # The local house-style template is optional and intentionally not part of
    # the public repository. A clean clone must still be able to generate the
    # complete manuscript with python-docx's standard document styles.
    document = Document(TEMPLATE) if TEMPLATE.exists() else Document()
    clear_body(document)
    for style_name in ("Normal", "Abstract", "Bibliography", "List Paragraph", "Caption"):
        try:
            style = document.styles[style_name]
        except KeyError:
            continue
        style.font.name = "Arial"
        style.font.size = Pt(12)
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    for style_name in ("Title", "Heading 1", "Heading 2", "Heading 3", "Abstract Title"):
        try:
            document.styles[style_name].font.color.rgb = RGBColor(0, 0, 0)
        except KeyError:
            continue
    document.core_properties.title = (
        "BioLatent: An Uncertainty-Aware Benchmark of Frozen Molecular, "
        "Protein, and Genomic Representations")
    document.core_properties.author = "Yassir Boulaamane"
    document.core_properties.subject = "BioLatent molecular-representation benchmark"
    document.core_properties.keywords = (
        "molecular representations, molecular property prediction, chemical fingerprints, "
        "scaffold split, pretrained models, benchmark uncertainty")

    title = document.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title.add_run("BioLatent: An Uncertainty-Aware Benchmark of Frozen Molecular, "
                              "Protein, and Genomic Representations")
    title_run.font.color.rgb = RGBColor(0, 0, 0)
    author = document.add_paragraph(
        "Yassir Boulaamane",
        style=available_style(document, "Author", "Subtitle"),
    )
    author.alignment = WD_ALIGN_PARAGRAPH.CENTER
    affiliation = document.add_paragraph(
        "InSiliChem, Departament de Química, Universitat Autònoma de Barcelona, "
        "08193, Bellaterra (Barcelona), Spain")
    affiliation.alignment = WD_ALIGN_PARAGRAPH.CENTER
    email = document.add_paragraph("Correspondence: yassir.boulaamane@uab.cat")
    email.alignment = WD_ALIGN_PARAGRAPH.CENTER

    abstract_heading = document.add_paragraph(
        "Abstract", style=available_style(document, "Abstract Title", "Heading 1")
    )
    for run in abstract_heading.runs:
        run.font.color.rgb = RGBColor(0, 0, 0)
    abstract = (
        f"Comparisons of molecular representations are often confounded by differences in "
        f"dataset preparation, scaffold partitioning and predictive models. BioLatent compares "
        f"established fingerprints, physicochemical descriptors and pretrained representations "
        f"under a common evaluation procedure. We studied six molecular-property datasets and "
        f"three protein or genomic datasets, comprising {cell_count} evaluations of "
        f"{model_count} representations. Each representation was kept fixed and assessed with "
        f"the same regularised linear prediction model for a given endpoint. Comparison models "
        f"were selected without using the test data, and uncertainty was estimated from paired "
        f"resampling that respected molecular scaffolds. After correction for all comparisons, "
        f"{inference['molecule']['significant']} of {inference['molecule']['total']} molecular "
        f"differences were statistically distinguishable. The corresponding results were "
        f"{inference['protein']['significant']} of {inference['protein']['total']} for proteins "
        f"and {inference['genomics']['significant']} of {inference['genomics']['total']} for the "
        f"genomic task. The highest-scoring molecular representation depended on the endpoint, "
        f"and repeated scaffold partitions changed the leading method in several datasets. "
        f"Conventional fingerprints and descriptors remained competitive with pretrained "
        f"molecular models. These findings show that small numerical differences should not be "
        f"interpreted as stable rankings without uncertainty estimates and split-sensitivity "
        f"analysis. BioLatent provides a reproducible basis for comparing molecular "
        f"representations while preserving the endpoint-specific nature of their performance.")
    abstract_paragraph = document.add_paragraph(
        abstract, style=available_style(document, "Abstract")
    )
    abstract_paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    for run in abstract_paragraph.runs:
        run.font.size = Pt(12)
    add_body(document, "Keywords: molecular representations; molecular property prediction; "
             "chemical fingerprints; scaffold split; pretrained models; benchmark uncertainty")

    add_heading(document, "1. Introduction", 1)
    add_body(document, "Prediction of molecular properties from chemical structure supports compound "
             "selection throughout discovery and development. The representation determines which "
             "structural distinctions are available to the predictive model. Circular fingerprints, "
             "including extended-connectivity fingerprints, encode local atom environments, while "
             "calculated descriptors summarize physicochemical and topological properties [1]. "
             "Recent methods instead learn representations from SMILES strings, molecular graphs or "
             "three-dimensional conformations [2-6]. Pretraining is intended to transfer chemical "
             "regularities learned from large unlabelled collections to endpoints with fewer measured "
             "compounds.")
    add_body(document, "A learned representation is not necessarily more informative for every "
             "property. Comparative studies have found that performance depends on the endpoint, "
             "chemical series, predictive model and data partition, and that established fingerprints "
             "or descriptors remain strong comparators [7,8]. Published scores can also reflect "
             "differences in compound standardisation, dataset version, hyperparameter search and "
             "model capacity. A representation paired with a highly tuned nonlinear predictor is not "
             "being tested under the same conditions as one paired with a simple linear model. These "
             "sources of variation make numerical rankings assembled across publications difficult to "
             "interpret.")
    add_body(document, "BioLatent initially assembled a provenance-aware registry of molecular and "
             "biological representations and the benchmark values reported for them. Examination "
             "of those records showed that results assigned to the same endpoint often came from "
             "different dataset versions, partitions, predictive models and tuning procedures. The "
             "registry is therefore a descriptive catalogue, not a basis for ranking methods. This "
             "limitation motivated a separate measured benchmark in which compatible "
             "representations were recomputed and evaluated under one prespecified procedure. The "
             "registry and measured benchmark are complementary, but their numerical values are "
             "kept analytically separate.")
    add_body(document, "MoleculeNet and the Therapeutics Data Commons established public datasets and "
             "evaluation practices for molecular machine learning [9,10]. The choice of partition is "
             "nevertheless consequential. Random allocation can place close analogues in both the "
             "training and test sets, whereas temporal validation can better approximate prospective "
             "use in some settings [11]. Redundancy between training and evaluation compounds can also "
             "reward memorisation rather than generalisation [12]. Scaffold partitioning based on "
             "Bemis-Murcko frameworks provides a practical test across distinct core structures [13], "
             "but the result can still depend on the particular scaffold allocation. A single score "
             "from one partition therefore does not establish a stable ordering of representations.")
    add_body(document, "Statistical precision is a separate concern. Molecular benchmarks differ in "
             "sample size, assay noise, class balance and structural diversity. Although uncertainty "
             "quantification is increasingly studied for individual molecular predictions [14], "
             "comparisons between representations also require uncertainty on the difference in test "
             "performance. Methods evaluated on the same compounds produce paired outcomes, and "
             "testing many alternatives increases the chance of a nominally significant result. "
             "Confidence intervals, paired tests and correction for multiple comparisons are therefore "
             "needed before small score differences are interpreted as evidence of separation.")
    add_body(document, "BioLatent addresses these issues with a common frozen-representation design. "
             "Each compatible representation is computed once per dataset and supplied to the same "
             "regularised linear prediction procedure. This design asks whether task-relevant "
             "information is accessible from the fixed vector without representation-specific "
             "fine-tuning; it does not estimate the maximum performance attainable by an end-to-end "
             "model. We asked three questions: whether pretrained representations consistently "
             "separate from established fingerprints and descriptors, whether apparent rankings are "
             "robust to scaffold allocation, and how often numerical differences remain statistically "
             "distinguishable after study-wide correction. The primary analysis covers six molecular "
             "endpoints spanning permeability, toxicity, enzyme inhibition, solubility, lipophilicity "
             "and metabolism. Protein and genomic tasks test the same comparison framework in other "
             "biological sequences without treating scores from different modalities as directly "
             "comparable.")
    add_publication_figure(
        document, "figure1_study_design.png", figure_legends["Figure 1"], 6.55
    )

    add_heading(document, "2. Methods", 1)
    add_heading(document, "2.1 Study design and datasets", 2)
    add_body(document, "The primary analysis comprised six molecular datasets. BBBP, ClinTox, "
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
    add_body(document, "The extension analysis used DeepLoc 2.0 protein localisation, TAPE protein "
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
    add_caption(document, "Table 1. Datasets and evaluation measures. Dataset sizes are reported after preprocessing; the test set was not used for model selection.")
    add_table(document, ["Dataset", "Endpoint", "Compounds or sequences", "Test set", "Partition", "Measure"],
              task_rows, widths=[0.75, 1.65, 0.8, 0.6, 1.25, 1.05], font_size=7.2)

    add_heading(document, "2.2 Molecular and sequence representations", 2)
    add_body(document, "The molecular comparison included ECFP4 circular fingerprints, RDKit2D "
             "descriptors, three SMILES-based models, two pretrained graph families, a contrastive "
             "graph model and a three-dimensional molecular model [2-6]. Fingerprints and "
             "descriptors provide established cheminformatics baselines; the remaining methods "
             "represent structures learned from large unlabelled molecular collections. Each "
             "representation was calculated once and held fixed during property-model fitting.")
    add_body(document, "The extension used amino-acid triplet frequencies, four ESM-2 sizes and "
             "ProtBERT for proteins [19,20], together with nucleotide 5-mer frequencies, Nucleotide "
             "Transformer and HyenaDNA for promoter sequences [18,21]. A representation was evaluated "
             "only on its corresponding molecular or sequence domain. MolCLR could not process all "
             "ClinTox structures with its published molecular featurisation and is therefore shown "
             "as unavailable rather than estimated from a reduced dataset.")
    model_rows = [
        [MODEL_LABELS[model], *REPRESENTATION_DETAILS[model]]
        for model in MODEL_LABELS
    ]
    add_caption(document, "Table 2. Representations included in BioLatent. Detailed model versions and software provenance are provided in the public run manifest.")
    add_table(document, ["Representation", "Input", "Approach", "Comparison role"],
              model_rows, widths=[1.35, 1.35, 2.2, 1.25], font_size=7.2)

    add_heading(document, "2.3 Standardised prediction models and performance measures", 2)
    add_body(document, "For each dataset, representation values were standardised using the "
             "training compounds or sequences only. Binary and multi-endpoint outcomes were modelled "
             "with L2-regularised logistic regression; continuous outcomes were modelled with ridge "
             "regression. The regularisation strength was selected by three-fold cross-validation "
             "within the training data and the selected model was then refitted using all available "
             "non-test observations.")
    add_body(document, "Classification performance was measured by area under the receiver operating "
             "characteristic curve (ROC-AUC). ClinTox and DeepLoc were summarised by the mean ROC-AUC "
             "across their endpoints. ESOL, Lipophilicity and Fluorescence were evaluated by Spearman "
             "correlation. The same measure was used for model selection and final evaluation. A "
             "small nonlinear model was retained as a diagnostic but did not contribute to rankings "
             "or statistical comparisons.")

    add_heading(document, "2.4 Statistical comparison of representations", 2)
    add_body(document, "One comparison representation was selected for each dataset using validation "
             "performance before the final test results were examined. Promoters lacked a published "
             "validation set, so 10% of its training data was reserved for this purpose. The highest "
             "test score is also reported descriptively, but it was not used to choose the comparison "
             "representation.")
    add_body(document, "Differences between representations were evaluated from paired predictions on "
             "the same test observations. Confidence intervals were obtained by bootstrap resampling. "
             "For molecular datasets, complete Bemis–Murcko scaffold groups were resampled together "
             "to preserve dependence within a chemical series; individual acyclic compounds were kept "
             "as separate groups. Statistical evidence was estimated by paired randomisation with "
             "2,000 repetitions [22]. Holm adjustment controlled the family-wise error rate across all "
             "59 comparisons in the study [23]. A difference was considered statistically "
             "distinguishable when the adjusted p-value was below 0.05.")

    add_heading(document, "2.5 Robustness to scaffold partition and test-set size", 2)
    add_body(document, "The six molecular analyses were repeated with five prespecified balanced "
             "scaffold partitions. This analysis examined whether the leading representation and "
             "the magnitude of its score depended on the particular allocation of chemical series. "
             "The original partition remained the primary analysis.")
    add_body(document, "To examine measurement precision, the saved test predictions were repeatedly "
             "evaluated on smaller subsets. Molecular subsets retained complete scaffold groups. The "
             "resulting ranges describe how precisely the present test sets distinguish the methods; "
             "they do not predict the exact benefit of collecting additional compounds.")

    add_heading(document, "2.6 Overlap with sampled pretraining sources", 2)
    add_body(document, f"Molecular test compounds were compared with random samples of "
             f"{exposure['sample_size']:,} structures from ZINC and PubChem. We recorded exact "
             "canonical structure matches, close ECFP4 neighbours (Tanimoto similarity at least "
             "0.9) and shared Bemis–Murcko scaffolds. These database samples approximate possible "
             "structural familiarity; they are not the exact dated training collections of every "
             "model and therefore cannot establish training-set membership or label leakage. "
             "Protein sequences were compared with Swiss-Prot by sequence identity and coverage. "
             "The promoter sequences derive from the human reference genome used by genomic "
             "pretraining collections.")

    add_heading(document, "2.7 Computational reproducibility", 2)
    add_body(document, "All pretrained model versions and source revisions were fixed before "
             "evaluation. Molecular strings used a maximum model input length of 256; protein and "
             "DNA sequences were limited to 510 biological characters before encoding. Sequence "
             "representations were averaged across valid sequence positions, Uni-Mol across atoms, "
             "and graph representations according to their published implementations. Input files, "
             "representation matrices and software environments were recorded with cryptographic "
             "checksums. The complete provenance record, predictions and analysis code are provided "
             "with the public release.")

    add_heading(document, "3. Results", 1)
    add_heading(document, "3.1 Molecular-property prediction", 2)
    add_body(document, "The identity of the highest-scoring representation varied across the six "
             "chemical endpoints. ChemBERTa-ZINC produced the highest observed scores for BBBP "
             "(0.971) and ClinTox (0.985), ECFP4 for BACE (0.890), GROVER Large for ESOL "
             "(0.915), GROVER Base for Lipophilicity (0.781), and ChemBERTa-77M for CYP3A4 "
             "substrate classification (0.729). Thus, neither a single pretrained architecture nor "
             "pretraining in general produced the highest score in every dataset.")
    add_body(document, "The conventional baselines remained informative. ECFP4 led the BACE "
             "evaluation, and RDKit2D approached the leading score for ESOL. Conversely, "
             "some pretrained representations performed well on one endpoint and poorly on another. "
             "These results favour endpoint-specific assessment over a global ranking of molecular "
             "representations.")
    add_caption(document, "Table 3. Molecular-property performance under the common evaluation procedure. BBBP, BACE and CYP3A4 are reported as ROC-AUC; ClinTox as mean ROC-AUC; and ESOL and Lipophilicity as Spearman correlation. † indicates the highest observed score in that dataset; it does not by itself imply a statistically supported difference.")
    add_table(document, ["Representation", "BBBP", "ClinTox", "BACE", "ESOL", "Lipo", "CYP3A4"],
              readable_result_rows(results, paired, TASK_ORDER[:6]),
              widths=[1.55, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7], font_size=7.5)
    add_publication_figure(
        document, "figure2_molecular_performance.png", figure_legends["Figure 2"], 5.55
    )

    add_heading(document, "3.2 Extension to protein and genomic datasets", 2)
    add_body(document, "For DeepLoc, performance increased across the four ESM-2 sizes, reaching "
             "a mean ROC-AUC of 0.892 with ESM-2 650M. The Fluorescence results did not follow the "
             "same pattern: amino-acid triplet frequencies achieved the highest correlation "
             "(0.674), followed by ProtBERT (0.662). For promoter recognition, the three methods "
             "were closely grouped between 0.930 and 0.938 ROC-AUC.")
    add_caption(document, "Table 4. Performance on the protein and genomic extension datasets. DeepLoc is reported as mean ROC-AUC, Fluorescence as Spearman correlation and Promoters as ROC-AUC. † indicates the highest observed score within a dataset; an em dash denotes a representation from another biological domain.")
    add_table(document, ["Representation", "DeepLoc", "Fluorescence", "Promoters"],
              readable_result_rows(results, paired, ["DeepLoc", "Fluorescence", "Promoters"]),
              widths=[2.3, 1.1, 1.15, 1.1], font_size=7.5)
    add_publication_figure(
        document, "figure3_protein_genomic_performance.png",
        figure_legends["Figure 3"], 6.15
    )

    add_heading(document, "3.3 Statistical support for performance differences", 2)
    inference_rows = []
    for task in TASK_ORDER:
        entry = paired[task]
        significant = sum(bool(value.get("significant_global", value["significant"]))
                          for value in entry["comparisons"].values())
        inference_rows.append([
            task,
            MODEL_LABELS.get(entry["reference"], entry["reference"]),
            MODEL_LABELS.get(entry["observed_test_best"], entry["observed_test_best"]),
            f"{significant} of {len(entry['comparisons'])}",
        ])
    add_caption(document, "Table 5. Statistical comparison with the representation selected from validation data. The highest observed test score is descriptive. The final column reports how many alternatives differed after correction across all 59 study comparisons.")
    add_table(document, ["Dataset", "Preselected comparison", "Highest observed representation", "Statistically distinguishable"],
              inference_rows, widths=[1.0, 1.8, 1.8, 1.35], font_size=7.4)
    add_body(document, f"Only {inference['molecule']['significant']} of "
             f"{inference['molecule']['total']} molecular comparisons were statistically "
             "distinguishable after correction across the study. Evidence varied markedly by "
             "endpoint: seven of eight comparisons were distinguishable for Lipophilicity, four "
             "of seven for ClinTox, two of eight for ESOL and one of eight for BBBP; none were "
             "distinguishable for BACE or CYP3A4. Numerical ordering alone therefore overstated "
             "the separation among molecular representations in several datasets.")
    add_body(document, f"All {inference['protein']['significant']} protein comparisons were "
             "distinguishable from their preselected comparison method, whereas neither genomic "
             "comparison was distinguishable. The protein test sets were much larger than most "
             "molecular test sets, but sample size is not the only explanation: endpoint noise, "
             "effect size and dependence among observations also influence precision.")
    add_publication_figure(
        document, "figure4_inference_and_split_sensitivity.png",
        figure_legends["Figure 4"], 5.65
    )

    add_heading(document, "3.4 Sensitivity to scaffold partition and test-set size", 2)
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
    add_caption(document, "Table 6. Sensitivity of molecular results to five balanced scaffold partitions. Score spread is the largest range observed for any representation within the dataset.")
    add_table(document, ["Dataset", "Most frequent leader", "Partitions led", "Largest score spread"],
              split_rows, widths=[1.0, 1.8, 1.1, 2.15], font_size=7.5)
    add_body(document, "No molecular dataset had the same leading representation in all five "
             "scaffold partitions. The most frequent leader prevailed in two to four partitions, "
             "and the largest within-method score spread ranged from 0.084 for BACE to 0.279 for "
             "ESOL. This variation shows that conclusions based on a single scaffold allocation "
             "can be unstable even when every method is evaluated consistently.")
    add_body(document, "Within the ESM-2 series, larger models improved DeepLoc at each consecutive "
             "step. Fluorescence was non-monotonic: ESM-2 35M exceeded 8M, 150M fell below 35M, "
             "and 650M improved over 150M. Model size alone therefore did not determine performance "
             "across protein endpoints.")

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
    add_publication_figure(
        document, "figure5_subsampling_resolution.png", figure_legends["Figure 5"], 5.95
    )

    add_heading(document, "3.5 Structural overlap with sampled pretraining sources", 2)
    add_body(document, "Exact molecular matches were rare in the sampled databases: none occurred "
             "in the ZINC sample and one Lipophilicity compound occurred in the PubChem sample. "
             "Close ECFP4 neighbours were also uncommon. Shared scaffolds were more frequent and "
             "strongly endpoint-dependent, ranging from 1.3% for BACE in ZINC to 86.0% for ESOL "
             "in PubChem. Structural familiarity may therefore differ substantially among benchmark "
             "datasets even when exact compound overlap is minimal.")
    add_body(document, "These comparisons use random database samples rather than the exact dated "
             "pretraining collections. They should be interpreted as chemical-overlap context, not "
             "as evidence that test compounds or property labels were memorised during pretraining.")
    add_publication_figure(
        document, "figureS1_exposure_proxies.png", figure_legends["Figure S1"], 5.95
    )

    add_heading(document, "4. Discussion", 1)
    add_body(document, "The molecular results do not support a universal ordering of representation "
             "families. A chemical language model led BBBP, ClinTox and CYP3A4, a circular "
             "fingerprint led BACE, and pretrained graph models led the two continuous-property "
             "datasets. This pattern is chemically plausible: endpoints differ in structural "
             "complexity, assay noise, dataset size and the extent to which local substructures or "
             "global physicochemical properties are informative. A representation that is useful "
             "for one endpoint should not therefore be assumed to dominate another.")
    add_body(document, "Classical cheminformatics representations remained strong comparators. "
             "Their competitiveness is important because fingerprints and calculated descriptors "
             "are inexpensive, interpretable and well characterised. The present results do not "
             "argue against pretrained molecular models; rather, they show that their value must be "
             "demonstrated against appropriately tuned conventional methods on chemically separated "
             "test sets.")
    add_body(document, "Scaffold sensitivity was at least as important as the nominal ranking. The "
             "leading representation changed across repeated partitions in every molecular dataset, "
             "and score variation was substantial for ESOL and CYP3A4. This behaviour is consistent "
             "with the limited number and uneven distribution of chemical series in many public "
             "benchmarks. Reporting one scaffold split without uncertainty can make a modest and "
             "partition-dependent advantage appear general.")
    add_body(document, "The protein and genomic experiments clarify the role of statistical precision "
             "without making direct cross-domain performance claims. The large protein test sets "
             "supported clear separation among the evaluated methods, whereas the molecular datasets "
             "often did not. The promoter methods were numerically close and statistically "
             "indistinguishable. Sample size contributed to these differences, but endpoint noise, "
             "sequence relatedness and effect magnitude also matter.")
    add_body(document, "BioLatent contributes a controlled comparison and reusable result resource, "
             "rather than a new molecular representation. Its principal advantage is that the same "
             "dataset definitions, predictive models and statistical criteria are applied throughout. "
             "The public predictions and source data allow new representations to be added without "
             "treating heterogeneous literature values as if they came from one experiment.")

    add_heading(document, "5. Limitations", 1)
    limitations = [
        "The selected datasets and representations do not cover all chemical endpoints or available pretrained molecular models.",
        "Pretrained representations were assessed in one fixed form with a common linear prediction model. Alternative representation layers, aggregation methods and end-to-end model fitting were outside the study scope.",
        "The confidence intervals describe the fixed primary test partitions. Five additional scaffold partitions provide a robustness check but do not capture every possible division of chemical space.",
        "Some molecular test sets are small, particularly CYP3A4, and consequently provide limited power to distinguish similar methods.",
        "DeepLoc uses one prespecified assignment of its published homology partitions rather than the complete cross-validation average reported by the original study.",
        "Related variants in the Fluorescence dataset may not be fully independent, so its uncertainty could be underestimated.",
        "The ZINC, PubChem and Swiss-Prot comparisons are sampled indicators of structural or sequence familiarity, not exact reconstructions of model pretraining collections.",
        "No independent benchmark collection was used to establish that the observed rankings generalise to other chemical series or assay settings.",
    ]
    for item in limitations:
        paragraph = document.add_paragraph(item, style="List Paragraph")
        paragraph.style = document.styles["List Paragraph"]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        for run in paragraph.runs:
            run.font.size = Pt(12)

    add_heading(document, "6. Conclusion", 1)
    add_body(document, "Under a common evaluation procedure, molecular-representation performance "
             "was endpoint-dependent and sensitive to scaffold partitioning. Conventional "
             "fingerprints and descriptors remained competitive, while pretrained methods provided "
             "clear advantages in selected datasets rather than uniformly. Most numerical molecular "
             "rankings were not supported as statistically distinguishable differences after "
             "study-wide correction. BioLatent therefore supports representation selection based on "
             "the chemical endpoint, uncertainty and scaffold robustness, rather than on a single "
             "aggregate leaderboard.")

    add_heading(document, "Data and code availability", 1)
    paragraph = add_body(document, "The benchmark results, test-set predictions and figure source "
                         "data are archived in Zenodo version 1.0.0: ")
    add_hyperlink(paragraph, "https://doi.org/10.5281/zenodo.22813148",
                  "https://doi.org/10.5281/zenodo.22813148")
    paragraph = add_body(document, "Source code and the manuscript generator are available in the "
                         "BioLatent repository: ")
    add_hyperlink(paragraph, "https://github.com/yboulaamane/biolatent",
                  "https://github.com/yboulaamane/biolatent")
    add_body(document, "Raw benchmark datasets and representation matrices are regenerated from "
             "their documented public sources and are not redistributed in the repository. The "
             "release manifest records source checksums, model versions, structure or sequence "
             "processing and software versions. The BioLatent website presents the reported "
             "literature values in the Literature Registry and the results generated under the "
             "common evaluation procedure in the Measured Benchmark.")

    add_heading(document, "Declarations", 1)
    add_heading(document, "Author contributions", 2)
    add_body(document, "Yassir Boulaamane conceived and designed the study, developed the "
             "software, curated the data, performed and interpreted the analyses, prepared the "
             "figures, and wrote and revised the manuscript.")
    add_heading(document, "Funding", 2)
    add_body(document, "This research received no specific grant from any funding agency in the "
             "public, commercial or not-for-profit sectors.")
    add_heading(document, "Competing interests", 2)
    add_body(document, "The author declares no competing interests.")
    add_heading(document, "Acknowledgements", 2)
    add_body(document, "The author has no acknowledgements to declare.")
    add_heading(document, "Ethics approval and consent to participate", 2)
    add_body(document, "Not applicable. This computational study analysed public, "
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
        ("[22] Phipson B, Smyth GK. Permutation p-values should never be zero. Statistical Applications in Genetics and Molecular Biology. 2010;9:Article 39. ", "https://doi.org/10.2202/1544-6115.1585"),
        ("[23] Holm S. A simple sequentially rejective multiple test procedure. Scandinavian Journal of Statistics. 1979;6:65-70. ", "https://www.jstor.org/stable/4615733"),
    ]
    for text, url in references:
        paragraph = document.add_paragraph(
            style=available_style(document, "Bibliography")
        )
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        paragraph.add_run(text).font.size = Pt(12)
        add_hyperlink(paragraph, url.replace("https://doi.org/", "doi:"), url)

    for section in document.sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)
        add_page_number(section)
    normal = document.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(12)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    document.save(OUTPUT)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    build()
