#!/usr/bin/env bash

set -euo pipefail

fail() {
    printf '\nERROR: %s\n' "$1" >&2
    exit 1
}

require_command() {
    local command_name="$1"

    if ! command -v "${command_name}" >/dev/null 2>&1; then
        fail "Required TeX command '${command_name}' was not found on PATH."
    fi
}

run_logged() {
    local description="$1"
    local log_file="$2"
    shift 2

    printf '  [check] %s\n' "${description}"
    if ! "$@" >"${log_file}" 2>&1; then
        printf '\nERROR: %s failed. Last 60 log lines:\n' "${description}" >&2
        tail -n 60 "${log_file}" >&2 || true
        return 1
    fi
}

assert_svg() {
    local svg_path="$1"
    local description="$2"

    [[ -s "${svg_path}" ]] \
        || fail "${description} did not produce a non-empty SVG at '${svg_path}'."
    if ! LC_ALL=C grep -q '<svg' "${svg_path}"; then
        fail "${description} produced '${svg_path}', but it does not contain an SVG root element."
    fi
}

for required_command in latex xelatex dvisvgm kpsewhich mktemp; do
    require_command "${required_command}"
done

ctex_path="$(kpsewhich ctex.sty || true)"
if [[ -z "${ctex_path}" || ! -f "${ctex_path}" ]]; then
    fail "ctex.sty is unavailable. A full MacTeX installation should provide it."
fi

temp_root="${TMPDIR:-/tmp}"
temp_root="${temp_root%/}"
[[ -d "${temp_root}" && -w "${temp_root}" ]] \
    || fail "Temporary directory '${temp_root}' does not exist or is not writable."

work_dir="$(mktemp -d "${temp_root}/mathcoffee-tex-check.XXXXXX")"
readonly temp_root work_dir

cleanup() {
    case "${work_dir}" in
        "${temp_root}/mathcoffee-tex-check."*)
            [[ ! -d "${work_dir}" ]] || rm -rf -- "${work_dir}"
            ;;
        *)
            printf 'ERROR: Refusing to clean unexpected temporary path: %s\n' "${work_dir}" >&2
            ;;
    esac
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

cat >"${work_dir}/math.tex" <<'TEX'
\documentclass[preview]{standalone}
\usepackage{amsmath}
\begin{document}
\[
  e^{i\pi} + 1 = 0
\]
\end{document}
TEX

cat >"${work_dir}/chinese.tex" <<'TEX'
\documentclass[preview]{standalone}
\usepackage[UTF8,fontset=fandol]{ctex}
\usepackage{amsmath}
\begin{document}
数学咖啡：$\displaystyle\int_0^1 x^2\,\mathrm{d}x = \frac{1}{3}$
\end{document}
TEX

run_logged \
    "LaTeX mathematics compilation" \
    "${work_dir}/latex-command.log" \
    latex \
    -interaction=nonstopmode \
    -halt-on-error \
    -file-line-error \
    -output-directory="${work_dir}" \
    "${work_dir}/math.tex"

[[ -s "${work_dir}/math.dvi" ]] \
    || fail "LaTeX completed without producing '${work_dir}/math.dvi'."

run_logged \
    "LaTeX DVI to SVG conversion" \
    "${work_dir}/math-dvisvgm.log" \
    dvisvgm \
    --page=1 \
    --no-fonts \
    --output="${work_dir}/math.svg" \
    "${work_dir}/math.dvi"
assert_svg "${work_dir}/math.svg" "LaTeX mathematics conversion"

run_logged \
    "XeLaTeX and ctex compilation" \
    "${work_dir}/xelatex-command.log" \
    xelatex \
    -no-pdf \
    -interaction=nonstopmode \
    -halt-on-error \
    -file-line-error \
    -output-directory="${work_dir}" \
    "${work_dir}/chinese.tex"

[[ -s "${work_dir}/chinese.xdv" ]] \
    || fail "XeLaTeX completed without producing '${work_dir}/chinese.xdv'."

run_logged \
    "XeLaTeX/ctex XDV to SVG conversion" \
    "${work_dir}/chinese-dvisvgm.log" \
    dvisvgm \
    --page=1 \
    --no-fonts \
    --output="${work_dir}/chinese.svg" \
    "${work_dir}/chinese.xdv"
assert_svg "${work_dir}/chinese.svg" "XeLaTeX/ctex conversion"

printf '  [ok] LaTeX math and XeLaTeX/ctex SVG pipelines\n'
