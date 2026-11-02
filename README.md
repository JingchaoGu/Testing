# Playbook Testing — Codex Plugin

将微软 ISE Engineering Playbook 的测试原则落成可执行的 **skill + Codex hooks + Git hooks + CI/CD 检查入口**。Python 3.10+，只使用标准库；需要 Git。仓库默认不启用代理自动执行。

核心流程：验收标准 → 用例与风险 → 开发快速反馈 → 提交/推送检查 → PR 门禁 → 部署后冒烟 → 发布验证 → 生产缺陷回归。

## 安装与分享

前置条件：Git、Python 3.10+、Codex CLI 已安装并可从终端调用。仓库是私有的，需先通过 Git 凭据管理器、SSH 等现有方式取得访问权限；不需要将 token 写进命令。

### 快速安装：Windows PowerShell

```powershell
codex plugin marketplace add JingchaoGu/Testing --ref main
if ($LASTEXITCODE -ne 0) { throw 'Marketplace registration failed' }
codex plugin add playbook-testing@testing-playbook
```

### 快速安装：Linux

```sh
codex plugin marketplace add JingchaoGu/Testing --ref main &&
codex plugin add playbook-testing@testing-playbook
```

### 快速安装：macOS

```sh
codex plugin marketplace add JingchaoGu/Testing --ref main &&
codex plugin add playbook-testing@testing-playbook
```

三平台使用同一个 marketplace 与插件标识。`plugin add` 需要支持该子命令的 CLI；旧版可在注册后到桌面端插件目录的 `Testing Playbook` 来源安装 `Playbook Testing`。参见 [Codex CLI 插件命令](https://learn.chatgpt.com/docs/cli/reference)。

### 带检查与旧版兼容的安装脚本

已克隆或已解压插件包时，可直接运行以下脚本。脚本检查依赖、注册 marketplace，并检测 CLI 是否支持直接安装；不支持时明确提示桌面端安装，失败时保留非零退出码。

Windows PowerShell（从仓库根执行）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

Linux / macOS（从仓库根执行）：

```sh
sh ./scripts/install.sh
```

`ExecutionPolicy Bypass` 仅作用于这一次脚本进程，不修改系统策略。私有仓库不采用匿名 raw 下载后执行的命令。需要源码时先使用 `git clone https://github.com/JingchaoGu/Testing.git`。

安装后开启新会话，运行插件 setup，并通过 `/hooks` 审阅并信任当前 hook 定义。Windows hooks 使用 `py -3`，macOS/Linux 使用 `python3`。安装脚本不安装项目 Git hooks、不改变远端分支规则，也不写入 hook 信任记录。

使用本地包时，解压生成的 ZIP 后，可将解压出的插件根目录作为本地 marketplace 添加：`codex plugin marketplace add ./playbook-testing`，再执行同一个 `codex plugin add` 命令。

目前带生命周期 hooks 的插件适合 Codex 桌面端手动安装/本地或团队分发，不能直接提交公共插件目录。hooks 需要本地执行环境及用户信任；云端编排不保证运行这些脚本。参见 [OpenAI 打包说明](https://developers.openai.com/plugins/build/plugins) 和 [Hooks](https://learn.chatgpt.com/docs/hooks)。

## 接入一个项目

在目标项目调用：

```text
使用 Playbook Testing 的 setup，为此仓库配置实际测试命令，接入 Codex 与 Git hooks，并生成 PR 门禁。
```

手工接入也可以：

```sh
python3 /path/to/Testing/scripts/setup_repo.py --repo /path/to/project --github-workflow
# 编辑项目 .testing-policy.json，填写真实命令和所需阶段。
python3 /path/to/project/.testing-tools/quality.py run --repo /path/to/project --stage pr
python3 /path/to/project/.testing-tools/install_git_hooks.py --repo /path/to/project
```

Windows 将 `python3` 换成 `py -3`。接入工具只写项目本地文件；遇到不同内容的已有文件或自定义 Git hook 管理器会保留并提示人工合并。

设置 `agent_hooks: true` 才启用该项目的代理测试。`edit` 用于快速反馈，允许 TDD 的暂时失败；`task-finish` 在结束时检查。失败最多自动请求一次继续修复，仍失败则要求明确报告未验证，不把结果改成通过。

## 已实现能力

| 入口 | 行为 |
| --- | --- |
| Codex `SessionStart` | 加载项目测试上下文，不自动建立测试策略 |
| Codex `PostToolUse` | 文件快照改变后运行 edit；重复无变更事件不重复测试 |
| Codex `Stop` | 验证本次会话改动的 task-finish，防止无限继续 |
| Git pre-commit | 导出真实 index tree 测试，保留未暂存修改与未跟踪文件 |
| Git pre-push | 从 stdin 读取全部 ref，验证每个不同候选 commit，处理新分支和删除 |
| PR/合并队列 | 运行项目必需检查；验证同一代码快照的报告，汇总作业必须成功 |
| 部署/发布/生产阶段 | 必须先 smoke；要求环境和产物标识；失败停止后续检查 |

共享入口：`quality.py run --stage STAGE`。阶段名为 `edit`、`task-finish`、`commit`、`push`、`pr`、`deployed`、`release`、`production`。push 由 `quality.py git-hook pre-push` 读取 Git 的 ref 输入。

结果写入项目 `.testing-results/`：每轮独立目录、命令日志、JUnit、证据 JSON，以及阶段最新记录。测试失败、零测试、全跳过、报告缺失、超时或输入在验证中发生变化都不能通过。先保留首次失败，再进行有界修复和复测。结果目录应保持 Git 忽略。

## 配置、验证和限制

- [命令与阶段配置](docs/configuration.md)
- [Playbook 原则、适配决策与来源](skills/playbook-testing/references/core-model.md)
- [信任边界与已知限制](docs/limitations.md)

本插件提供执行和证据，不自动保证用例充分、业务验收正确或生产安全。Git 本地 hooks 可绕过；正式合并依赖服务端 required check，发布审批依赖项目环境规则。模板不包含真实业务部署、压力实验或生产探针，需按项目风险接入其实际命令。

## 开发与打包

```sh
python3 -m unittest discover -s tests -v
python3 scripts/quality.py run --stage pr
python3 scripts/quality.py verify --stage pr
python3 scripts/package_plugin.py
```

ZIP 默认输出到 `dist/playbook-testing-0.1.1.zip`。包含插件清单、两个 skills、hooks、脚本、模板、说明和本地 marketplace；不打包 Git 数据、测试报告、缓存、目标项目策略或凭据。

本仓库 CI 在 Linux、Windows 与 macOS 上验证实际提交/推送 hook、安装脚本和失败路径，并构建分发包。它不会部署应用。源自微软 Playbook 的原则均在参考资料中注明；该插件并非微软或 OpenAI 的官方产品。
