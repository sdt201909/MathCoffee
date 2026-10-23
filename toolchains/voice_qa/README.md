# 本地声线一致性代理

此可选工具使用 WeSpeaker embedding 定位跨句音色异常，支持同文本候选比较。
它读取本地 WAV 并输出诊断报告，不修改旁白，不证明人物身份、正确发音或听感合格。
仓库不包含模型权重、录音和既往分析结果。

## 来源与隔离

[WeSpeaker 模型](https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet34-LM)
固定 revision 为 `f0c48c298fd835726c27956a5d617bad7115627e`。
ONNX 文件 SHA-256 为
`7bb2f06e9df17cdf1ef14ee8a15ab08ed28e8d0ef5054ee135741560df2ec068`。
来源、模型卡与许可证由下载器保存到 `media/models/wespeaker-voxceleb-resnet34-LM/`。
模型来源声明 CC-BY-4.0，署名为 WeSpeaker project; Wang et al., ICASSP 2023；
上游推理代码参考见
[固定源码](https://github.com/wenet-e2e/wespeaker/blob/9fecd6cb4f47475d01761d87c826298dff4ef18c/wespeaker/bin/infer_onnx.py)。

使用独立 Python 3.12 环境和 macOS arm64 锁文件。先确认已有 uv 和 Python 3.12；
`VOICE_QA_BASE_PYTHON` 可指定解释器。安装与模型下载会联网，需先获得用户授权。

```sh
sh toolchains/voice_qa/setup.sh
.venv-voice-qa/bin/python toolchains/voice_qa/fetch_model.py
.venv-voice-qa/bin/python scripts/audit_speaker_embeddings.py \
  --input media/voiceover/example/manifest.json \
  --reference media/voiceover/example/reference.wav \
  --output media/reports/example/speaker_metrics.json
.venv-voice-qa/bin/python toolchains/voice_qa/test_metric.py
```

分析阶段使用 CPU，并在创建 ORT Session 前禁用 telemetry；不上传音频。
运行时可能输出设备缓存等警告，应保留并按实际环境检查。

## 输入与检查

输入支持 `chapters[].cues[]`、配音 `cases[]`，或通用清单：

```json
{"items":[{"id":"sentence_01","path":"voice.wav","sha256":"optional_expected_sha256","text":"原输入文字","active_start_sample":0,"active_end_sample":240000}]}
```

路径可为绝对路径，或相对清单／项目目录。活动边界采用源采样率；缺省时分析全 WAV。
特征计算使用 Kaldi-native-fbank、16kHz、80维、25ms 窗／10ms 步长和逐句均值归一化。
小于0.5秒、非有限或哈希不符的音频会拒绝。

`--compare` 校验模型、锚点、特征配置及匹配 ID 的文字；`--only-ids` 可固定句集。
输出拒绝覆盖，记录输入、WAV、模型与脚本哈希、包版本、embedding 和相似度。
通用测试覆盖特征帧数、纯增益不变性、重采样、无效输入、活动边界与哈希拒绝。
相似度没有自动合格阈值，异常应交由人耳确认。
