[English](installation.md) | 简体中文

# 在 Apple Silicon Mac 上安装

从 [GitHub Release](https://github.com/sdt201909/MathCoffee/releases) 下载**完整的 Codex
或 Claude Code ZIP**，不要把自动生成的源码压缩包当作安装插件。每个包均包含匹配 wheel、
安装入口、宿主目录、共用技能、许可证及中英文文档。先用 `shasum -a 256` 核对 ZIP 与
Release 的 `SHA256SUMS` 对应行，再解压到新目录；支持带空格路径。

本 Alpha 的目标为原生 Apple Silicon macOS，采用当前受
[Homebrew 支持的系统](https://docs.brew.sh/Installation.html)，目前基线为 macOS 15 及以上。
首版不承诺 Intel／Rosetta、Windows 或 Linux 制作环境。Linux 轻量 CI 只检查规划和契约。

## 1. 首次准备系统前置条件

空白 Mac 打开终端，执行：

```sh
xcode-select --install
```

自行完成 Apple 安装窗口，再按 [Homebrew 官方说明](https://docs.brew.sh/Installation.html)
安装 Homebrew。入口可发现 `/opt/homebrew` 原生安装，无需修改 shell 配置。它不会代装
Xcode／Homebrew、处理管理员密码或接受系统协议；此流程不要求完整 Xcode 应用。

另行安装并登录自己选择的 Agent 宿主。MathCoffee 不创建宿主账号、购买订阅或保存宿主凭据。
宿主如何处理提示词与账号认证，仍遵循该宿主设置。

## 2. 选择档位并查看计划

在解压后的插件目录运行：

| 档位 | 准备内容 | 适用方式 |
|---|---|---|
| `core`（默认） | uv、Python 3.13、隔离的 MathCoffee core | brief、authoring、配置与无模型规划 |
| `render` | core 加 Node 24、Cairo／Pango、pkgconf、FFmpeg、锁定的 Manim／Remotion 与浏览器 | 用自己的录音或显式无声模式渲染 |
| `full` | render 加独立 Python 3.12／MLX-Audio 环境 | 准备模型后使用本地 Serena 配音 |

```sh
bash bin/setup-macos --profile core
bash bin/setup-macos --profile render --with-tex
bash bin/setup-macos --profile full --with-tex --with-model
```

以上命令只检查本地状态并显示 JSON 计划，不安装、下载或创建托管目录。完全没有可用 Python
时，前端会给出较简短的前置准备计划。

- `--with-tex` 显式允许安装缺失的 `mactex-no-gui`，已有 TeX 则复用。标准 macOS 安装器
  可能请求管理员确认，需自行完成。BasicTeX 只有补齐所需宏包与 OpenType 数学字体后才可能
  替代完整发行版，本版未验证该精简路径。
- `--with-model` 仅适用于 `full`，显式请求固定 Qwen3-TTS CustomVoice 快照，文件合计
  **4,520,218,951 字节**，不含缓存和额外开销；匿名下载并核对固定来源及逐文件身份。
- `full` 不带 `--with-model` 时只准备声音环境，明确报告未请求模型，不下载权重。
- 公式依赖 XeLaTeX、`standalone.cls`、`unicode-math.sty`、`latinmodern-math.otf` 与
  dvisvgm。`doctor` 检查其存在；实际编译、字形和外观仍需真实样片。

完整 TeX、环境缓存、权重和视频产物需要较多磁盘空间，应为完整工作环境和制作产物准备至少
数十 GB。此前本地配音校准峰值进程内存约 7.7 GB；16 GB 及以上统一内存是实用建议，不是
对新机器的性能测试或保证。只规划、导入录音可以避开本地 TTS 开销。

## 3. 执行所选计划

准备完整本地环境：

```sh
bash bin/setup-macos --profile full --with-tex --with-model --execute
bin/mathcoffee doctor --profile full
```

或者只准备较小的档位：

```sh
bash bin/setup-macos --profile core --execute
bin/mathcoffee doctor --profile core
```

入口只安装缺失的所选 Homebrew 包，不主动请求升级或清理已有包。它建立有归属记录的版本化
环境，并登记实际解释器路径。框架 wheel 用 `--offline --no-deps` 安装；渲染与配音依赖由
各自锁文件准备。系统包、浏览器另从上游下载；Python／npm 锁文件不能使系统包逐位可复现。

完成后会显示收据与启动路径。中断时，用同一 wheel 重跑相同命令，可恢复身份匹配的已完成
步骤。相同版本下不同 wheel、无归属记录的环境或符号链接目标会被拒绝覆盖。不要删除验收
依据来强行重试，先检查收据／错误或向维护者反馈。

`doctor` JSON 含 `profile`、`required_checks` 和 `missing_required`。检查 `status: ready`，
诊断进程成功退出不等于全套制作验收通过。`core` 不要求渲染、配音或模型；`render` 不要求
声音权重；默认诊断档位为 `full`。

## 4. 加载宿主插件

包内本地 marketplace 指向包含 wheel 的同一解压目录，保留该目录供后续刷新。

**Codex**：添加解压目录作为本地 marketplace：

```sh
codex plugin marketplace add /absolute/path/to/extracted-plugin
```

打开插件浏览器，选择 `mathcoffee-codex` 来源并安装 MathCoffee；按宿主提示开启新聊天或
重启。提供相应安装子命令的 Codex CLI 也可执行
`codex plugin add mathcoffee@mathcoffee-codex`，本地安装测试使用了此路径。
见[官方打包说明](https://developers.openai.com/plugins/build/plugins)。

**Claude Code**：在 Claude Code 会话中运行：

```text
/plugin marketplace add /absolute/path/to/extracted-plugin
/plugin install mathcoffee@mathcoffee-claude
```

按宿主选择作用范围并重新加载。见[官方安装指南](https://code.claude.com/docs/en/discover-plugins)。
Claude 包已做结构检查，真实加载仍是社区试用目标。此次 Release 不等于两宿主官方公共插件
目录的上架。

使用已安装插件的 setup／create／review／revise 技能。没有生命周期 hook 自动安装依赖、
下载模型或运行影片；也可以只使用 CLI。

## 5. 创建自己的工程

```sh
bin/mathcoffee init --workspace "$HOME/Movies/MyMathVideo" \
  --brand '自己的频道' --title '观众关心的问题'
bin/mathcoffee plan --workspace "$HOME/Movies/MyMathVideo"
```

工作区必须为新目录。填写 `authoring.json` 和 `mathcoffee.json` 后重新规划；空模板返回
`incomplete` 是预期结果。遵循[创作接口](project_interface.zh-CN.md)与
[制作流程](production_workflow.zh-CN.md)。

| 位置 | 内容 |
|---|---|
| 解压目录／宿主插件缓存 | 只读技能、启动器、wheel 与包资源 |
| `~/Library/Application Support/MathCoffee/runtimes/<version>/core` | 有归属记录的 Python 3.13 core |
| 同版本下 `render` 与 `speech` | 独立渲染和 Python 3.12 配音环境 |
| `~/Library/Application Support/MathCoffee/runtime.json` | 显式安装登记的可执行路径 |
| `~/Library/Caches/MathCoffee` | 版本化引擎／浏览器缓存与固定模型缓存 |
| 自己选择的工作区 | authoring、录音、构建阶段、成品及审查依据 |

可用 `MATHCOFFEE_DATA_HOME`、`MATHCOFFEE_CACHE_HOME` 指定专用外部目录；
`MATHCOFFEE_PYTHON` 显式指定启动器使用的已有 core。工程运行时覆盖支持另行维护的环境。

## 手动配置与源码开发

已有依赖时，可将本地 wheel 安装到新的外部 Python 3.13 环境，并让启动器使用它：

```sh
uv venv --python /absolute/path/to/python3.13 /absolute/path/to/mathcoffee-core
uv pip install --offline --no-deps --python /absolute/path/to/mathcoffee-core/bin/python \
  /absolute/path/to/mathcoffee-0.2.0a2-py3-none-any.whl
export MATHCOFFEE_PYTHON=/absolute/path/to/mathcoffee-core/bin/python
bin/mathcoffee setup --component render
bin/mathcoffee setup --component speech
bin/mathcoffee setup --component model
```

组件命令默认只显示计划，加 `--execute` 才执行。确保进程 PATH 选中 Node 24，或登记其绝对
路径；统一入口会处理这些信息。不要向 Python 3.13 core／渲染环境混装配音包。

源码目录没有内置 wheel。贡献者先 `uv build --wheel`，再向入口传
`--wheel /absolute/path/to/the-wheel.whl`，或遵循[贡献指南](../CONTRIBUTING.zh-CN.md)。
`Brewfile` 列出完整运行时前置包，不含 TeX 和模型；主动选择全套依赖时可用
`brew bundle --no-upgrade`，而统一入口会按 core／render 减少安装量。

## 升级、卸载与问题反馈

新版本解压到独立目录，核对校验和后运行其入口。新版本拥有新的 core／运行时目录，不修改
旧作品；全局启动器可能转为新 core。刻意锁定旧环境的作品应保留旧插件与运行时路径，通过
工程配置或 `MATHCOFFEE_PYTHON` 明确选择。不要覆盖安装资源或隐式迁移正式产物。

宿主卸载移除插件登记／缓存，不删除外部运行时、模型缓存或用户工作区。卸载插件不是媒体清理
授权。通过 [issue 模板](https://github.com/sdt201909/MathCoffee/issues/new/choose) 反馈，先移除
私有旁白、路径、凭据和版权素材。

安装入口与包流程已在本机测试，真正空白 Mac 的完整配置仍待独立试用，见
[验证状态](implementation_status.zh-CN.md)。
