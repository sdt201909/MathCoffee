#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
export UV_CACHE_DIR="$PWD/media/reports/agent_upgrade/speech_runtime/uv-cache"
BASE_PYTHON="${SPEECH_BASE_PYTHON:-python3.12}"
if [ ! -x .venv-speech/bin/python ]; then
  uv --no-config venv --python "$BASE_PYTHON" .venv-speech
fi
uv --no-config pip sync --python .venv-speech/bin/python \
  --index-url https://pypi.org/simple --require-hashes \
  toolchains/speech/requirements.lock
