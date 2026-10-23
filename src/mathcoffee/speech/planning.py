"""Keep published copy separate from explicitly reviewed spoken forms."""

from __future__ import annotations

import re
from copy import deepcopy

HAN = re.compile(r"[\u3400-\u9fff]")
SYLLABLE = re.compile(r"[\u3105-\u312f十月压言阳要阴应用又中穵外万王为文瓮我元云]+[1-5]")
PHONEME_PUNCTUATION = re.compile(r"^[\s/.,:;!?，。；：！？“”‘’、'\"()—…-]*$")
SAFE_ZH = re.compile(r"^[\u3400-\u9fff\s，。；：！？、,.!?;:'\"“”‘’（）()—…-]+$")


class PronunciationError(ValueError):
    """A requested pronunciation cannot be safely aligned or represented."""


def validate_lexicon(lexicon):
    if lexicon.get("schema_version") != 1:
        raise ValueError("unsupported speech lexicon version")
    seen = set()
    for rule in lexicon.get("pronunciations", []):
        phrase = rule["phrase"]
        if not phrase or phrase in seen:
            raise ValueError("pronunciation phrases must be unique and nonempty")
        seen.add(phrase)
        for target in rule["kokoro_targets"]:
            offset = target["offset"]
            if type(offset) is not int or not 0 <= offset < len(phrase):
                raise ValueError("invalid pronunciation character offset")
            if not HAN.fullmatch(phrase[offset]):
                raise ValueError("pronunciation targets must be Chinese characters")
            if not SYLLABLE.fullmatch(target["phoneme"]):
                raise ValueError("Kokoro v1.1 Chinese syllable must end in a tone digit")
    for rule in lexicon.get("aliases", []):
        if not rule.get("source") or not rule.get("spoken"):
            raise ValueError("empty speech alias")
        if rule.get("kind") not in ("spoken_form", "spelling_alias"):
            raise ValueError("speech alias needs an explicit kind")
        if rule.get("boundary", "identifier") not in ("identifier", "number", "formula"):
            raise ValueError("unknown speech alias boundary")


def alias_has_boundary(text, start, end, rule):
    """Do not match inside identifiers, decimal literals or longer equations."""
    source = rule["source"]
    if not (source[0].isascii() and source[0].isalnum()):
        return True
    left = text[start - 1] if start else ""
    right = text[end] if end < len(text) else ""
    if any(c == "_" or (c.isascii() and c.isalnum()) for c in (left, right)):
        return False
    # A sentence-ending dot is valid; a decimal/multi-dot literal is not.
    if right == "." and end + 1 < len(text) and text[end + 1].isdigit():
        return False
    if left == "." and start >= 2 and text[start - 2].isdigit():
        return False
    if rule.get("boundary") == "formula":
        if any(c and c in "+-*/=<>²³^×÷≤≥" for c in (left, right)):
            return False
    return True


def apply_aliases(text, rules, provider):
    """Single left-to-right pass: longer literal phrases win, never recurse."""
    eligible = [r for r in rules if provider in r.get("providers", [])]
    eligible.sort(key=lambda r: (-len(r["source"]), r["source"]))
    output, changes, offset = [], [], 0
    while offset < len(text):
        found = next((r for r in eligible if text.startswith(r["source"], offset)), None)
        if found is None:
            output.append(text[offset])
            offset += 1
            continue
        source = found["source"]
        end = offset + len(source)
        if not alias_has_boundary(text, offset, end, found):
            output.append(text[offset])
            offset += 1
            continue
        output.append(found["spoken"])
        changes.append({"offset": offset, **deepcopy(found)})
        offset = end
    return "".join(output), changes


def pronunciation_targets(text, rules):
    """Prefer the longest matching context at each character, then rule order."""
    targets = {}
    for rule in sorted(rules, key=lambda r: -len(r["phrase"])):
        cursor = 0
        while (start := text.find(rule["phrase"], cursor)) >= 0:
            for target in rule["kokoro_targets"]:
                position = start + target["offset"]
                targets.setdefault(position, {**target, "phrase": rule["phrase"]})
            cursor = start + 1
    return targets


