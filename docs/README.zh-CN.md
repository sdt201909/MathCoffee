# 框架文档入口

[English](README.md) | 简体中文

此仓库保留 MathCoffee 的通用制作能力，不包含频道单期的场景、正文、媒体或交付记录。

| 文档 | 用途 |
|---|---|
| [全新 Mac 安装](installation.zh-CN.md) | 系统依赖、独立运行时与首次使用 |
| [Agent 约定](../AGENTS.zh-CN.md) | 工作区保护、独立环境、审查与可恢复清理 |
| [制作流程](production_workflow.zh-CN.md) | 从 brief 到可核验交付 |
| [创作与配置接口](project_interface.zh-CN.md) | 用户工作区、Authoring v1、CLI 与构建恢复 |
| [候选风格基线](style_baseline.zh-CN.md) | 横竖屏预设、语义颜色、节奏与确认边界 |
| [受众约定](audience_contract.zh-CN.md) | 问题链、显示文案与片尾边界 |
| [双引擎接口](engine_integration.zh-CN.md) | 同一时间轴、素材契约与渲染入口 |
| [配音管线](voice_pipeline.zh-CN.md) | 本地 provider、词典、真实句窗与试听边界 |
| [依赖与授权边界](dependencies.zh-CN.md) | 运行时锁、第三方声明与待审项目 |
| [实施与验收状态](implementation_status.zh-CN.md) | 已实现内容、验证范围与仍待完成的门槛 |
| [Plugin 路线图](plugin_roadmap.zh-CN.md) | 分阶段目标和发布前要求 |
| [仓库边界](repository_scope.zh-CN.md) | 文件白名单、历史隔离与后续提交方式 |
| [参与贡献](../CONTRIBUTING.zh-CN.md) | 社区改动、检查和审查约定 |

制作一期时，在本地工程建立本期 brief 和唯一 authoring 来源；数学说明、旁白、
实际句窗、场景与交付记录使用相同稳定 ID。文档里的 `episode`、`example` 是占位名，
对应文件由具体制作任务提供，仓库没有内置成片样例。

安装者先按根 [README](../README.zh-CN.md) 建立独立工作区，再填写创作源。框架代码、运行时、
模型缓存与用户作品分开存放；不能把插件目录当作本期工程。候选预设尚待作者看片与
听音确认，安装或自动检查成功均不代表这一门槛已经完成。
