"""Generate the public BioLatent manuscript from committed result artefacts.

The existing ``BioLatent_methods.docx`` is used only as a style and page-layout
template. The source document is never overwritten. Every result table and all
headline counts are computed from JSON so prose cannot silently drift after a
rerun.
"""

import json
import os
from collections import Counter
from pathlib import Path

import numpy as np
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = Path(os.environ.get(
    "BIOLATENT_MANUSCRIPT_TEMPLATE", ROOT / "BioLatent_methods.docx"
))
OUTPUT = ROOT / "paper" / "BioLatent_methods_revised.docx"
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
    properties.extend([color, underline])
    run.append(properties)
    text_element = OxmlElement("w:t")
    text_element.text = text
    run.append(text_element)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def add_heading(document, text, level):
    paragraph = document.add_heading(text, level=level)
    paragraph.paragraph_format.keep_with_next = True
    return paragraph


def add_body(document, text, style=None):
    paragraph = document.add_paragraph(text, style=style)
    paragraph.paragraph_format.space_after = Pt(6)
    paragraph.paragraph_format.line_spacing = 1.08
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
    paragraph.paragraph_format.keep_with_next = True
    return paragraph


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


def fmt(value):
    return f"{float(value):.4f}"


def result_rows(results, tasks):
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
            values.append(fmt(cell["linear"]["score"]) if cell else "N/A")
        rows.append(values)
    return rows


