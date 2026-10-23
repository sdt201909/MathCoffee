# 本地配音与读音验收

独立安装后，以 `mathcoffee voice --workspace <用户工程>` 准备请求，显式增加
`--generate` 才在本地合成。它读取统一 Authoring v1 与项目配置，见
[创作与配置接口](project_interface.md)。工程也可选择逐句录音导入或显式无声模式。

兼容入口 [synthesize_voice.py](../scripts/synthesize_voice.py) 支持 `kokoro` 与 `qwen_mlx`；
[create_episode_voiceover.py](../scripts/create_episode_voiceover.py) 保留既有制作调用，
显式提供 episode、authoring 与 revision。规范实现位于包内，安装者无需复制脚本或
向插件安装目录写入作品。

Manim 的 Python 3.13 环境与配音环境分开。Qwen MLX 使用 Python 3.12、
MLX-Audio 0.5.7 与固定模型快照；安装与匿名公开权重下载均为显式操作，见
[运行时说明](../toolchains/speech/README.md)。Kokoro 为可选既有 provider，
当前未随仓库提供其完整环境锁，不能把它当作已经可一键安装的后端。

## 正文、配置与模型输入

原文始终保留，字幕读取原文；词典和数值口述产生独立的归一化输入与命中记录。
[lexicon.json](../src/mathcoffee/data/speech/lexicon.json) 采用最长上下文优先，不能做全局单字替换。
图中 A/B/C 必须按同名字母点名，下标、撇号和大小写身份保留。
[figure_label_contract.py](../src/mathcoffee/figure_label_contract.py) 检查最终模型输入中的
标签序列；这只能证明文本身份对应，实际发音必须另听样音。

[voice_profiles.json](../src/mathcoffee/data/speech/voice_profiles.json) 的默认 `science_female`
请求 Serena 预置女声，清晰、理性、自然、均匀。profile 是参数配置，不能证明实际
音色、情绪或自然度。Kokoro 没有同等指令能力；Qwen 的期望读音也不是硬音素约束。
不克隆真人、不调用收费服务，正式合成使用已核验的本地权重并禁用隐式下载与 token。
固定模型文件身份由 [model_files.json](../src/mathcoffee/data/speech/model_files.json) 记录，
生成前核验内容与上游适配源码；`doctor` 的路径检查不等于完整模型哈希检查。

```sh
mathcoffee setup --component speech             # 只返回独立 Python 3.12 环境准备计划
mathcoffee setup --component model              # 只返回固定权重下载计划
# 已授权准备时，分别增加 --execute；不会随插件安装自动执行。
mathcoffee voice --workspace '/absolute/path/to/my video'
mathcoffee voice --workspace '/absolute/path/to/my video' --generate
```

下面是保留的源码工程调用；安装版优先使用上述 CLI。

```sh
# 仅在需要时安装可选的独立环境；不修改 .venv。
SPEECH_BASE_PYTHON=/absolute/path/to/python3.12 make speech-setup
make speech-model
make speech-doctor

.venv-speech/bin/python scripts/synthesize_voice.py \
  --provider qwen_mlx --all --dry-run --output-dir media/speech_smoke/new-plan
```

准备真实合成前，先用本片多音字、数字、公式、英文混读和图形标签生成短样音。
新 revision 与新目录保存请求、模型身份、输入 SHA、参数、PCM 与听审状态，不覆盖旧版。
依赖私有 API 的 [全文本适配](../src/mathcoffee/speech/qwen_context.py) 校验上游版本与源码 SHA，
不匹配时拒绝运行。`stream: false` 不等于全文本条件；适配后的实际上下文模式进入清单。

## 时间轴与验收

从真实 PCM 测活动窗，再派生字幕、镜头锚点和配乐避让。禁止用截尾或任意整段变速
把旁白挤入估计句窗。跨句声线、语速、停顿和发音分别检查，ASR 或强制对齐不能证明读对。

通用工具支持显式 seed 补录组合、语速与停顿测量，以及声学代理指标。
可选 [voice_qa](../toolchains/voice_qa/README.md) 使用本地模型排序疑似声音漂移，
不能替代人耳判断。未试听就记录待听审，不能把自动成功写成人工认可。
最终 AAC 音轨另验有效样本、尾部填充与 PCM 同步；源 WAV 正确不代表编码后音轨正确。
