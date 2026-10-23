[English](dependencies.md) | 简体中文

# 依赖与授权边界

项目原创代码采用 [Apache-2.0](../LICENSE)，另见根 [NOTICE](../NOTICE) 和
[README](../README.zh-CN.md)。第三方依赖、模型、字体和素材保留各自的条款。
原创代码授权、署名方式及 Plugin 打包边界须与第三方权限分别处理；保留上游声明
不等于项目拥有依赖或素材的版权。

| 组件 | 固定依据 | 分发范围 |
|---|---|---|
| Python 3.13／Manim 0.20.1 | `pyproject.toml`、`uv.lock` | 依赖声明与锁，环境不入库 |
| Node 24／Remotion 4.0.531 | 引擎 `package.json`、`package-lock.json` | 通用编排源码与锁，依赖和浏览器不入库 |
| Qwen MLX 本地配音 | `toolchains/speech/requirements.lock`、模型文件清单 | 适配代码、下载脚本及上游声明，模型不入库 |
| 声音一致性代理 | `toolchains/voice_qa/requirements.lock` | 可选工具与固定来源，模型不入库 |
| 科普声音／发音／程序配乐配置 | `src/mathcoffee/data/speech/`、`src/mathcoffee/data/audio/` | 通用 JSON，录音和成片不入库 |

Remotion 使用自己的许可条款，不能把它统称为 MIT 依赖。发布 Plugin、改变团队用途
或捆绑依赖前核对对应固定版本及[上游条款](https://www.remotion.dev/docs/license)；框架不设置
license key、接受新条款、申请账号或启用云渲染。声音运行时保留的上游许可证见
`toolchains/speech/LICENSE-*`。

本机字体、TeX 与 FFmpeg 不捆绑发布；依赖锁提供精确来源与哈希，不是全量许可审计。
外部素材必须另记作者、来源、许可与用途，未知许可的文件不能进入分发包。