def patch_kokoro_phonemes(text, phonemes, rules):
    """Only patch after a strict one-character/one-syllable alignment.

    Numbers, English, unknown glyphs and erhua contractions are not guessed. The
    caller must normalize/spell them or explicitly split language spans first.
    This applies reviewed syllables, not a universal Chinese pronunciation fix.
    """
    if not SAFE_ZH.fullmatch(text):
        raise PronunciationError("Chinese span has unexpanded symbols, digits or English")
    if not PHONEME_PUNCTUATION.fullmatch(SYLLABLE.sub("", phonemes)):
        raise PronunciationError("unknown symbols or contractions in Chinese phoneme alignment")
    characters, syllables = list(HAN.finditer(text)), list(SYLLABLE.finditer(phonemes))
    if len(characters) != len(syllables):
        raise PronunciationError(
            f"unsafe Chinese alignment: {len(characters)} characters / "
            f"{len(syllables)} syllables; split or review this cue"
        )
    targets, changes = pronunciation_targets(text, rules), []
    for character, syllable in zip(characters, syllables, strict=True):
        target = targets.get(character.start())
        if target is None:
            continue
        changes.append({
            "character_offset": character.start(), "character": character.group(),
            "original": syllable.group(), "corrected": target["phoneme"],
            "expected_pinyin": target["pinyin"], "phrase": target["phrase"],
            "phoneme_start": syllable.start(), "phoneme_end": syllable.end(),
            "changed": syllable.group() != target["phoneme"],
        })
    for change in reversed(changes):
        phonemes = (
            phonemes[:change["phoneme_start"]] + change["corrected"]
            + phonemes[change["phoneme_end"]:]
        )
    return phonemes, changes


def make_plan(case, provider, lexicon):
    validate_lexicon(lexicon)
    if provider not in ("kokoro", "qwen_mlx"):
        raise ValueError(f"unknown provider: {provider}")
    text = case["text"]
    if not isinstance(text, str) or not text.strip():
        raise ValueError("empty narration")
    original_spans = case.get("spans", [{"language": "zh", "text": text}])
    if "".join(s["text"] for s in original_spans) != text:
        raise ValueError("language spans must concatenate exactly to original subtitle text")
    spans, changes = [], []
    for span in original_spans:
        if span["language"] not in ("zh", "en") or not span["text"].strip():
            raise ValueError("language spans must be nonempty zh or en")
        spoken, replacements = apply_aliases(span["text"], lexicon["aliases"], provider)
        spans.append({"language": span["language"], "original": span["text"], "spoken": spoken})
        changes.extend({"span_index": len(spans) - 1, **c} for c in replacements)
    risks = ["pending_human_listening"]
    if provider == "kokoro":
        for span in spans:
            if span["language"] == "zh" and not SAFE_ZH.fullmatch(span["spoken"]):
                raise PronunciationError(
                    "Kokoro Chinese span contains English/digits/symbols; author explicit "
                    "language spans or a reviewed spoken-form alias"
                )
            if span["language"] == "en" and HAN.search(span["spoken"]):
                raise PronunciationError("Chinese text cannot be silently sent to English G2P")
        if any(s["language"] == "en" for s in spans):
            risks.append("explicit_language_splices_may_change_timbre_and_prosody")
    else:
        risks.append("no_hard_phoneme_override_pronunciations_require_listening")
        if re.search(r"[0-9²³=+*/^_]", "".join(s["spoken"] for s in spans)):
            risks.append("unreviewed_numeric_formula_or_identifier_text")
    return {
        "id": case["id"], "subtitle_text": text, "provider": provider,
        "spoken_text": "".join(s["spoken"] for s in spans), "spans": spans,
        "normalization_changes": changes, "expected_readings": case.get("expected_readings", []),
        "review_status": "pending_human_listening", "risks": risks,
        "review_questions": case.get("review_questions", []),
    }
