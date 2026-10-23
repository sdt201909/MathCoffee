[English](website.md) | 简体中文

# 主页维护

[MathCoffee 主页](https://sdt201909.github.io/MathCoffee/) 面向数学科普创作者，
以“开始创作”为主要入口，同时邀请社区参与维护。核心主张是“数学应是大众的，而非特权”。

网站独立于视频制作运行时。在仓库检出目录中使用 Node.js 24 即可开发，无需安装 Manim、
Remotion、Python 制作环境、TeX 或模型，也不需要录音及单期工程。

## 本地开发

在仓库根目录运行：

```sh
cd site
npm ci --ignore-scripts --no-audit --no-fund
npm run build
npm test
npm run preview
```

打开预览命令输出的地址，保留 `/MathCoffee/` 项目前缀。构建只把生成的网站写入仓库根目录的
`out/site/`。测试报告与截图放在 `out/site-review/`，不属于正式站点。

共享页面模板位于 `site/page.mjs`，中英文案位于 `site/content.mjs`，样式位于
`site/styles.css`。修改页面区域或控件时，两种语言都要完整更新。圆与正弦波示意为原创网页
代码，不代表制作插件导出的成片。

首次运行浏览器检查前安装测试浏览器：

```sh
npx playwright install chromium firefox webkit
npm run test:browser
```

本地只运行 Chromium 的快速检查：

```sh
BROWSER_PROJECTS=chromium npm run test:browser
```

Playwright WebKit 验证的是浏览器引擎，不能据此声称已在本机 Safari 应用中人工验收。
GitHub Actions 会在 Linux 上检查 Chromium、Firefox 与 WebKit 后再发布。
macOS 27 上的自动化 Firefox 可能因[上游应用数据访问问题](https://github.com/microsoft/playwright/issues/42768)
在载入页面之前启动失败；这与页面检查失败分别记录。不要为网站检查更改隐私权限或用户
Firefox 配置，可由 Linux 检查覆盖 Firefox。本机其他引擎可使用
`BROWSER_PROJECTS=chromium,webkit npm run test:browser`。
自动检查之外，另行查看桌面和手机布局，核对两种语言、两种配色、键盘焦点、图形标签、
减少动态效果设置及安装链接。

## 语言、主题与版本入口

根入口先使用记住的显式语言选择，再按浏览器语言偏好顺序匹配，最终回退英语。中文变体统一
使用简体中文。直接访问 `/en/` 或 `/zh/` 时保留该语言，保证分享链接结果稳定。手动切换
语言会记住选择，供以后访问根入口时使用。

主题选项为“系统、浅色、深色”，默认跟随系统并响应系统变化。偏好存储不可用时正常阅读；
关闭 JavaScript 后，两种静态语言页面仍可使用。网站不加入分析脚本、外部字体、账号系统、
模型调用或收费服务。

推广新版本时更新 `site/release.json`，保持显示版本、Codex 和 Claude Code 安装包地址及对应
版本的安装文档一致。首版指向 `v0.2.0-alpha.2`；不要用假定存在的“最新预发布版本”地址
替换显式下载链接。修改配置前确认两个完整插件 ZIP 确实存在，GitHub 自动生成的源码压缩包
不能替代完整安装插件包。

保留 Community Alpha 标记，并链接已发布的验证状态。提供宿主适配包与完成宿主真实加载、
空白 Mac 试用、人工风格确认和听审是不同结果。详见[实施状态](implementation_status.zh-CN.md)。

## 发布与仓库边界

`Website` 工作流检查 PR，但不发布 PR。`main` 上的网站变更或在 `main` 手动运行该工作流，
会先构建与检查再部署。流程固定官方 GitHub Actions 的提交 SHA，只有部署任务获得 Pages
写权限和 OpenID Connect 权限，无需额外部署密钥。参见 GitHub 的
[Pages 自定义工作流说明](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)。

仓库 Pages 发布来源设为 **GitHub Actions**，使用 `github-pages` environment，将正式部署
限制到 `main`，并保持 HTTPS。项目地址为 `https://sdt201909.github.io/MathCoffee/`，无需自定义
域名或独立服务器。部署后通过真实 HTTPS 地址检查根入口、两种语言页及实际安装包下载链接。

新增源码逐项登记到 `repository-files.txt`，保留现有媒体与单期内容禁令。原创图形使用内联
SVG 与系统字体；历史单集场景、视频、音频、模型、字体二进制、截图和构建产物不进入 Git。
Pages artifact 只上传 `out/site/`，不能上传仓库根目录或制作工程。

合入前检查仓库 guard 和真实分发包内容：网站源码、浏览器依赖、生成页面及审查产物不能进入
wheel 或两种宿主 Plugin ZIP；网站维护文档可随框架文档分发。文件清单和历史检查见
[仓库边界](repository_scope.zh-CN.md)。

源码分发包保留已审查的网站源码，以便依据完整文件清单重新构建；不包含
`node_modules`、生成的网站或浏览器检查产物。wheel 与宿主 ZIP 只携带相关文档，
不包含网站运行代码或浏览器测试依赖。
