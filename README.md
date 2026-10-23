# MathCoffee · 知数咖啡厅

本地运行、面向 Agent 的数学视频制作框架。默认预设延续 MathCoffee 的问题驱动讲述、
深色数学画面、语义配色与科普声音；使用者可以替换品牌，并通过配置调整风格。

当前版本为 **0.2.0a1 开发候选版**：已实现独立 CLI、创作数据编译、通用 Manim 组件、
Remotion 编排与 Codex／Claude Code 插件包。它需要本地制作依赖；安装插件不会自动
安装 TeX、下载声音模型或替你确认数学、听感和风格。首批校准预设仍待作者确认，
尚未公开发布或选择项目开源许可证。

## 安装与首次使用

首版支持 Apple Silicon Mac。使用生成的宿主 ZIP，解压到新目录；包中包含对应
marketplace、skills、启动器、框架 wheel、引擎与锁文件。源码仓库中的 marketplace
用于开发，发行与试用应使用含 wheel 的完整包。

按宿主的 marketplace 安装流程加载插件，再调用 MathCoffee 的 setup 工作流。
[Codex 插件规范](https://developers.openai.com/plugins/build/plugins) 与
[Claude Code 插件规范](https://code.claude.com/docs/en/plugins/create) 说明宿主安装方式。

也可以先把发行包中的 wheel 安装到独立 Python 3.13 环境，直接使用 CLI：

```sh
uv venv --python /absolute/path/to/python3.13 /absolute/path/to/mathcoffee-core
uv pip install --python /absolute/path/to/mathcoffee-core/bin/python /absolute/path/to/mathcoffee.whl
/absolute/path/to/mathcoffee-core/bin/mathcoffee init \
  --workspace '/absolute/path/to/my video' --brand '自己的频道' --title '观众问题'
/absolute/path/to/mathcoffee-core/bin/mathcoffee plan --workspace '/absolute/path/to/my video'
```

新工程是空白创作模板，`plan` 会返回 `incomplete`，直到填写正文、场景和数学状态。
没有模型或渲染依赖也能完成规划。配置字段见 [创作与配置接口](docs/project_interface.md)。

```sh
mathcoffee doctor --workspace '/absolute/path/to/my video'
mathcoffee setup --component render       # 仅显示准备步骤
mathcoffee setup --component speech       # 独立 Python 3.12 配音环境
mathcoffee setup --component model        # 固定公开权重、来源与大小
# 已授权执行准备时，给相应命令加 --execute。
# render 可加 --wheel 指定同一发行版的本地 wheel。

mathcoffee voice --workspace '/absolute/path/to/my video'              # 只准备请求
mathcoffee voice --workspace '/absolute/path/to/my video' --generate   # 本地离线合成
mathcoffee preview --workspace '/absolute/path/to/my video'
mathcoffee verify --workspace '/absolute/path/to/my video' --quality draft
mathcoffee status --workspace '/absolute/path/to/my video'
mathcoffee resume --workspace '/absolute/path/to/my video' --quality draft
```

低清全片技术检查通过后，完成真实画面审查并填写对应哈希绑定的 `reviews.json`，
才可运行 `mathcoffee render --workspace ... --quality final`。数学、叙事、听审、风格和
观众理解状态分别记录；自动 PASS 不代替这些判断。输出保存到用户工程，失败产物保留。

## 默认风格与配置

- `mathcoffee-shorts@1`：9:16、1080×1920/60，深色底、蓝／青对象、金色结果；
  默认有配音、无烧录旁白字幕，保留数学标签、公式和标题。
- `mathcoffee-longform@1`：16:9、1920×1080/60，独立横屏配色、标题／主图／公式区域；
  字幕策略独立配置，不将竖屏偏好强加横屏。
- 默认 Serena／science_female／全文本条件。可使用其他预置声音、本地 provider，
  或导入逐句 PCM；更换声音必须重新试听。不克隆真人、不调用收费合成 API。
- 两引擎共用解析后的颜色、字体、布局、字号和时窗。配置变更记录差异与身份；
  没有全局三分钟上限，不靠变速或裁尾挤入预算。

预设约定与校准边界见 [风格基线](docs/style_baseline.md)。自定义数学画面可在用户
工程提供 SceneBase 子类；框架不执行数学表达式字符串，也不会自动证明任意新主题。

## 开发与验证

先读 [Agent 约定](AGENTS.md)、[文档入口](docs/README.md) 和
[制作流程](docs/production_workflow.md)。裸 `make` 只显示帮助。

```sh
uv sync --locked --no-editable --extra render
make test-core
make test-speech                 # 使用独立 .venv-speech
make test-voice-qa               # 使用独立 .venv-voice-qa
make remotion-check
uv build --wheel                 # 后端在临时 staging 汇集白名单资源
mathcoffee bundle --host codex --wheel /absolute/path/to/wheel.whl --output /absolute/path/new-codex.zip
mathcoffee bundle --host claude --wheel /absolute/path/to/wheel.whl --output /absolute/path/new-claude.zip
```

自定义构建后端不提供 editable 安装；使用 wheel 或 `--no-editable`。
原有渲染及声音依赖版本保持锁定；准备系统 Cairo、TeX／中文字体、FFmpeg／FFprobe 后
再执行渲染安装。锁文件与源代码不等于新机器已经验收，实际状态见
[实施与验收状态](docs/implementation_status.md)、[后续路线图](docs/plugin_roadmap.md)。

仓库只纳入通用源码、配置、模板和测试。单期源码、媒体、权重、环境与本地验收工程
不入库；精确文件边界由 `repository-files.txt`、`make repository-check` 和历史检查保护。
第三方依赖与项目授权分开，见 [依赖说明](docs/dependencies.md)。
