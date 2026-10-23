"""Auditable visual-label / spoken-reference contract, outside provider code.

Validation compares references, not acoustic pronunciation. It never certifies
that a synthesizer actually said the requested letters; listening is separate.
Use only for authoring that explicitly opts in with figure_label_registry.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy

CONTRACT_VERSION = "figure-label-contract-v1"
_SUBSCRIPTS = "₀₁₂₃₄₅₆₇₈₉"
_NUMERALS = "零一二三四五六七八九"
_GLYPH = re.compile(r"([A-Za-z])([₀-₉]*)(′*)\Z")
_IDENTIFIER = "A-Za-z0-9_"


class FigureLabelError(ValueError):
    """A registered referent was changed, lost or ambiguously represented."""


def _spoken_for_glyph(glyph):
    match = _GLYPH.fullmatch(glyph)
    if not match:
        raise FigureLabelError(f"unsupported figure-label glyph: {glyph!r}")
    letter, subscript, primes = match.groups()
    spoken = letter
    if subscript:
        spoken += " 下标" + subscript.translate(str.maketrans(_SUBSCRIPTS, _NUMERALS))
    return spoken + " 撇" * len(primes)


def registry_from_display_names(names, *, forbidden_aliases=("甲", "乙", "丙")):
    """Create an explicit registry from actual model display names, in order."""
    unique = list(dict.fromkeys(names))
    registry = {
        "schema_version": 1,
        "labels": [{"glyph": name, "spoken": _spoken_for_glyph(name)} for name in unique],
        "forbidden_aliases": list(forbidden_aliases),
    }
    validate_registry(registry)
    return registry


def validate_registry(registry):
    if not isinstance(registry, dict) or registry.get("schema_version") != 1:
        raise FigureLabelError("unsupported figure-label registry schema")
    labels = registry.get("labels")
    if not isinstance(labels, list) or not labels:
        raise FigureLabelError("figure-label registry needs explicit labels")
    mapping = {}
    for label in labels:
        glyph, spoken = label.get("glyph"), label.get("spoken")
        if not isinstance(glyph, str) or glyph in mapping:
            raise FigureLabelError("figure glyphs must be unique nonempty strings")
        if spoken != _spoken_for_glyph(glyph):
            raise FigureLabelError(f"{glyph!r} must preserve its letter, case, subscript and prime")
        mapping[glyph] = spoken
    aliases = registry.get("forbidden_aliases", [])
    if not isinstance(aliases, list) or any(not isinstance(a, str) or not a for a in aliases):
        raise FigureLabelError("forbidden aliases must be explicit nonempty strings")
    if any(a in mapping or a in mapping.values() for a in aliases):
        raise FigureLabelError("forbidden alias conflicts with a registered label")
    return mapping


def registry_sha256(registry):
    validate_registry(registry)
    return hashlib.sha256(
        json.dumps(registry, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _forbid_aliases(text, registry):
    for alias in registry.get("forbidden_aliases", []):
        if alias in text:
            raise FigureLabelError(f"forbidden graph-label alias {alias!r}")


def _letters(mapping):
    # Include case variants to reject case loss rather than silently ignore it.
    return re.escape(
        "".join(sorted({c for glyph in mapping for c in (glyph[0], glyph[0].swapcase())}))
    )


def visual_references(text, registry):
    """Tokenize explicit glyphs; ABC, A2, my_A and English words stay intact."""
    mapping = validate_registry(registry)
    _forbid_aliases(text, registry)
    pattern = re.compile(
        rf"(?<![{_IDENTIFIER}])([{_letters(mapping)}][₀-₉]*[′']*)"
        rf"(?![{_IDENTIFIER}₀-₉′'])"
    )
    result = []
    for match in pattern.finditer(text):
        glyph = match.group()
        if glyph not in mapping:
            raise FigureLabelError(f"unregistered or case/prime-mismatched glyph {glyph!r}")
        result.append({"glyph": glyph, "start": match.start(), "end": match.end()})
    return result


def normalize_figure_labels(text, registry):
    """Expand only exact registered glyphs in one pass, with original offsets."""
    mapping = validate_registry(registry)
    references = visual_references(text, registry)
    pieces, cursor, changes = [], 0, []
    for reference in references:
        start, end = reference["start"], reference["end"]
        spoken = mapping[reference["glyph"]]
        pieces.extend([text[cursor:start], spoken])
        changes.append({**reference, "spoken": spoken})
        cursor = end
    pieces.append(text[cursor:])
    return {"text": "".join(pieces), "references": references, "expansions": changes}


def _spoken_references(text, registry):
    mapping = validate_registry(registry)
    _forbid_aliases(text, registry)
    pattern = re.compile(
        rf"(?<![{_IDENTIFIER}])([{_letters(mapping)}])"
        r"(?:(\s*下标\s*)([零一二三四五六七八九〇十百0-9]+)|([₀-₉]+))?"
        r"((?:\s*[撇′'])*)"
        rf"(?![{_IDENTIFIER}₀-₉′'])"
    )
    result = []
    for match in pattern.finditer(text):
        letter, marker, digits, raw_subscript, prime_text = match.groups()
        if marker:
            if any(c not in _NUMERALS for c in digits):
                raise FigureLabelError(f"noncanonical subscript pronunciation: {match.group()!r}")
            subscript = digits.translate(str.maketrans(_NUMERALS, _SUBSCRIPTS))
        else:
            subscript = raw_subscript or ""
        primes = "′" * sum(c in "撇′'" for c in prime_text)
        glyph = letter + subscript + primes
        raw = match.group()
        if glyph not in mapping or raw != mapping[glyph]:
            raise FigureLabelError(f"noncanonical spoken figure label {raw!r} (referent {glyph!r})")
        result.append({"glyph": glyph, "start": match.start(), "end": match.end(), "spoken": raw})
    return result


def validate_figure_plan(original_text, plan, registry):
    """Reject missing, repeated, reordered, renamed or degraded referents."""
    expected = visual_references(original_text, registry)
    if plan.get("subtitle_text") != original_text:
        raise FigureLabelError("subtitle_text must retain the exact visual-label glyphs")
    spoken_text = plan.get("spoken_text")
    if not isinstance(spoken_text, str):
        raise FigureLabelError("plan requires actual spoken_text")
    spans = plan.get("spans")
    if not isinstance(spans, list) or not spans:
        raise FigureLabelError("plan requires actual normalization spans")
    if "".join(s.get("original", "") for s in spans) != original_text:
        raise FigureLabelError("plan span originals do not preserve subtitle text")
    if "".join(s.get("spoken", "") for s in spans) != spoken_text:
        raise FigureLabelError("plan spoken spans do not concatenate to actual spoken_text")
    actual = _spoken_references(spoken_text, registry)
    expected_labels = [r["glyph"] for r in expected]
    actual_labels = [r["glyph"] for r in actual]
    if expected_labels != actual_labels:
        raise FigureLabelError(
            f"figure referents missing/repeated/reordered/renamed: "
            f"expected {expected_labels!r}, actual {actual_labels!r}"
        )
    return {
        "contract_version": CONTRACT_VERSION,
        "registry_sha256": registry_sha256(registry),
        "visual_references": expected,
        "spoken_references": actual,
        "status": "TEXT_CONTRACT_CHECKED_NOT_LISTENED",
    }


def make_figure_plan(case, provider, lexicon, registry):
    """Opt-in wrapper. Nonlabel plans remain exactly equal to old make_plan."""
    from mathcoffee.speech.planning import make_plan

    original = case["text"]
    normalized = normalize_figure_labels(original, registry)
    if not normalized["references"]:
        plan = make_plan(case, provider, lexicon)
        validate_figure_plan(original, plan, registry)
        return plan
    original_spans = case.get("spans", [{"language": "zh", "text": original}])
    if "".join(s["text"] for s in original_spans) != original:
        raise FigureLabelError("original spans must concatenate exactly to authoring text")
    expanded_spans = []
    for span in original_spans:
        expanded = normalize_figure_labels(span["text"], registry)["text"]
        expanded_spans.append({**deepcopy(span), "text": expanded})
    expanded_text = "".join(s["text"] for s in expanded_spans)
    if expanded_text != normalized["text"]:
        raise FigureLabelError("a registered figure label crosses language-span boundaries")
    expanded_case = {**deepcopy(case), "text": expanded_text, "spans": expanded_spans}
    plan = make_plan(expanded_case, provider, lexicon)
    plan["subtitle_text"] = original
    for span, source in zip(plan["spans"], original_spans, strict=True):
        span["original"] = source["text"]
    audit = validate_figure_plan(original, plan, registry)
    plan["figure_label_audit"] = {
        **audit,
        "expansions": normalized["expansions"],
        # Existing lexicon offsets still refer to these expanded input spans.
        "normalization_input_spans": expanded_spans,
    }
    return plan
