"""
BioLatent Multi-Modal Benchmark Demo (All 9 Datasets)
=====================================================

Executes the BioLatent Active Benchmark Suite across all 9 multi-modal datasets
(BBBP, ClinTox, BACE, ESOL, Lipophilicity, CYP3A4, DeepLoc, FLIP, Promoters)
using baseline representations (ECFP4, RDKit2D, K-mer).
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from benchmark.eval import run_suite_evaluation, ALL_DATASETS

if __name__ == "__main__":
    print("Executing BioLatent Full 9-Task Multi-Modal Benchmark Suite...")
    run_suite_evaluation(model_or_func="ecfp4", dataset_names=ALL_DATASETS)