def exposure_text(entry):
    if "measures" in entry:
        measures = entry["measures"]
        return (f"exact {100 * measures['exact_identity']['fraction']:.1f}%; "
                f"near {100 * measures['near_duplicate']['fraction']:.1f}%; "
                f"scaffold {100 * measures['shared_scaffold']['fraction']:.1f}%")
    return f"homology {100 * entry['fraction']:.1f}%"


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
    manifest = load_json("run_manifest.json")
    sensitivity = load_json("split_seed_sensitivity.json")
    resolution = load_json("resolution_curves.json")
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
    document.core_properties.title = (
        "Resolution and uncertainty in a cross-modal frozen-embedding benchmark")
    document.core_properties.author = "Yassir Boulaamane"
    document.core_properties.subject = "BioLatent frozen-embedding benchmark"
    document.core_properties.keywords = (
        "frozen embeddings, molecular representation, protein language model, "
        "genomics, paired randomisation, benchmark uncertainty")

    title = document.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run("What can a frozen-embedding benchmark resolve? ")
    title.add_run("A validation-selected, uncertainty-aware comparison of molecular, "
                  "protein and genomic representations")
    author = document.add_paragraph(
        "Yassir Boulaamane",
        style=available_style(document, "Author", "Subtitle"),
    )
    author.alignment = WD_ALIGN_PARAGRAPH.CENTER
    affiliation = document.add_paragraph(
        "Àrea de Química Física, Departament de Química, Universitat Autònoma de "
        "Barcelona, Cerdanyola del Vallès, Spain")
    affiliation.alignment = WD_ALIGN_PARAGRAPH.CENTER
    email = document.add_paragraph("Correspondence: yassir.boulaamane@uab.cat")
    email.alignment = WD_ALIGN_PARAGRAPH.CENTER

    document.add_paragraph(
        "Abstract", style=available_style(document, "Abstract Title", "Heading 1")
    )
    abstract = (
        f"Published representation leaderboards often combine scores produced under "
        f"different splits, pooling rules and downstream heads. We evaluated {model_count} "
        f"representations in {cell_count} model-task cells across nine molecular, protein "
        f"and genomic tasks under one frozen-embedding protocol. ClinTox was evaluated as "
        f"its two-endpoint task, CYP3A4 used the 667-molecule Carbon-Mangels substrate "
        f"dataset, and DeepLoc 2.0 retained all ten localisation labels and its published "
        f"homology partitions. Transformer embeddings were mean-pooled after excluding "
        f"padding and special tokens; checkpoint revisions and matrix hashes were recorded. "
        f"A standardised linear probe was ranked, while a one-hidden-layer MLP was retained "
        f"only as a diagnostic. The comparison reference was selected on validation data. "
        f"Difference intervals used paired bootstrap resampling, with Murcko scaffolds as "
        f"the molecular resampling unit, and p-values used paired randomisation followed by "
        f"a study-wide Holm correction. {inference['molecule']['significant']} of "
        f"{inference['molecule']['total']} molecular reference comparisons and "
        f"{inference['protein']['significant']} of {inference['protein']['total']} protein "
        f"comparisons survived the primary correction; the genomic count was "
        f"{inference['genomics']['significant']} of {inference['genomics']['total']}. "
        f"Repeated scaffold splits and test-set "
        f"subsampling showed that statistical resolution depends on sample size but also on "
        f"task structure, dependence and effect size. An input-exposure audit reported exact, "
        f"near-duplicate and scaffold proxies separately and did not interpret self-supervised "
        f"input familiarity as label leakage. BioLatent therefore measures linear decodability "
        f"under a specified pooling and truncation protocol, not intrinsic representation "
        f"quality. Its value is a reproducible cross-modal estimate with uncertainty and "
        f"provenance, rather than another single-number leaderboard.")
    document.add_paragraph(
        abstract, style=available_style(document, "Abstract")
    )
    add_body(document, "Keywords: frozen embeddings; linear probing; molecular property "
             "prediction; protein language models; genomic foundation models; paired "
             "randomisation; benchmark uncertainty")

    add_heading(document, "1. Introduction", 1)
    add_body(document, "The same benchmark name can conceal different train-test boundaries, "
             "readout architectures, pooling choices and tuning budgets. MoleculeNet and the "
             "Therapeutics Data Commons standardized important datasets, while TAPE and the "
             "Nucleotide Transformer task suite did the same for proteins and genomes [1-4]. "
             "Those resources do not make scores copied from independent model papers mutually "
             "comparable. A literature registry can preserve provenance, but it cannot remove "
             "protocol heterogeneity after the fact.")
    add_body(document, "Frozen-embedding evaluation reduces one source of variation by fixing "
             "the supervised readout. It does not produce a context-free measure of model "
             "quality. Pooling is itself a consequential modelling choice, as shown by recent "
             "DNA foundation-model benchmarks, and truncation can remove biologically relevant "
             "context [4,5]. The estimand in this study is therefore explicit: how much task "
             "signal is linearly decodable from a particular frozen checkpoint under one mean-"
             "pooling and truncation rule.")
    add_body(document, "We make four methodological changes that are often absent from a ranked "
             "table. First, dataset variants are specified precisely. Second, the comparator is "
             "selected before the test set is examined. Third, uncertainty and paired tests use "
             "dependence-aware resampling and family-wise multiplicity correction. Fourth, "
             "pretraining input exposure is reported as a proxy and is not called label leakage. "
             "The result is intended as an auditable measurement study and web resource, not a "
             "claim that one representation is universally best.")

    add_heading(document, "2. Methods", 1)
    add_heading(document, "2.1 Tasks and dataset variants", 2)
    add_body(document, "Nine per-object prediction tasks were used. MoleculeNet source SMILES "
             "were retained after RDKit validation; they were not canonicalized in a way that "
             "would collapse salts or stereoisomers carrying different source labels. The five "
             "MoleculeNet tasks used a balanced Murcko-scaffold split at seed 42 [1,6]. CYP3A4 "
             "used TDC CYP3A4_Substrate_CarbonMangels and was canonicalized and deduplicated "
             "before TDC scaffold splitting [2,7]. The larger CYP3A4_Veith inhibition dataset "
             "was not substituted for this substrate task.")
    add_body(document, "ClinTox retained FDA_APPROVED and CT_TOX and was ranked by their macro "
             "ROC-AUC. DeepLoc used the DeepLoc 2.0 SwissProt multi-label data and all ten "
             "compartments. Its published homology partitions were assigned in advance as fold "
             "0 test, fold 1 validation and folds 2-4 train [8]. Fluorescence retained the TAPE "
             "extrapolation split [3]. Promoters retained the Nucleotide Transformer chromosome "
             "partition; exact repeats were removed only within a partition [4].")
    task_rows = []
    for task in TASK_ORDER:
        entry = results[task]
        task_rows.append([
            entry.get("dataset_label", task), entry["modality"], entry["task_type"],
            entry["n_total"], entry["n_train"], entry["n_test"],
            entry["split_source"], entry["models"][next(iter(entry["models"]))]["linear"]["metric"],
        ])
    add_caption(document, "Table 1. Benchmark tasks after preprocessing. Counts and labels are read from benchmark_results.json.")
    add_table(document, ["Task", "Modality", "Type", "Total", "Train", "Test", "Split", "Ranked metric"],
              task_rows, widths=[1.15, 0.65, 0.7, 0.5, 0.5, 0.5, 1.3, 0.8], font_size=6.8)

    add_heading(document, "2.2 Frozen representations and provenance", 2)
    add_body(document, "Every model was used only on its native modality. Classical baselines "
             "were ECFP4 and RDKit2D for molecules, amino-acid 3-mer frequencies for proteins, "
             "and DNA 5-mer frequencies for genomes. Neural checkpoints included ChemBERTa, "
             "MoLFormer, Uni-Mol, MolCLR GIN, GROVER Base/Large, four ESM-2 scales, ProtBERT, "
             "Nucleotide Transformer and HyenaDNA [4,9-13,17-19]. The MolCLR-ClinTox cell was "
             "N/A because the checkpoint's native featuriser cannot represent every structure "
             "in that task. Missing cells are not imputed.")
    add_body(document, "All neural checkpoints were pinned to immutable source revisions and "
             "weight hashes. Raw "
             "protein and DNA input was capped at 510 characters before tokenization, and the "
             "token budget was 512 including special tokens; molecular tokenization was capped "
             "at 256. ProtBERT inputs followed its documented U/Z/O/B-to-X mapping. Transformer "
             "outputs were averaged over attention-mask tokens after "
             "tokenizer-designated special tokens were removed. Uni-Mol used mean atom pooling; "
             "MolCLR used its 512-dimensional encoder feature before the contrastive projection "
             "head; GROVER used the official concatenated atom- and bond-view mean fingerprint. "
             "Each sidecar stores the input "
             "hash, matrix hash, revision, dimensions, pooling text, truncation count and the "
             "embedding subprocess software versions. The inference-precision policy and float32 "
             "output-matrix dtype are recorded in the public run manifest, which aggregates these "
             "records.")
    model_rows = []
    seen = set()
    for task in TASK_ORDER:
        for model, sidecar in manifest["tasks"][task]["embeddings"].items():
            if model in seen:
                continue
            seen.add(model)
            model_rows.append([
                MODEL_LABELS.get(model, model), sidecar["kind"], sidecar["modality"],
                sidecar.get("checkpoint") or "deterministic featurizer",
                (sidecar.get("revision") or "not applicable")[:12], sidecar["dim"],
            ])
    add_caption(document, "Table 2. Representation implementations and pinned revisions.")
    add_table(document, ["Representation", "Kind", "Modality", "Checkpoint", "Revision", "Dim"],
              model_rows, widths=[1.15, 0.6, 0.65, 2.35, 0.85, 0.45], font_size=7)

    add_heading(document, "2.3 Probe and metrics", 2)
    add_body(document, "Features were standardized using training-set means and variances only. "
             "The ranked probe was L2-regularized logistic regression for binary or multi-label "
             "classification and ridge regression otherwise. C or alpha was selected by three-"
             "fold training-only cross-validation from one fixed grid. The search used at most "
             "6,000 training rows, selected deterministically, after which the chosen probe was "
             "refit on the complete training split. Classification used ROC-AUC; multi-label "
             "tasks used macro ROC-AUC; regression used Spearman rho both for cross-validation "
             "selection and ranking. Accuracy, macro-F1, RMSE and R-squared were diagnostic.")
    add_body(document, "A one-hidden-layer MLP with 256 ReLU units, alpha 10^-4, batch size 256, "
             "learning rate 10^-3 and early stopping was fit as a non-linear diagnostic. It was "
             "not ranked. Calling this architecture a two-hidden-layer network would be incorrect; "
             "the output layer is not a second hidden layer.")

    add_heading(document, "2.4 Paired inference and multiplicity", 2)
    add_body(document, "The reference representation for each task was chosen by its validation "
             "score. Promoters has no published validation partition, so a deterministic stratified "
             "10% holdout from training was used for reference selection. After reference "
             "selection, every final probe was refit on all non-test labels (training plus "
             "validation where available). The numerical test best was reported "
             "descriptively and was not used to choose the comparator.")
    add_body(document, "A paired bootstrap resampled the same units for both models and formed a "
             "95% percentile interval for their metric difference. Molecular units were Murcko "
             "scaffold clusters; acyclic compounds without a Murcko scaffold were treated as "
             "separate identity units. Protein and genomic units were individual test items. "
             "Two-sided Monte Carlo randomisation p-values were computed from 2,000 null draws by "
             "swapping the two models' predictions within the same units [14]. The primary Holm "
             "correction covered every validation-reference comparison in the nine-task study "
             "[15]. Task-only and modality-only adjusted values were retained as sensitivity "
             "analyses. Consecutive ESM-2 scale steps formed a separate pre-specified family.")

    add_heading(document, "2.5 Split sensitivity and empirical resolution", 2)
    add_body(document, "Molecular split sensitivity was assessed by redrawing the balanced scaffold "
             "split at five pre-specified seeds and refitting each linear probe. These diagnostic "
             "resplits do not replace the primary fixed partition. Separately, saved test predictions "
             "were repeatedly subsampled without replacement at increasing sample sizes. Molecular "
             "subsamples selected whole scaffold groups. The central 95% range and sign consistency "
             "describe stability conditional on the observed test set; they are not a causal "
             "decomposition of differences between modalities.")

    add_heading(document, "2.6 Pretraining input-exposure audit", 2)
    add_body(document, f"Molecular test items were compared with random "
             f"{exposure['sample_size']:,}-molecule ZINC and PubChem database "
             "samples. Exact canonical identity, ECFP4 Tanimoto similarity of at least 0.9, and "
             "Murcko-scaffold identity were reported separately. Because these samples are not the "
             "checkpoints' exact dated training subsets, the fractions are exposure proxies rather "
             "than confirmed membership. Proteins were aligned to Swiss-Prot with MMseqs2 at 50% "
             "identity and 50% coverage as a homology proxy for UniRef50/UniRef100. Promoters derive from the "
             "human reference assembly used in genomic pretraining, so input exposure is structural. "
             "GROVER also declares ChEMBL pretraining, for which no pinned local snapshot was "
             "available; that source is marked unmeasured rather than represented by ZINC. "
             "None of these analyses establishes that downstream labels were present in pretraining.")

    add_heading(document, "2.7 Web implementation", 2)
    add_body(document, "The public interface is implemented in Next.js 16.3.5 and TypeScript. The "
             "Measured Benchmark imports the result JSON directly at build time. Literature values "
             "remain in a separate registry because their protocols are heterogeneous. Headline "
             "counts are computed from the result files rather than hard-coded.")

    add_heading(document, "3. Results", 1)
    add_heading(document, "3.1 Frozen linear-probe performance", 2)
    add_body(document, "Tables 3-5 report the complete ranked linear-probe results. These scores are "
             "internally comparable within this protocol. They should not be substituted for values "
             "from papers that used different splits, pooling, layers or downstream heads.")
    add_caption(document, "Table 3. Molecular ranked metrics. ClinTox is macro ROC-AUC across two endpoints; ESOL and Lipophilicity use Spearman rho; other tasks use ROC-AUC.")
    add_table(document, ["Representation", "BBBP", "ClinTox", "BACE", "ESOL", "Lipo", "CYP3A4"],
              result_rows(results, TASK_ORDER[:6]), widths=[1.45, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7])
    add_caption(document, "Table 4. Protein ranked metrics. DeepLoc 2.0 uses macro ROC-AUC and Fluorescence uses Spearman rho.")
    add_table(document, ["Representation", "DeepLoc 2.0", "Fluorescence"],
              result_rows(results, ["DeepLoc", "Fluorescence"]), widths=[2.2, 1.2, 1.2])
    add_caption(document, "Table 5. Genomic ranked metric. Promoters uses ROC-AUC.")
    add_table(document, ["Representation", "Promoters"],
              result_rows(results, ["Promoters"]), widths=[2.5, 1.2])

    add_heading(document, "3.2 Validation-selected paired comparisons", 2)
    inference_rows = []
    for task in TASK_ORDER:
        entry = paired[task]
        significant = sum(bool(value.get("significant_global", value["significant"]))
                          for value in entry["comparisons"].values())
        inference_rows.append([
            results[task].get("dataset_label", task),
            MODEL_LABELS.get(entry["reference"], entry["reference"]),
            fmt(entry["reference_test_score"]),
            MODEL_LABELS.get(entry["observed_test_best"], entry["observed_test_best"]),
            fmt(entry["observed_test_best_score"]),
            f"{significant}/{len(entry['comparisons'])}", entry["resampling_unit"],
        ])
    add_caption(document, "Table 6. Reference selection and study-wide Holm results. The observed test best is descriptive.")
    add_table(document, ["Task", "Validation reference", "Ref. test", "Numerical test best", "Best test", "Separated", "Unit"],
              inference_rows, widths=[1.0, 1.25, 0.6, 1.25, 0.6, 0.6, 1.0], font_size=6.8)
    add_body(document, f"Across molecular tasks, {inference['molecule']['significant']} of "
             f"{inference['molecule']['total']} reference comparisons survived the primary "
             f"study-wide correction. The protein count was {inference['protein']['significant']} "
             f"of {inference['protein']['total']}, and the genomic count was "
             f"{inference['genomics']['significant']} of {inference['genomics']['total']}. "
             "These counts describe this model roster and these fixed task variants; they are "
             "not evidence that one biological modality is intrinsically easier to benchmark.")

    add_heading(document, "3.3 Scale, split and sample-size sensitivity", 2)
    ladder_rows = []
    for task, entry in paired.items():
        for ladder in entry.get("ladders", {}).values():
            for step, value in ladder["steps"].items():
                ladder_rows.append([task, step.replace("->", " to "), fmt(value["delta"]),
                                    f"[{fmt(value['ci_low'])}, {fmt(value['ci_high'])}]",
                                    f"{value['p_holm']:.4g}", value["direction"]])
    if ladder_rows:
        add_caption(document, "Table 7. Pre-specified ESM-2 scale steps, Holm-corrected within the ladder.")
        add_table(document, ["Task", "Step", "Delta", "95% interval", "Holm p", "Direction"],
                  ladder_rows, widths=[0.9, 1.5, 0.6, 1.3, 0.7, 1.25])

    split_rows = []
    for task, entry in sensitivity["tasks"].items():
        ranges = {model: values["range"] for model, values in entry["models"].items()}
        winners = [run["order"][0] for run in entry["runs"]]
        common, frequency = Counter(winners).most_common(1)[0]
        split_rows.append([task, fmt(max(ranges.values())),
                           MODEL_LABELS.get(common, common), f"{frequency}/{len(winners)}",
                           ", ".join(MODEL_LABELS.get(item, item)
                                     for item in sorted(set(winners)))])
    add_caption(document, "Table 8. Five-seed balanced-scaffold sensitivity. Maximum range is across models within a task.")
    add_table(document, ["Task", "Maximum score range", "Most frequent numerical best", "Frequency", "Observed best models"],
              split_rows, widths=[0.9, 1.0, 1.5, 0.7, 2.3], font_size=7)

    widths_100, widths_1000 = [], []
    for task in resolution["tasks"].values():
        for comparison in task["comparisons"].values():
            for point in comparison["curve"]:
                if point["requested_n"] == 100:
                    widths_100.append(point["central_95_width"])
                if point["requested_n"] == 1000:
                    widths_1000.append(point["central_95_width"])
    if widths_100:
        text = (f"Across available reference comparisons, the median empirical central-range "
                f"width at n=100 was {np.median(widths_100):.4f}.")
        if widths_1000:
            text += (f" At n=1,000 it was {np.median(widths_1000):.4f}. The contraction "
                     "supports test size as a contributor to precision, while the substantial "
                     "between-task spread shows that it is not the sole determinant.")
        add_body(document, text)

    add_heading(document, "3.4 Input-exposure proxies", 2)
    exposure_rows = []
    for task in TASK_ORDER:
        entry = exposure["tasks"].get(task, {})
        empirical = entry.get("empirical", {})
        structural = entry.get("structural", {})
        unmeasured = entry.get("unmeasured", {})
        notes = [value["claim"] for value in structural.values()]
        notes.extend(f"{corpus}: {value['reason']}" for corpus, value in unmeasured.items())
        exposure_rows.append([
            task,
            exposure_text(empirical["zinc"]) if "zinc" in empirical else "N/A",
            exposure_text(empirical["pubchem"]) if "pubchem" in empirical else "N/A",
            exposure_text(empirical["swissprot"]) if "swissprot" in empirical else "N/A",
            "; ".join(notes),
        ])
    add_caption(document, "Table 9. Pretraining input-exposure proxies. Molecular cells report exact, near-duplicate and shared-scaffold fractions separately.")
    add_table(document, ["Task", "ZINC sample", "PubChem sample", "Swiss-Prot", "Structural note"],
              exposure_rows, widths=[0.9, 1.4, 1.4, 1.0, 2.1], font_size=6.8)
    add_body(document, "High exposure-proxy fractions change the interpretation of a frozen "
             "representation score: they indicate that input familiarity may contribute. They "
             "do not demonstrate memorized downstream labels, and a low random-sample fraction "
             "does not prove absence from the checkpoint's exact training corpus.")

    add_heading(document, "4. Discussion", 1)
    add_body(document, "The study has practical value because it turns a literature directory "
             "into an executable measurement protocol with explicit dataset variants, immutable "
             "checkpoint revisions, saved predictions and multiplicity-aware comparisons. It also "
             "makes negative conclusions legible: failure to resolve a difference is not evidence "
             "of equality, but it is stronger and more useful than silently converting numerical "
             "noise into a rank.")
    add_body(document, "The work should not be presented as the first frozen-embedding benchmark. "
             "TAPE, Nucleotide Transformer and recent DNA foundation-model studies already use "
             "frozen or zero-shot embeddings and controlled downstream evaluation [3-5]. The "
             "distinct contribution here is the cross-modal combination of validation-selected "
             "paired inference, dependence-aware molecular resampling, split sensitivity, public "
             "matrix provenance and input-exposure context. This is a methods and resource "
             "contribution rather than a new representation architecture.")
    add_body(document, "The results also reinforce that pooling cannot be treated as neutral. "
             "Mean pooling was fixed to avoid per-model tuning, but recent genomic benchmarking "
             "shows that pooling choice can materially change conclusions [5]. Similarly, a 510-"
             "character cap makes long-protein results conditional on truncated inputs. Frozen "
             "probing measures accessible information after these decisions, not everything that "
             "the pretrained model could express under task-specific adaptation.")

    add_heading(document, "5. Limitations", 1)
    limitations = [
        "The roster is deliberately small and cannot support universal claims about architecture families.",
        "One checkpoint layer and one mean-pooling rule were used. Layer choice, alternative pooling and fine-tuning are outside the estimand.",
        "Bootstrap intervals are conditional on the fixed test partition. Five molecular resplits provide sensitivity evidence but not a full hierarchical variance estimate.",
        "DeepLoc 2.0 uses one pre-specified assignment of five published homology partitions, not the paper's complete five-fold cross-validation average.",
        "The TAPE Fluorescence variants are related. Item-level resampling does not model every mutational dependency, so its intervals may remain optimistic.",
        "The ZINC and PubChem audits use random database samples rather than exact dated checkpoint corpora. Swiss-Prot homology is a proxy for UniRef50/UniRef100 exposure.",
        "Self-supervised input exposure is not label leakage. The study cannot determine whether familiarity helped an individual prediction.",
        "The regularisation search is capped at 6,000 rows for computational parity. This is disclosed because it is part of the protocol.",
        "No external holdout study establishes that conclusions transfer to another benchmark collection.",
    ]
    for item in limitations:
        document.add_paragraph(item, style="List Paragraph").style = document.styles["List Paragraph"]

    add_heading(document, "6. Conclusion", 1)
    add_body(document, "BioLatent is most defensible as an uncertainty-aware benchmark and "
             "provenance resource whose claims remain at the level supported by the design. It compares "
             "linear decodability under one frozen protocol; it does not identify an intrinsically "
             "best representation, prove contamination, or establish that sample size alone causes "
             "cross-modal differences. Reporting the validation-selected comparator, paired "
             "difference interval, multiplicity-adjusted p-value, split sensitivity and input-"
             "exposure proxy is a more defensible unit than a single rank.")

    add_heading(document, "Data and code availability", 1)
    paragraph = add_body(document, "Source code, public result JSON, prediction artefacts and the "
                         "manuscript generator are available in the BioLatent repository: ")
    add_hyperlink(paragraph, "https://github.com/yboulaamane/biolatent",
                  "https://github.com/yboulaamane/biolatent")
    add_body(document, "Raw benchmark datasets and embedding matrices are regenerated from the "
             "pinned sources and checkpoints and are not committed to the web repository. The "
             "public run manifest records dataset hashes, checkpoint revisions, pooling, "
             "truncation and software versions.")

    add_heading(document, "References", 1)
    references = [
        ("[1] Wu Z et al. MoleculeNet: a benchmark for molecular machine learning. Chemical Science. 2018;9:513-530. ", "https://doi.org/10.1039/C7SC02664A"),
        ("[2] Huang K et al. Therapeutics Data Commons: machine learning datasets and tasks for therapeutics. NeurIPS Datasets and Benchmarks. 2021. ", "https://doi.org/10.48550/arXiv.2102.09548"),
        ("[3] Rao R et al. Evaluating protein transfer learning with TAPE. NeurIPS. 2019. ", "https://doi.org/10.48550/arXiv.1906.08230"),
        ("[4] Dalla-Torre H et al. Nucleotide Transformer: building and evaluating robust foundation models for human genomics. Nature Methods. 2025;22:287-297. ", "https://doi.org/10.1038/s41592-024-02523-z"),
        ("[5] Feng H et al. Benchmarking DNA foundation models for genomic and genetic tasks. Nature Communications. 2025;16:10780. ", "https://doi.org/10.1038/s41467-025-65823-8"),
        ("[6] Bemis GW, Murcko MA. The properties of known drugs. 1. Molecular frameworks. Journal of Medicinal Chemistry. 1996;39:2887-2893. ", "https://doi.org/10.1021/jm9602928"),
        ("[7] Carbon-Mangels M, Hutter MC. Selecting relevant descriptors for classification by Bayesian estimates: a comparison with decision trees and support vector machines approaches for discrimination of CYP3A4 substrates. Molecular Informatics. 2011;30:885-895. ", "https://doi.org/10.1002/minf.201100069"),
        ("[8] Thumuluri V et al. DeepLoc 2.0: multi-label subcellular localization prediction using protein language models. Nucleic Acids Research. 2022;50:W228-W234. ", "https://doi.org/10.1093/nar/gkac278"),
        ("[9] Chithrananda S, Grand G, Ramsundar B. ChemBERTa: large-scale self-supervised pretraining for molecular property prediction. 2020. ", "https://doi.org/10.48550/arXiv.2010.09885"),
        ("[10] Ross J et al. Large-scale chemical language representations capture molecular structure and properties. Nature Machine Intelligence. 2022;4:1256-1264. ", "https://doi.org/10.1038/s42256-022-00580-7"),
        ("[11] Lin Z et al. Evolutionary-scale prediction of atomic-level protein structure with a language model. Science. 2023;379:1123-1130. ", "https://doi.org/10.1126/science.ade2574"),
        ("[12] Elnaggar A et al. ProtTrans: toward understanding the language of life through self-supervised learning. IEEE TPAMI. 2022;44:7112-7127. ", "https://doi.org/10.1109/TPAMI.2021.3095381"),
        ("[13] Nguyen E et al. HyenaDNA: long-range genomic sequence modeling at single nucleotide resolution. NeurIPS. 2023. ", "https://doi.org/10.48550/arXiv.2306.15794"),
        ("[14] Phipson B, Smyth GK. Permutation p-values should never be zero. Statistical Applications in Genetics and Molecular Biology. 2010;9:Article 39. ", "https://doi.org/10.2202/1544-6115.1585"),
        ("[15] Holm S. A simple sequentially rejective multiple test procedure. Scandinavian Journal of Statistics. 1979;6:65-70. ", "https://www.jstor.org/stable/4615733"),
        ("[16] Sultan A et al. Transformers for molecular property prediction: domain adaptation efficiently improves performance. Journal of Cheminformatics. 2026;18:107. ", "https://doi.org/10.1186/s13321-026-01252-z"),
        ("[17] Zhou G et al. Uni-Mol: a universal 3D molecular representation learning framework. ICLR. 2023. ", "https://openreview.net/forum?id=6K2RM6wVqKu"),
        ("[18] Wang Y et al. Molecular contrastive learning of representations via graph neural networks. Nature Machine Intelligence. 2022;4:279-287. ", "https://doi.org/10.1038/s42256-022-00447-x"),
        ("[19] Rong Y et al. Self-supervised graph transformer on large-scale molecular data. NeurIPS. 2020;33:12559-12571. ", "https://doi.org/10.48550/arXiv.2007.02835"),
    ]
    for text, url in references:
        paragraph = document.add_paragraph(
            style=available_style(document, "Bibliography")
        )
        paragraph.add_run(text)
        add_hyperlink(paragraph, url.replace("https://doi.org/", "doi:"), url)

    for section in document.sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)
        add_page_number(section)
    normal = document.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(9.5)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    document.save(OUTPUT)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    build()
