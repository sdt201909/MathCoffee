[English](README.md) | 简体中文

# MathCoffee · 知数咖啡厅

[项目主页](https://sdt201909.github.io/MathCoffee/) ·
[开始创作](https://sdt201909.github.io/MathCoffee/zh/#get-started) ·
[社区交流](https://github.com/sdt201909/MathCoffee/discussions)

**数学应是大众的，而非特权。**

面向 **Codex 与 Claude Code**、在本地运行的 Agent-Native 数学视频制作工具。
以一份 authoring 创作来源驱动 Manim 数学场景、Remotion 编排，以及由实际旁白决定的共同时间轴。

默认预设提炼问题驱动讲述、语义配色、深色数学画面与本地科普声音。使用者提供自己的频道品牌、
题目、数学模型和许可明确的素材，品牌与风格分别配置。

**社区 Alpha：`v0.2.0-alpha.2`**（Python `0.2.0a2`）。原创框架代码与文档采用
[Apache-2.0](LICENSE)。这是供社区共同完善的早期版本：默认风格确认、实际听审、Claude Code
真实加载、长片验收，以及独立空白 Mac 试用仍待完成。见[实施状态](docs/implementation_status.zh-CN.md)
和[路线图](docs/plugin_roadmap.zh-CN.md)。

## 在新 Mac 上开始

首批目标为 **Apple Silicon Mac**，使用目前受 Homebrew 支持的 macOS。先安装 Apple
Command Line Tools 和 [Homebrew](https://docs.brew.sh/Installation.html)，再从
[Releases](https://github.com/sdt201909/MathCoffee/releases) 下载并解压对应宿主 ZIP。
包内包含插件、wheel、文档、锁文件和安装入口。GitHub 自动生成的源码压缩包不是完整安装插件包。

在解压后的插件目录运行：

```sh
# 先查看完整安装计划；不会安装或下载。
bash bin/setup-macos --profile full --with-tex --with-model

# 显式执行同一组已选择的准备工作。
bash bin/setup-macos --profile full --with-tex --with-model --execute

bin/mathcoffee doctor --profile full
bin/mathcoffee init --workspace "$HOME/Movies/MyMathVideo" \
  --brand '自己的频道' --title '观众关心的问题'
bin/mathcoffee plan --workspace "$HOME/Movies/MyMathVideo"
```

空白 authoring 尚未填完时，`plan` 返回 `incomplete`；缺模型或渲染环境不影响规划。
只规划可用 `--profile core`；使用自己的录音可用 `--profile render`。
`--with-model` 显式选择数 GB 的模型下载；`--with-tex` 可能触发标准 macOS 管理员提示。
已有依赖优先复用；入口不会代装 Homebrew、接受操作系统协议、修改 shell 配置或清理媒体。

[安装指南](docs/installation.zh-CN.md)包含前置条件、分档安装、手动流程、宿主加载、存储、恢复
与卸载说明。安装宿主插件后，让 Agent 使用 MathCoffee 在自己的工作区创建视频。
本次通过 Release 包分发，尚未上架两种宿主的官方公共插件目录。

## 制作与审查

```sh
bin/mathcoffee voice --workspace "$HOME/Movies/MyMathVideo"              # 仅规划
bin/mathcoffee voice --workspace "$HOME/Movies/MyMathVideo" --generate   # 本地合成
bin/mathcoffee preview --workspace "$HOME/Movies/MyMathVideo"
bin/mathcoffee verify --workspace "$HOME/Movies/MyMathVideo" --quality draft
bin/mathcoffee status --workspace "$HOME/Movies/MyMathVideo"
bin/mathcoffee resume --workspace "$HOME/Movies/MyMathVideo" --quality draft
```

先完成数学与论述审稿、实际听音和低清全片画面检查，再进行正式渲染。高清门禁要求画面审查绑定
该版草稿的身份与哈希；自动检查不能代签数学、观众理解、发音或风格。产物和失败现场保存到用户
工作区，不写入插件安装目录。

## 默认风格

| 预设 | 交付画幅 | 旁白字幕 |
|---|---|---|
| `mathcoffee-shorts@1` | 1080×1920，60 fps | 默认关闭，保留标签、公式和标题 |
| `mathcoffee-longform@1` | 1920×1080，60 fps | 独立配置，默认开启 |

两引擎读取同一份解析后的颜色、字体、布局、字号、节奏、声音、配乐及品牌配置；自定义覆盖记录
差异与身份。不设置全局三分钟上限，也不通过静默变速或裁尾挤进预算。

当前本地配音默认 **Serena／science_female／full_text**，面向中文科普视频 brief。
可以选择已支持的本地 provider／声音，或导入逐句 PCM。更换声音后重新检查发音与一致性；
不要求付费合成服务或真人声音克隆。

详见[创作与配置接口](docs/project_interface.zh-CN.md)、[风格基线](docs/style_baseline.zh-CN.md)
及[制作流程](docs/production_workflow.zh-CN.md)。自定义数学场景可在用户工程扩展 `SceneBase`。
框架不会证明任意数学，也不内置完整单期视频。

## 参与维护

欢迎提交安装反馈、新题材验证、风格组件、无障碍改进、provider 适配、文档与修复。
先读[贡献指南](CONTRIBUTING.zh-CN.md)、[Agent 约定](AGENTS.zh-CN.md)及
[文档入口](docs/README.zh-CN.md)。单期代码、录音、素材、模型、环境及交付压缩包不进入源码仓库。

```sh
uv sync --locked --no-editable --extra render
make test-core
make test-speech            # 独立 Python 3.12 .venv-speech
make test-voice-qa          # 可选独立 .venv-voice-qa
make remotion-check
uv build --wheel --sdist
```

裸 `make` 显示帮助。构建后端不支持 editable 安装；使用 wheel 或 `--no-editable`。
渲染与声音接口继续锁定已测试版本。`repository-files.txt` 与仓库守卫保护源码边界。
轻量 CI 不代替空白 Mac 上的真实媒体与配音测试。

## 许可证与依赖边界

原创框架代码和文档采用 [Apache License 2.0](LICENSE)，见 [NOTICE](NOTICE)与
[第三方声明](THIRD_PARTY_NOTICES.zh-CN.md)。依赖保留各自条款，**包括 Remotion 独立的使用
及商业许可条款**。包内不包含模型权重、字体、浏览器二进制或媒体。安装框架不会授予原频道品牌、
作品、录音，或他人肖像与声音的使用权。
