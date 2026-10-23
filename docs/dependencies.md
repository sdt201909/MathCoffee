# 依赖与授权边界

本仓库目前为私有开发基础，尚未选择项目开源许可证。准备公开发布时，需要独立
确定原创代码授权、署名方式及 Plugin 打包边界；保留第三方声明不等于整个项目已开源。

| 组件 | 固定依据 | 分发范围 |
|---|---|---|
| Python 3.13／Manim 0.20.1 | `pyproject.toml`、`uv.lock` | 依赖声明与锁，环境不入库 |
| Node 24／Remotion 4.0.531 | 引擎 `package.json`、`package-lock.json` | 通用编排源码与锁，依赖和浏览器不入库 |
| Qwen MLX 本地配音 | `toolchains/speech/requirements.lock`、模型文件清单 | 适配代码、下载脚本及上游声明，模型不入库 |
| 声音一致性代理 | `toolchains/voice_qa/requirements.lock` | 可选工具与固定来源，模型不入库 |
| 科普声音／发音／程序配乐配置 | `assets/speech/`、`assets/audio/` | 通用 JSON，录音和成片不入库 |

Remotion 使用自己的许可条款，不能把它统称为 MIT 依赖。发布 Plugin、改变团队用途
或捆绑依赖前核对对应固定版本及上游条款；本次没有设置 license key、接受新条款、
申请账号或启用云渲染。声音运行时保留的上游许可证见 `toolchains/speech/LICENSE-*`。

本机字体、TeX 与 FFmpeg 不捆绑发布；依赖锁提供精确来源与哈希，不是全量许可审计。
外部素材必须另记作者、来源、许可与用途，未知许可的文件不能进入分发包。
