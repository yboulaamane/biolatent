# BioLatent figure legends

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
