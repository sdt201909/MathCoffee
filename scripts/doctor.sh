#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
readonly SCRIPT_DIR PROJECT_ROOT

# Do not let a diagnostic command download another Python behind the user's back.
export UV_PYTHON_DOWNLOADS=never
export UV_NO_PROGRESS=1

pass() {
    printf '  [ok] %s\n' "$1"
}

fail() {
    printf '\nERROR: %s\n' "$1" >&2
    exit 1
}

require_command() {
    local command_name="$1"
    local install_hint="$2"
    local command_path

    if ! command_path="$(command -v "${command_name}")"; then
        fail "Required command '${command_name}' was not found. ${install_hint}"
    fi
    pass "${command_name}: ${command_path}"
}

printf 'MathCoffee environment doctor\n'
printf 'Project: %s\n\n' "${PROJECT_ROOT}"

printf 'Host architecture\n'
host_arch="$(uname -m)"
if [[ "${host_arch}" != "arm64" ]]; then
    fail "This project requires a native Apple Silicon shell (arm64); uname -m reported '${host_arch}'. If Terminal is running with Rosetta, disable that setting and try again."
fi
pass "native architecture: ${host_arch}"

printf '\nHomebrew\n'
require_command "brew" "Install Apple Silicon Homebrew at /opt/homebrew."
brew_prefix="$(brew --prefix)"
if [[ "${brew_prefix}" != "/opt/homebrew" ]]; then
    fail "Expected the Apple Silicon Homebrew prefix '/opt/homebrew', but brew reported '${brew_prefix}'."
fi
pass "prefix: ${brew_prefix}"

printf '\nProject files and uv\n'
[[ -f "${PROJECT_ROOT}/pyproject.toml" ]] \
    || fail "Missing ${PROJECT_ROOT}/pyproject.toml."
[[ -f "${PROJECT_ROOT}/uv.lock" ]] \
    || fail "Missing ${PROJECT_ROOT}/uv.lock. Run 'make setup' first."
require_command "uv" "Install it with 'brew bundle --file=${PROJECT_ROOT}/Brewfile'."
pass "$(uv --version)"

cd "${PROJECT_ROOT}"
uv_run=(uv run --locked --no-sync)

if ! python_info="$(
    "${uv_run[@]}" python -c \
        'import platform, sys; print(f"{platform.python_version()}|{platform.machine()}|{sys.executable}")'
)"; then
    fail "The locked uv environment is not ready. Run 'make setup' to create and sync ${PROJECT_ROOT}/.venv."
fi
IFS='|' read -r python_version python_arch python_executable <<<"${python_info}"

if [[ "${python_version}" != 3.13.* ]]; then
    fail "Expected uv's project Python to be 3.13.x, but found '${python_version}' at '${python_executable}'."
fi
if [[ "${python_arch}" != "arm64" ]]; then
    fail "Expected uv's project Python to be arm64, but it reported '${python_arch}' at '${python_executable}'."
fi
case "${python_executable}" in
    "${PROJECT_ROOT}/.venv/bin/python" | "${PROJECT_ROOT}/.venv/bin/python3" | "${PROJECT_ROOT}/.venv/bin/python3.13")
        ;;
    *)
        fail "uv is not using this project's .venv; it selected '${python_executable}'. Run 'make setup' and retry."
        ;;
esac
pass "Python ${python_version} (${python_arch}): ${python_executable}"

printf '\nManim and Cairo\n'
if ! manim_version="$(
    "${uv_run[@]}" python -c 'import manim; print(manim.__version__)'
)"; then
    fail "Manim is not importable from the locked uv environment. Run 'make setup'."
fi
if [[ "${manim_version}" != "0.20.1" ]]; then
    fail "Expected Manim 0.20.1, but the project environment contains '${manim_version}'."
fi
pass "Manim ${manim_version}"

require_command "pkg-config" "Install the Homebrew 'pkgconf' formula."
if ! pkg-config --exists cairo; then
    fail "pkg-config cannot resolve Cairo. Install the Homebrew 'cairo' formula, then rerun setup."
fi
pass "Cairo $(pkg-config --modversion cairo)"

printf '\nTeX toolchain\n'
require_command "latex" "Install MacTeX, then ensure /Library/TeX/texbin is on PATH."
require_command "xelatex" "Install a full MacTeX distribution."
require_command "dvisvgm" "Install a full MacTeX distribution."
require_command "kpsewhich" "Install a full MacTeX distribution."
ctex_path="$(kpsewhich ctex.sty || true)"
if [[ -z "${ctex_path}" || ! -f "${ctex_path}" ]]; then
    fail "TeX cannot locate ctex.sty. Install the ctex package (included with full MacTeX)."
fi
pass "ctex: ${ctex_path}"
"${SCRIPT_DIR}/check_tex.sh"

printf '\nJupyter\n'
if ! jupyter_info="$(
    "${uv_run[@]}" python -c \
        'import IPython, ipykernel, jupyterlab; print(f"JupyterLab {jupyterlab.__version__}, IPython {IPython.__version__}, ipykernel {ipykernel.__version__}")'
)"; then
    fail "JupyterLab, IPython, or ipykernel is missing from the locked uv environment."
fi
if ! jupyter_lab_version="$("${uv_run[@]}" jupyter lab --version)"; then
    fail "The JupyterLab command cannot start inside the locked uv environment."
fi
pass "${jupyter_info}"
pass "jupyter lab command: ${jupyter_lab_version}"

printf '\nManim health check\n'
if ! printf 'n\n' | "${uv_run[@]}" manim checkhealth; then
    fail "'uv run --locked --no-sync manim checkhealth' reported a problem."
fi
pass "manim checkhealth completed"

printf '\nAll MathCoffee environment checks passed.\n'
