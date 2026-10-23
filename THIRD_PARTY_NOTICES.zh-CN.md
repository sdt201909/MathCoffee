[English](THIRD_PARTY_NOTICES.md) | 简体中文

# 第三方声明

MathCoffee 原创框架代码和文档采用 [Apache License 2.0](LICENSE)，项目署名记录见
[NOTICE](NOTICE)。该许可不替代依赖、模型权重、字体、录音、频道品牌及其他素材自身的条款。

源码仓库及插件包包含框架源码、配置、锁文件、文档和 MathCoffee wheel，不包含已安装的
依赖环境、`node_modules`、浏览器或 FFmpeg 二进制、模型权重、字体、录音、视频素材及
完整单期工程。显式执行环境准备后，才从各自上游下载所选运行时组件。

| 组件 | 来源与条款 | 使用方式 |
|---|---|---|
| Manim 0.20.1 | [Manim Community，MIT](https://github.com/ManimCommunity/manim/blob/v0.20.1/LICENSE) | 独立安装到渲染环境，不内置上游运行时 |
| Remotion 4.0.531 | [Remotion 许可与条款](https://www.remotion.dev/docs/license) | 通过 npm 独立安装，使用者须按自己的使用场景核对使用及商业条款 |
| React 与 TypeScript | [React 许可](https://github.com/facebook/react/blob/main/LICENSE)、[TypeScript 许可](https://github.com/microsoft/TypeScript/blob/main/LICENSE.txt) | 独立 npm 依赖，版本记录在引擎锁文件 |
| MLX-Audio 0.5.7 | [上游 MIT 许可](https://github.com/Blaizzy/mlx-audio/blob/main/LICENSE)；[保留文本](toolchains/speech/LICENSE-mlx-audio.txt) | 本地配音适配器调用独立安装的运行时 |
| Qwen3-TTS CustomVoice 模型 | [固定版本模型卡](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice/blob/0c0e3051f131929182e2c023b9537f8b1c68adfe/README.md)；[保留的 Apache-2.0 文本](toolchains/speech/LICENSE-Qwen3-TTS.txt) | 可选匿名下载，固定修订并逐文件校验；不包含权重 |
| 可选配音与声音 QA provider | [配音约定](docs/voice_pipeline.zh-CN.md)、[声音 QA 来源](toolchains/voice_qa/README.zh-CN.md) | 使用独立环境与模型，标准安装入口不会自动安装 |
| Python 库 | `uv.lock`、`toolchains/render/requirements.lock`、`toolchains/speech/requirements.lock` | 保留各自上游许可，不分发环境 |
| Cairo、Pango、FFmpeg、TeX 与字体 | 对应系统包／发行版条款 | 由使用者安装或提供，不内置二进制或字体文件 |

框架采用 Apache-2.0 **不代表**所有依赖也采用此许可，或可在所有商业场景免费使用。
尤其在团队、产品或商业服务中使用 Remotion 前，应核对上游条款。框架不会创建 Remotion
账号、购买许可、配置许可密钥、代替使用者接受额外条款或启用云渲染。

每项外部视频资产仍须记录来源、作者、许可证、用途与版本／哈希。安装框架不会授予
原频道的作品、标识、录音，或他人肖像与声音的使用权。初始化时请填写自己的品牌。

本文说明分发边界与主要声明，不是对全部传递依赖的完整授权审计。再分发依赖时，应核对
实际安装版本及其上游许可文件。更多信息见[依赖说明](docs/dependencies.zh-CN.md)与
[贡献指南](CONTRIBUTING.zh-CN.md)。
