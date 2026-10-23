# MathCoffee · 知数咖啡厅

面向 Agent 的数学科普视频制作工具集：用一份创作数据连接数学状态、画面、旁白、
字幕和验收，让新作品延续清晰推理、严谨几何与简洁叙事的风格。

当前是 **Plugin 开发前的框架基础版本**，尚不能通过插件安装后直接完成一键制作。
仓库只保存通用工具、配置、依赖锁和工作约定；频道单期代码、正文、素材、声音、
成片与本机制作记录留在独立的本地制作工程中。

## 已有能力

- Manim 数学动画环境和 Remotion 横屏／竖屏编排；共享帧时间轴、素材哈希和媒体预检。
- 本地配音 provider、版本化发音词典、图形标签身份校验与逐句声音记录。
- 原创程序配乐、实际句窗驱动的避让、编码音轨与音频缓存验证。
- 受众文字检查、数学／论述／画面／试听分开记录的制作约定。
- 显式提交文件白名单与历史检查，防止把本地制作内容带入仓库。

先读 [Agent 约定](AGENTS.md)、[文档入口](docs/README.md) 和
[制作流程](docs/production_workflow.md)。插件化后续工作见 [路线图](docs/plugin_roadmap.md)。

## 环境与安装

当前运行基线为 macOS Apple Silicon、Python 3.13、Manim 0.20.1；JavaScript 引擎
使用 Node 24、Remotion 4.0.531。配音使用独立 Python 3.12 环境，不能混装到 Manim。
完整 TeX Live／MacTeX、中文字体，以及音视频预检所需的 FFmpeg／FFprobe 需另行准备。

```sh
# 已具备 Homebrew、uv、Cairo、pkgconf 时，同步锁定 Python 环境。
uv sync --locked
make help
make doctor
make test-core

# 可选：Remotion 依赖安装；浏览器下载是单独的显式操作。
make remotion-setup
make remotion-check
make remotion-browser
```

`make` 只显示帮助，不安装、不渲染。`make doctor` 运行本机 TeX 烟测。
配音环境、权重下载与声音测试见 [配音管线](docs/voice_pipeline.md)。
本仓库不包含模型权重，不使用收费合成 API，不自动上传正文或音频。

## 使用边界

新一期的 authoring、场景、实验、素材和输出存入本地制作工程；本仓库不携带历史作品。
当前尚未完成可安装的软件包／插件入口分离，现有 CLI 依赖仓库布局；制作时需使用
独立本地 checkout，或在本地工作区放入被忽略的 `scenes/`、`assets/` 与 `media/` 内容。
通用的场景调用始终显式指定项目配置：

```sh
uv run --locked manim --config_file manim.cfg -ql scenes/your_scene.py YourScene
```

运行命令前按 `--help` 核对输入；渲染使用新输出路径，先低清审查，再做高清交付。
本次框架验证覆盖自动测试与静态检查，没有合成新声音或渲染新影片。

## 仓库结构

| 路径 | 内容 |
|---|---|
| `src/mathcoffee/` | 时间轴、音频、配乐、配音与标签契约 |
| `scripts/` | 通用制作 CLI、环境诊断与仓库边界检查 |
| `engines/remotion/` | 通用合成器、类型与媒体预检 |
| `assets/speech/`、`assets/audio/` | 通用词典、声音配置与程序配乐配方，无媒体素材 |
| `toolchains/` | 独立可选运行时、锁文件和第三方许可证 |
| `tests/` | 不依赖单集文件的通用回归测试 |
| `docs/` | 制作约定、能力边界与插件化路线 |
| `repository-files.txt` | 经审查允许提交的精确文件清单 |

提交前执行 `make repository-check`；首次整理文件后先显式暂存，再检查索引。
`scripts/repository_guard.py --ref HEAD --history` 检查当前提交可达的每一版文件树。
新增通用文件时需要审查其内容与依赖，再更新白名单；白名单不能替代人工内容审查。

仓库目前保持私有，尚未选择项目开源许可证，也未发布 Plugin。
第三方组件的许可随各自来源保留，见 [依赖与授权边界](docs/dependencies.md)。
