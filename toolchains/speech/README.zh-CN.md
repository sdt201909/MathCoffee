[English](README.md) | 简体中文

# 本地 MLX / Qwen 配音运行时

此可选工具链使用独立 Python 3.12 环境，锁文件针对 macOS arm64。它不改变主 Manim 环境。
模型采用固定的 Qwen CustomVoice 官方快照，推理由独立项目 MLX-Audio 提供。
仓库只包含下载器、配置和许可证，不包含模型权重或生成音频。

## 安装和检查

安装版插件请先读[安装指南](../../docs/installation.zh-CN.md)，使用 CLI 的外部运行时目录：

```sh
mathcoffee setup --component speech
mathcoffee setup --component model
```

上面只显示计划，已授权准备时再加 `--execute`；模型下载是独立显式操作，规划不需要权重。
以下命令用于源码开发。

先确认已有 Python 3.12 和 uv；下面命令会联网安装依赖及下载约 4.52 GB 的公开模型，
仅在用户授权后运行。可用 `SPEECH_BASE_PYTHON` 指定现有 Python 3.12 解释器。

```sh
sh toolchains/speech/setup.sh
.venv-speech/bin/python toolchains/speech/fetch_model.py
.venv-speech/bin/python toolchains/speech/doctor.py --verify-model
.venv-speech/bin/python toolchains/speech/smoke.py
```

`setup.sh` 用 `uv pip sync --require-hashes` 安装锁定包；下载器仅访问公开固定文件，
显式禁止 Hugging Face 隐式 token。[模型清单](../../src/mathcoffee/data/speech/model_files.json) 保存模型 revision、文件大小
与校验值。完整文件通过校验后才记入完成清单；中断下载保留临时文件。
`doctor.py` 和 `smoke.py` 离线运行；源码工具链的报告写入 `media/reports/agent_upgrade/speech_runtime/`。
后者会加载模型并生成一条短句，需要 Apple Silicon Metal 和相应内存。

## 固定来源与许可证

- MLX-Audio 0.5.7：[PyPI](https://pypi.org/project/mlx-audio/0.5.7/)、
  [上游项目](https://github.com/Blaizzy/mlx-audio)，许可证文本见 [LICENSE-mlx-audio.txt](LICENSE-mlx-audio.txt)。
- Qwen CustomVoice：[固定模型快照](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice/tree/0c0e3051f131929182e2c023b9537f8b1c68adfe)。
  revision 为 `0c0e3051f131929182e2c023b9537f8b1c68adfe`；来源和许可证哈希见
  [licenses.json](licenses.json)，文本见 [LICENSE-Qwen3-TTS.txt](LICENSE-Qwen3-TTS.txt)。

锁定来源不等于所有平台均验证通过。下载模型后仍应保存其来源与许可材料。
工具采用预置说话人，不提供真人声音克隆或云端回退。

## 验收边界

provider 会记录原文、归一化文字、发音词典命中、模型来源、运行时适配与输出哈希。
Qwen 接收文字及风格指令；Kokoro 的音素替换不能作为 Qwen 的硬发音控制。
`smoke.py` 的有限值、非静音和波形检查不证明读音、音色、情绪或完整性合格。
实际试听与编码后声画同步检查应另行记录。使用接口见
[配音管线](../../docs/voice_pipeline.zh-CN.md)。
