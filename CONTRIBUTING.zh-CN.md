[English](CONTRIBUTING.md) | 简体中文

# 参与 MathCoffee 维护

欢迎使用英文或中文参与。先读 [README](README.zh-CN.md)、[安装指南](docs/installation.zh-CN.md)、
[文档入口](docs/README.zh-CN.md) 和 [Agent 工作约定](AGENTS.zh-CN.md)。较大改造请先通过 issue
讨论；小而聚焦的修复可以直接提交 pull request。

## 仓库接收哪些内容

欢迎通用制作组件、宿主适配、配置、文档和测试。使用原创、合成的测试夹具说明问题，
不要引入一套完整视频制作工程。框架应独立于某一期节目或某位维护者的机器。

不要提交单期源码、authoring 或旁白、媒体、模型权重、字体、录音、虚拟环境、缓存、
凭据或私有日志。被 Git 忽略不代表可删除。用户作品放在插件安装目录之外，更新时保留。

新增框架文件时，先审查内容与授权，再把准确路径加入 `repository-files.txt`，显式暂存。
仓库检查也覆盖提交历史；先提交禁止资产、再删除，并不会把它从历史中清除。

## 如何修改

1. 保持唯一 authoring 来源，以及稳定的场景、句子、状态与事件 ID。共用数学数值和几何
   不应在引擎、声音和字幕之间分叉。
2. 多 Agent 协作时按文件指定唯一写入者。让改动聚焦，说明修改前后的行为，并同步受影响
   的接口和中英文文档。
3. 添加或运行覆盖真实变更与兼容边界的检查。优先用小型可复现夹具，不以昂贵的全片渲染
   替代有针对性的测试。明确哪些检查未跑。
4. 视觉或声音修改需要真实媒体时，把验收工程保存在仓库之外，记录源、产物身份和实际审查
   范围。不要在公开 issue 或 pull request 附上私有旁白或资产。

## 相关检查

已有合适的独立环境后，可执行：

```sh
make test-core
make test-speech
make test-voice-qa
make remotion-check
make repository-check
.venv/bin/python scripts/repository_guard.py --ref HEAD --history
```

完整 core 测试包含渲染组件导入。规划与打包修改可使用以下轻量子集，不需要 Manim、
声音模型或浏览器：

```sh
PYTHONPATH=src python -m unittest \
  tests.test_project_style tests.test_cli_runtime tests.test_plugin_bundle \
  tests.test_repository_guard tests.test_bootstrap
uv build --wheel
```

Ubuntu CI 检查该子集、安装包和 Remotion 契约／类型，不证明 Apple Silicon 渲染、真实
宿主加载、数学正确性、默认风格或实际发音已经验收。不要为文档或简单规划修改调用
收费服务、下载声音模型或渲染历史作品。

数学或叙事改动需要说明假设、推导和仍存边界。视觉改动需区分边界测量、编码帧抽样与
完整动态审查。声音改动需区分文字／信号检查与真实试听，并在适用时检查最终编码音轨。
技术 PASS 不能替人签署人工审查。

## Pull request 与授权

按模板说明使用者能看到的变化、相关检查、限制，以及依赖或再分发范围变化。不要把未跑
检查写成通过，不夹带无关格式化或单期制作工作。

只提交你有权按项目 [Apache-2.0 许可证](LICENSE) 贡献的材料。保留第三方要求的声明与署名，
标明不同条款的内容。项目许可证不替代依赖、模型、字体、音乐或其他素材的许可。另见
[依赖边界](docs/dependencies.zh-CN.md) 和 [第三方声明](THIRD_PARTY_NOTICES.md)。

安全漏洞请按 [SECURITY.md](SECURITY.zh-CN.md) 私下报告，不要把利用细节或秘密放进公开 issue。
