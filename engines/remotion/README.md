# Remotion 编排引擎

本目录提供可复用的横屏与竖屏合成入口。Manim 片段负责数学状态与几何，
Remotion 读取整数帧时间轴，组合画面、字幕和唯一的预混音。
仓库不附带任何单期节目、旁白、视频或模型权重。

## 环境与安装

要求 Node 24、npm、FFmpeg/ffprobe。当前锁定 Remotion 4.0.531、React 19.2.3、
TypeScript 5.9.3；使用锁文件安装，不修改 Python 环境。

```sh
cd engines/remotion
npm ci --ignore-scripts --no-audit --no-fund --cache .npm-cache --registry https://registry.npmjs.org
npm run browser:ensure
npm run typecheck
npm test
```

安装命令会下载 npm 包，`browser:ensure` 会准备本地 Chrome Headless Shell。
正式制作前应单独完成依赖与浏览器准备。字体使用系统字体，当前样式以 Apple Silicon
Mac 上的中文字体为基线；其他平台须核验字体替代、布局和浏览器可用性。

## 渲染

`MathCoffeeTimeline` 横屏入口使用 16:9；`MathCoffeeShorts` 竖屏入口使用 9:16。
输入与输出均须为绝对路径，所有素材 `file` 字段均相对于专用素材目录。

```sh
node render.mjs \
  --props /absolute/path/timeline.json \
  --public-dir /absolute/path/dedicated-public \
  --output /absolute/path/new-landscape.mp4 \
  --browser-executable /absolute/path/chrome

node render-shorts.mjs \
  --props /absolute/path/portrait-timeline.json \
  --public-dir /absolute/path/dedicated-public \
  --output /absolute/path/new-portrait.mp4 \
  --browser-executable /absolute/path/chrome
```

横屏可省略浏览器参数，由 Remotion 查找或准备兼容浏览器；竖屏省略时使用
`node_modules/.remotion/` 下的 Apple Silicon Chrome Headless Shell。
显式传入本地浏览器路径可固定实际使用的程序。渲染和单元测试不调用云渲染服务。

无声试验必须同时使用 `audio: null` 和 `--no-audio`；该开关拒绝丢弃已声明的混音。
竖屏还支持 `--no-captions`，以及 `--still-frame N` 导出新路径的 PNG。
输出文件或回执已存在时拒绝覆盖。失败产物保留供诊断，重试应使用新输出路径。

## 共用契约

[`src/schema.ts`](src/schema.ts) 定义基础时间轴：

- `schema_version: 1`，偶数宽高、1–120 的整数帧率、正整数总帧数。
- `clips`：稳定 `id`、`renderer`、`file`、`sha256`、`start_frame`、
  `source_in_frame`、`duration_frames`。素材尺寸和帧率须与目标相同。
- `captions`：稳定 `id`、`text`、`start_frame`、`end_frame`。
- `audio`：唯一的 48 kHz 双声道预混音，`samples` 必须精确覆盖全片；源视频静音。
- `qa.anchor_frames`：可选测试锚点，每个锚点显示两帧白块。

区间采用 `[start, end)`，按时间排序且不得重叠。URL、绝对素材路径、上级路径、
越界符号链接及源哈希不符均被拒绝。专用素材目录只能放本次有权使用的输入，
不要把项目根或用户目录直接作为 `public-dir`。

横屏画面全幅显示输入片段，空档显示深色背景，字幕覆盖逻辑 1920×1080 下的
`x=64, y=950, width=1792, height=110` 区域；输入几何应预留字幕空间。
横屏本身不添加节目标题、品牌或默认正文。

竖屏扩展见 [`src/shorts-schema.ts`](src/shorts-schema.ts)：`shorts` 包含期号、品牌、
栏目、标题时窗和可选片尾、黑帧、字幕开关；这些显示字符串均来自输入数据。
标题最多16字符，副标题24字符；字幕最多两行、每行18字符。默认注册数据仅为
中性占位，不代表任何一期内容。注册占位数据不显示旁白字幕；正式输入应显式设置
`show_captions`，该字段省略时契约沿用显示字幕的兼容行为。

## 回执与验证边界

渲染回执保存输入、素材、源码、依赖版本、浏览器和产物的 SHA-256 及真实媒体参数，
并在渲染后复核输入未变化。竖屏另输出显示文字清单，并通过原生 FFmpeg 对完整
预混音做一次 AAC 编码，复制视频流后核对精确容器音频时钟。

`npm test` 检查契约、路径隔离、CLI 与输出保护；`npm run typecheck` 检查类型。
它们不启动浏览器，不证明实际画面、字体、可读性、配音读法或声画同步通过。
正式交付仍需低清全片审查、高清容器检查、实际编码音轨验证和听审。

## 第三方依赖

锁文件只固定依赖版本，不替代依赖的许可证。Remotion 等第三方组件保留各自授权
条件；本项目未来的代码授权不覆盖它们。Plugin 分发前需明确依赖安装与分发边界，
并核对锁定版本随包附带的许可证及[Remotion 官方说明](https://www.remotion.dev/docs/license)。
本目录不配置账号、license key、云渲染、付费 API 或外部素材服务。
