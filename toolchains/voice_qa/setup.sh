#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
export UV_CACHE_DIR="${VOICE_QA_UV_CACHE:-/tmp/mathcoffee-voiceqa-uv-cache}"
if [ ! -x .venv-voice-qa/bin/python ]; then
  uv --no-config venv --python "${VOICE_QA_BASE_PYTHON:-python3.12}" .venv-voice-qa
fi
uv --no-config pip sync --python .venv-voice-qa/bin/python \
  --index-url https://pypi.org/simple --require-hashes toolchains/voice_qa/requirements.lock
