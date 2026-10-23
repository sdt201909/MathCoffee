# Manim 与 Remotion 共用时间轴

Manim 负责可计算数学状态、几何及连续变换；Remotion 负责信息排版、镜头与片段编排。
两者读取同一创作数据和实际配音时间，不另写一套字幕正文。
统一 CLI 从 [Authoring v1](project_interface.md) 派生时间轴，通用组件读取同一份解析后
风格。Manim 绘制数学主体，Remotion 绘制标题、品牌及配置允许的旁白字幕，避免重复文字。

Python 侧契约为 [renderer_contract.py](../src/mathcoffee/renderer_contract.py)，
JavaScript 侧为 [schema.ts](../engines/remotion/src/schema.ts)。
基础契约允许偶数尺寸；当前通用合成版式限定横屏 16:9 与竖屏 9:16。

| 字段 | 约束 |
|---|---|
| `schema_version` | 整数 1 |
| `width/height/fps/duration_frames` | 偶数尺寸、1–120 整数帧率、正整数总帧数 |
| `clips[]` | 稳定 ID、renderer、素材相对路径／SHA-256、全局起帧、源入帧、长度 |
| `captions[]` | 原文、稳定 ID、全局起止帧 |
| `audio` | 默认单份预混音，48 kHz、双声道、精确样本数与 SHA-256；显式无声用途允许 null |
| `qa.anchor_frames` | 可选的两帧测量闪点，不属于正式观众内容 |

区间统一为 `[start, end)`，按时间排序，不重叠且在全片内。源视频音轨静音，旁白只
来自预混音；字幕只在最终编排层烧录。v1 不表示 29.97 帧率，不能静默按 30 解释。
字幕可留空以生成无旁白字幕版本；图中必要标签与公式仍由场景表达。
可选 `style` 携带解析后的颜色、字体、布局和字幕策略；不含 style 的旧 v1 时间轴仍可读取。
竖屏候选预设默认不烧录旁白字幕，横屏配置独立，见[候选风格基线](style_baseline.md)。

每次渲染只暴露专用 `public/` 素材目录。拒绝 URL、绝对路径、上级路径和越界符号链接。
预检核对实际视频尺寸、帧率、源帧范围，以及混音样本数和所有媒体哈希。
通过预检不代表数学正确、发音准确、受众理解或完整视听审查通过。

## 运行

JavaScript 精确依赖由 `engines/remotion/package-lock.json` 锁定；Manim 使用独立
Python 3.13 和 `uv.lock`，不因安装辅助引擎升级历史依赖。

安装版使用 `mathcoffee preview --workspace <用户工程>` 生成低清，再以 `verify`、
`status` 和 `resume` 核验或恢复。渲染 Python、Node、浏览器和独立 Remotion 引擎位置
由 runtime 配置解析，插件安装目录只读。框架不在渲染时偷偷下载浏览器；缺失时返回
准备要求。运行时准备需显式执行 `setup`，详见根 [README](../README.md)。

下面是保留的源码工程调用：

```sh
make remotion-setup
make remotion-check
make remotion-browser

.venv/bin/python scripts/validate_renderer_timeline.py \
  /absolute/path/timeline.json --assets /absolute/path/public

node engines/remotion/render.mjs \
  --props /absolute/path/timeline.json \
  --public-dir /absolute/path/public --output /absolute/path/new-film.mp4
```

竖屏使用独立 `render-shorts.mjs` 与 `shorts` 数据字段，详见
[引擎 README](../engines/remotion/README.md)。输出必须使用新路径；`--no-audio` 是
显式无声用途，默认生产入口要求预混音。所有动画由帧号决定，不依赖墙上时钟。

渲染收据记录输入、代码、依赖、浏览器和输出哈希，并复核运行期间输入未改变。
正文、风格、状态、声音或实现身份变化后，旧构建保留且不能作为当前构建的验收依据。
高清入口要求相同身份的低清技术检查通过，并由真实画面审查提供绑定成片哈希的
`reviews.json`，没有 force 绕过参数；数学、叙事与实际听审仍需分别记录。
最终容器仍需完整解码、字幕边界、编码后声音同步及中间动作审查。该仓库没有携带
以往作品的技术验收记录；测试结果不能当作任意新作品已通过验收的依据。
