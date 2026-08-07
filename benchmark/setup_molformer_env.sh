#!/usr/bin/env bash
# Build the compatibility interpreter used only for MoLFormer-XL embedding.
#
# MoLFormer's pinned remote code imports an API available in transformers 5 but
# absent from the main transformers 4.50.3 environment. The embedding runner
# isolates every neural model in a subprocess and records that subprocess's
# Python, torch and transformers versions in the public run manifest, so the
# compatibility environment is explicit rather than hidden.
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
import torch, transformers
import transformers.masking_utils
print(f"transformers {transformers.__version__}, torch {torch.__version__}")
print("masking_utils present")
PY
