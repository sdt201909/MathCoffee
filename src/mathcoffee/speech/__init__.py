"""Offline, provider-specific narration planning and synthesis.

Heavy speech runtimes are imported only when a provider is instantiated. Planning
and pronunciation tests therefore run in the ordinary Manim environment.
"""

from .planning import PronunciationError, make_plan, patch_kokoro_phonemes

__all__ = ["PronunciationError", "make_plan", "patch_kokoro_phonemes"]
