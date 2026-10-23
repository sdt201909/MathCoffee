# 用户工程与公共接口

`mathcoffee init --workspace <新目录>` 创建 `mathcoffee.json`、空白 `authoring.json` 和
工程说明。现有目录即使为空也不覆盖。输入、导入逐句音轨和作品输出属于用户工程；
运行时、权重和插件代码有各自独立位置，不随卸载删除作品。

## 项目配置

`mathcoffee.json` 为 schema_version=1，使用以下字段：

| 字段 | 用途 |
|---|---|
| `title`、`brand` | 用户标题与品牌；默认品牌为空 |
| `preset`、`style` | 预设 ID 与严格字段覆盖；`mathcoffee style` 查看解析结果与 diff |
| `authoring` | 相对本工程的唯一创作来源路径 |
| `runtime` | 可选显式 render_python、speech_python、node、browser_executable、model_path、remotion_root |
| `voice` | provider：qwen_mlx／kokoro；mode：synthesize／imported／silent；index 为导入清单相对路径 |
| `music.enabled` | 是否启用程序配乐；曲目标签、种子、电平等配置在 style.music |

安装运行时默认放在 `~/Library/Application Support/MathCoffee/runtimes/<version>/`，
浏览器、引擎和模型缓存放在 `~/Library/Caches/MathCoffee/`。测试或受管部署可使用
`MATHCOFFEE_DATA_HOME`、`MATHCOFFEE_CACHE_HOME` 指定专用位置。用户项目中的 runtime
覆盖全局 `runtime.json`。启动器可通过 `MATHCOFFEE_PYTHON` 选择已安装框架的 core。

`setup` 不带 `--execute` 只返回计划。执行时使用独立环境与带身份的安装回执，
失败后保留现场；相同来源可继续未完成步骤。已有但不属于该回执的环境不会被同步。
模型独立下载，正式合成离线运行。doctor 检查声明的版本与路径，默认不读取整套模型哈希。

## Authoring v1

规范结构为 `schema_version / episode / title / brief / math_states / actions / scenes`。
每个 scene 有稳定 `id`、观众标题及 `sentences`；每句有稳定 `id` 与唯一原文 `text`，
可附 `screen_text`、`formula`、`visual`、`state_ref`、`action_refs`、`duration_seconds`。
旧 `chapters/cues` 在入口归一化，拒绝混用或静默改写 ID／正文。

- `brief` 记录观众、主问题、假设、数学边界与授权外部来源。
- `math_states` 是稳定 ID 到有限 JSON 状态的映射；图形、数字和公式应共同引用它。
- 通用 visual 支持文字、公式、向量、点、折线、对照、状态读数、强调、总结与参考；
  具体参数以 `components.referenced_visual/build_visual` 为准。框架拒绝未知类型。
- `actions` 的通用模式只登记 `semantic_anchor`；需要真实移动或变形时，在用户工程的
  `scene_module` 中实现，并由实际渲染记录动作。不能把计划事件当已执行证据。
- `figure_label_registry` 可在创作源或句子声明；传播至归一化和实际 TTS 请求，
  保留字母、下标、撇号身份。文本校验不能证明听音正确。

计划派生 `build/plan.json`，声音请求和句窗从此来源生成。内部 caption 正文与原文一致，
最终是否烧录字幕由风格决定。实际 PCM 决定发声活动时间，帧时窗向上量化并保留停顿；
配音超预算会延长镜头，不截尾或变速。

导入音轨清单为 `{"cues":[{"id":"...","text":"原文","path":"voice/cue.wav","sha256":"..."}]}`。
必须覆盖全部句子并保持顺序；路径位于本工程内；音轨为单声道 PCM16／24／32 WAV，
读取实际样本与活动窗，拒绝缺失、截断、静音、哈希或原文不一致。它不证明录音读对。

## 构建、恢复与审查

`preview` 为低清，`render --quality final` 为高清，`resume` 只复用身份与产物哈希匹配
的步骤。正文、状态、风格、PCM、依赖或实现发生变化，会产生新构建身份；旧产物保留。
单场景仅依赖自身句窗、引用的状态／动作和实际渲染代码，避免无关章节变更后全片重渲染。

每次构建记录 schedule、renderer v1 timeline、显示清单、媒体与命令、源和输出哈希。
最终容器验证覆盖完整视频帧与 PTS、实际音轨时钟、AAC 对预混音同步、声明的字幕窗口，
其边界以验证回执为准。无声用途必须显式选择 silent；它不会被写成声音已通过验收。

高清入口读取对应构建身份的 `reviews.json`。真实审查后填写 `draft_visual: approved`、
`reviewer`，并保留确切 `reviewed_output_sha256`。CLI 没有 force 绕过参数。其余数学、
叙事、听审、风格和观众理解仍分别记录；低清画面获认可不代表其他门槛已完成。

CLI 默认输出 JSON；成功为0，输入／执行阻断为2，创作未补全为3。doctor 的
`setup_required` 是结构化诊断结果，规划仍可用。读取 JSON 的 status/checks，而非仅凭退出码判断制作能力。
