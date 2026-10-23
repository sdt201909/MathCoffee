# 成片面向观众：论述与显示文字约定

知数咖啡厅的成片回答观众正在追问的数学问题。工程记录服务制作人员，存于计划、
审校与交付文档；它们不能因为真实、详尽或已通过测试就进入旁白、字幕和画面。
本约定用于频道内容片。确实以制作技术为主题的作品，应先在本期 brief 明确受众和
讲解目的，按该目的调整检查规则，不能用自动豁免字段隐藏命中。

## 从问题推到工具

审稿要沿实际播放顺序逐段回答：观众正在解决什么，已经得到什么，仍缺哪一步，
下一工具为什么能解决这个障碍。将答案放在本期制作计划或审稿记录，不能把这四项
机械念给观众。先呈现可观察的差异、失败或需要，再引入能解释它的定义和推理。
没有推进主问题的段落应删减或合并；章节数与目标时长都不是保留重复解释的理由。

跨章连接要检查“前一段的结果是否真能成为后一段的出发点”，不以“接下来介绍”
代替因果。代表性连续样段应覆盖一次真正的概念跨越，而非挑选各章最好看的片段。
记录时间戳、原句、观众尚不知道的条件、修订后的承接及真实动态画面。
技术测试、数学审校、论述连贯审查、视听抽样、人工试听是不同证据，分别报告；
任何自动检查 PASS 都不代表观众已经理解。

## 全片及片尾的受众边界

旁白、字幕、标题、图注、数字说明、公式附注、参考卡和封面都是观众文字。
不能向片中或片尾搬入项目路径、版本号、引擎或配音模型、生成过程、调试、验收、
复现命令、文件哈希、工程交付或内部制作流程。必要的使用许可署名遵照资产约定；
学术来源以观众可读的作者、作品名、年份及必要的出处呈现，不能指向“项目说明”
或“制作记录”来代替参考资料。

片尾从最后一段正文开始检查，一直看到最终黑帧：结论要回扣开场问题，数学边界
要说明结论适用在哪里，参考资料帮助继续阅读，频道收束自然简洁。不得把内部话语
从片尾移到正文。修订涉及正文时，更新整段配音、句窗、字幕与显示文案；旧尾声
不能因复用缓存而回流。保留完整尾音和实际黑帧，不用突然裁音来清除旧句。

“生成子空间”“验证等式”“连续版本”“工程中的流体计算”等可以是合法数学内容。
检查器采用有上下文的规则，避免禁止这些单词本身；其漏报和误报仍需编辑判断。

## 显式显示文字清单

每期保留一份 `audience_display_manifest.json`，由 renderer 的同一显示文字来源导出。
不得只扫描 authoring 的旁白，因为辅助函数、动画目标和片尾卡可能另有硬编码文字。
以下是机器接口，路径和哈希属于内部信息，不显示给观众：

```json
{
  "schema_version": 1,
  "episode": "episode_id",
  "authoring_sha256": "完整 authoring 文件的 SHA-256",
  "coverage": {"scene_ids": ["opening", "closing"], "declared_complete": true},
  "entries": [
    {"id": "opening.question", "scene_id": "opening", "kind": "heading",
     "text": "这张速度图，还缺什么？", "cue_ids": ["opening_01"]},
    {"id": "closing.brand", "scene_id": "closing", "kind": "brand",
     "text": "知数咖啡厅 · 我们下次见", "cue_ids": ["closing_01"]}
  ],
  "renderer_sources": [{"path": "scenes/episode.py", "sha256": "文件 SHA-256"}],
  "metadata": {"description": "内部生成与审查记录，不属于显示文字"}
}
```

条目 ID 唯一；`scene_id` 与可选 `cue_ids` 必须能在 authoring 中定位。
`kind` 为 `heading`、`label`、`formula`、`reference` 或 `brand`。
每章至少登记一个真实显示条目；全文只有旁白而没有屏幕文字的特殊章，需调整契约并
明确说明，不能伪造一条不可见文字凑覆盖。动态文案登记格式化后取值，包括动画目标。
来源哈希绑定所有实际参与显示文字的 renderer 模块。清单按章覆盖声明不等于证明
实际帧中没有未登记文字，真实渲染仍须对照显示回执与编码画面。

可用 Manim 正式构造路径的 `dry_run` / `skip_animations` 导出初始显示清单，再在
正式渲染中记录真实显示条目核对。`Text`、`MathTex`、辅助函数生成的标签、动画
目标和 `become` 后文字都在范围内。仅按最终帧扫描会漏掉中间文字；数字更新器
可记录其格式规则与实测取值，但不能用“动态标签”名义跳过中文说明。

## 检查入口与证据边界

先检查正文，随后在时间轴和显示清单都齐备时做完整登记范围检查：

```sh
.venv/bin/python scripts/check_audience_text.py \
  --authoring assets/episode_authoring.json \
  --report media/reports/episode/audience/authoring.json

.venv/bin/python scripts/check_audience_text.py \
  --authoring assets/episode_authoring.json \
  --display-manifest media/episode/audience_display_manifest.json \
  --timeline media/episode/timeline.json \
  --require-complete --report media/reports/episode/audience/complete.json
```

检查器只读取 authoring 标题、章标题、句子正文和公式；显示清单的 `entries[].text`；
timeline 的逐句 `caption` 和正文一致性。内部 `scope`、`review`、`question`、
`result`、文件路径和其他 metadata 不递归扫描。若这些内部字段实际显示，必须作为
显示条目登记。字幕允许换行／空白差异，不允许静默删句、重排或换成旧稿。

返回 `BLOCKED` 表示规则命中、来源过期、结构或字幕不一致；`SCOPED_TEXT_PASS`
仅表示现有输入范围无命中；`DECLARED_SURFACES_TEXT_PASS` 表示完整登记范围检查
通过。最后一种状态仍不意味着理解、发音或所有画面文字都通过。`--require-complete`
拒绝缺显示清单或时间轴的有限检查。退出码为 0（检查通过）、1（检查阻断）、2（输入
无法读取／解析）。代表性整章样段显式加 `--allow-scene-subset`，逐句必须完整，
顺序遵从 authoring；正式全片不使用该选项。报告记录实际选择的章节。

渲染器可导入 `check_text(text, location=..., channel=...)` 对真实文字即时检查，
或调用 `check_audience(authoring, display_manifest=..., timeline=...,
authoring_sha256=..., root=..., allow_scene_subset=False)`。最终打包前重新核对清单
与时间轴输入哈希，并单独保存论述审查和从正文到黑帧的画面／音频审查结果。
