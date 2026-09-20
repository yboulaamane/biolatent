# BioLatent figure legends

## Figure 1. Study design and validated benchmark scope

BioLatent evaluates fixed molecular, protein and genomic representations on nine public datasets. For a given endpoint, every representation is assessed with the same regularised linear prediction procedure. One comparison method is selected using validation data before the test set is examined. Molecular confidence intervals resample Bemis–Murcko scaffolds and DeepLoc intervals resample MMseqs2 homology clusters. Statistical evidence is adjusted across 54 eligible study comparisons; the five Fluorescence comparisons are descriptive because its test variants form one connected homology component at the prespecified threshold. The validated release contains 18 domain-specific representations and 68 model–dataset evaluations, of which 19 of 54 eligible formal comparisons were statistically distinguishable after correction.

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
