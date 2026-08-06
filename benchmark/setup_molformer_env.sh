#!/usr/bin/env bash
# Build the second interpreter that MoLFormer-XL runs in.
#
# Why a second environment exists
# -------------------------------
# MoLFormer-XL ships its modelling code as remote code on the Hub, and that code
# imports `transformers.masking_utils`, which does not exist before transformers
# 5. The rest of the suite is pinned to 4.50.3 (see requirements.txt) and
# upgrading it in place would silently re-run every other model under a
# different library version, invalidating results already computed.
#
# Since embedding already runs in a subprocess per (model, dataset), the model
# simply declares its own interpreter -- see MOLFORMER_ENV in embed.py. Nothing
# else in the pipeline is affected.
#
# The venv inherits system site-packages so torch, numpy and RDKit are shared
# with the main environment; only transformers and tokenizers are overridden.
#
# Usage:  bash benchmark/setup_molformer_env.sh [/path/to/base/python]
# Then point MOLFORMER_ENV in embed.py at the printed interpreter path.

set -euo pipefail

BASE_PYTHON="${1:-$(command -v python)}"
ENV_DIR="${MOLFORMER_ENV_DIR:-$HOME/biolatent_molformer_env}"

echo "Base interpreter: $BASE_PYTHON"
echo "Target venv:      $ENV_DIR"

"$BASE_PYTHON" -m venv --system-site-packages "$ENV_DIR"
"$ENV_DIR/bin/pip" install --quiet --upgrade pip
"$ENV_DIR/bin/pip" install --quiet "transformers==5.14.1" "tokenizers==0.22.2"

"$ENV_DIR/bin/python" - <<'PY'
import transformers, torch
print(f"transformers {transformers.__version__}, torch {torch.__version__}")
import transformers.masking_utils  # the import that fails on 4.x
print("masking_utils present -- MoLFormer-XL remote code will load")
PY

echo
echo "Set MOLFORMER_ENV in benchmark/embed.py to:"
echo "    $ENV_DIR/bin/python"
