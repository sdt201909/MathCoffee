# MathCoffee candidate style baseline v1

English | [简体中文](style_baseline.zh-CN.md)

Both presets were extracted from the current local production conventions and
implemented as new generic components. No historical episode scenes, scripts,
or media were copied. Presets remain `pending_author_confirmation`: only review
of calibration videos and real listening can establish that the default style
has the author's approval. Custom presets record a diff and are evaluated on
their own results.

| Setting | Shorts | Longform |
|---|---|---|
| Final canvas | 1080×1920 / 60 fps | 1920×1080 / 60 fps |
| Draft canvas | 540×960 / 30 fps | 960×540 / 30 fps |
| Background | #070C13 | #07111B |
| Objects A / B | #4EA1FF / #70E1E8 | #65B7EE / #72D5D6 |
| Result / emphasis | #FFD166 | #F0C777 |
| Body text | #F4F7FB | #EFF4F5 |
| Font | Heiti SC with an explicit fallback chain | Heiti SC with an explicit fallback chain |
| Core formula hold | At least 6 seconds | At least 4 seconds |
| Conclusion hold | At least 6 seconds | At least 6 seconds |
| Burned-in narration captions by default | Off | On |

Pair colors with text or values; do not encode a condition through color alone.
Titles, branding, diagrams, formulas, and captions use the same pixel-based
configuration, scaled to the canvas. A topic is not forced into three columns
or a fixed chapter count. Remotion text budgets reject overflow without
truncating text. Manim component bounds and fitting ratios are recorded, and
excessive shrinking is rejected. Actual font resolution, bounds, and action
checks are retained in separate receipts.

Begin with an observable question and develop one main example. Introduce a new
tool because of the known result and the obstacle that remains. Mathematical
states come from the model; visual interpolation must not invent causality.
The ending returns to the question, states applicability conditions, and gives
audience-readable academic sources. Production, engine, version, and acceptance
information must not enter narration, captions, or the ending.

The default voice request is Serena / `science_female` / `full_text`: clear,
rational, even, and slightly brisk. Identical parameters do not guarantee
consistent delivery between sentences. Voice samples must cover ambiguous
pronunciations, numbers, Chinese/English mixing, diagram labels, and adjacent
sentence joins. Listening review and proxy metrics are recorded separately.
Music is selected deterministically by tags and yields to narration using
measured activity windows. Explicit silence is allowed.

Calibration reviews distinguish automated geometry/bounds checks, actual encoded
intermediate frames, continuous reasoning, real audio, and the target audience's
ability to explain the idea back. Preferences from previous videos, unit tests,
or a single contact sheet do not establish acceptance of an entire new topic.
