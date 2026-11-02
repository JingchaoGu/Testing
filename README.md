# Playbook Testing — Codex Plugin

将微软 ISE Engineering Playbook 的测试原则落成可执行的 **skill + Codex hooks + Git hooks + CI/CD 检查入口**。Python 3.10+，只使用标准库；需要 Git。仓库默认不启用代理自动执行。

核心流程：验收标准 → 用例与风险 → 开发快速反馈 → 提交/推送检查 → PR 门禁 → 部署后冒烟 → 发布验证 → 生产缺陷回归。

## 安装与分享

前置条件：Git、Python 3.10+、Codex CLI 已安装并可从终端调用。仓库现已公开，下载不需要 GitHub token。

统一使用 Codex 原生插件命令安装。

### 快速安装：Windows PowerShell

```powershell
codex plugin marketplace add JingchaoGu/Testing --ref main
if ($LASTEXITCODE -ne 0) { throw 'Marketplace registration failed' }
codex plugin add playbook-testing@testing-playbook
```

### 快速安装：Linux / macOS

```sh
codex plugin marketplace add JingchaoGu/Testing --ref main &&
codex plugin add playbook-testing@testing-playbook
```

三平台使用同一个 marketplace 与插件标识。`plugin add` 需要支持该子命令的 CLI；旧版可在注册后到桌面端插件目录的 `Testing Playbook` 来源安装 `Playbook Testing`。参见 [Codex CLI 插件命令](https://learn.chatgpt.com/docs/cli/reference)。

安装后在目标项目开启新会话，运行 `$playbook-testing init`，并通过 `/hooks` 审阅并信任当前 hook 定义。Windows hooks 使用 `py -3`，macOS/Linux 使用 `python3`。安装携带 Codex hooks；项目初始化负责测试策略和 Git hooks；远端分支规则与 Codex 信任由各自平台管理。

若此前安装过同名独立 skill，确认新版插件可用后停用旧副本，避免调用到旧版入口。

使用本地包时，解压生成的 ZIP 后，可将解压出的插件根目录作为本地 marketplace 添加：`codex plugin marketplace add ./playbook-testing`，再执行同一个 `codex plugin add` 命令。

目前带生命周期 hooks 的插件适合 Codex 桌面端手动安装/本地或团队分发，不能直接提交公共插件目录。hooks 需要本地执行环境及用户信任；云端编排不保证运行这些脚本。参见 [OpenAI 打包说明](https://developers.openai.com/plugins/build/plugins) 和 [Hooks](https://learn.chatgpt.com/docs/hooks)。

## 命令使用流程

采用与 [Impeccable](https://github.com/pbakaus/impeccable) 类似的“安装 → 初始化 → 统一命令 → 可选快捷入口”流程。在 Codex 聊天中调用：

```text
$playbook-testing init
$playbook-testing plan
$playbook-testing check
$playbook-testing check pr
$playbook-testing fix
$playbook-testing doctor
$playbook-testing hooks status
$playbook-testing pin check doctor fix
```

`init` 发现项目已有测试并配置真实命令，默认接入项目代理检查和 Git pre-commit/pre-push；可以附加“只配置代理 hooks”等范围约束。CI 用 `$playbook-testing ci` 单独接入，或在 init 时明确要求。空测试策略不会被当作初始化完成。

| 命令 | 用途 |
| --- | --- |
| 不带参数 | 展示菜单；不自动修改项目 |
| `init` | 项目发现、测试映射、验证、hook 接入 |
| `plan` | 从验收标准与风险制定分阶段方案 |
| `check [阶段]` | 运行现有检查，默认 task-finish；失败返回失败 |
| `fix [阶段]` | 读失败证据、最小修复、必要回归并复测 |
| `doctor` | 只读检查配置与证据，明确尚未核实的信任/远端规则 |
| `hooks status/on/off` | 查看/切换当前项目的代理检查，不删除 Git hooks |
| `ci` | 复用测试策略接入 PR/合并队列及汇总 gate |
| `release` | 验证已有部署候选，先 smoke；不执行部署或代替审批 |
| `pin/unpin <命令...>` | 注册/移除 `$pt-check` 等项目快捷 skill |

pin 后可以调用 `$pt-check pr`、`$pt-doctor`、`$pt-fix`。快捷入口写入 `.agents/skills/pt-<命令>/SKILL.md`，可提交给团队共享；重复 pin 不改同样内容，同名外部 skill、用户修改及链接目录会被保留。unpin 仅删除生成且未被修改的文件。技能列表未刷新时开启新会话。

`$playbook-testing` 与 `$pt-check` 是 **Codex skill 调用**，不是 shell 命令或新增的 Codex 内置斜杠命令。`init/plan/fix/ci/release` 由代理结合项目完成；执行器不会凭空产生测试或验收结论。参见 [Skills 调用方式](https://learn.chatgpt.com/docs/build-skills)。

## 终端与项目接入

手工接入或接入其他自动化时：

```sh
python3 /path/to/Testing/scripts/setup_repo.py --repo /path/to/project --github-workflow
# 编辑项目 .testing-policy.json，填写真实命令和所需阶段。
python3 /path/to/project/.testing-tools/testing.py check --repo /path/to/project --stage pr
python3 /path/to/project/.testing-tools/testing.py hooks on --repo /path/to/project
python3 /path/to/project/.testing-tools/install_git_hooks.py --repo /path/to/project
python3 /path/to/project/.testing-tools/testing.py doctor --repo /path/to/project
python3 /path/to/project/.testing-tools/testing.py pin check doctor --repo /path/to/project
```

Windows 将 `python3` 换成 `py -3`。接入工具只写项目本地文件；遇到不同内容的已有文件或自定义 Git hook 管理器会保留并提示人工合并。

设置 `agent_hooks: true` 且信任定义后才启用该项目的代理测试。`hooks on` 验证 edit/task-finish 非空且配置超时总和分别不超过 100/150 秒，给事件超时留出余量；长测放入 Git/CI。`edit` 用于快速反馈，允许 TDD 的暂时失败；`task-finish` 在结束时检查。失败最多自动请求一次继续修复，仍失败则要求明确报告未验证，不把结果改成通过。

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

ZIP 默认输出到 `dist/playbook-testing-0.2.1.zip`。包含插件清单、两个 skills、命令路由、hooks、脚本、模板、说明和本地 marketplace；不打包 Git 数据、测试报告、缓存、目标项目策略或凭据。

本仓库 CI 在 Linux、Windows 与 macOS 上验证实际提交/推送 hook、命令、证据和失败路径，并构建分发包。它不会部署应用。源自微软 Playbook 的原则均在参考资料中注明；该插件并非微软或 OpenAI 的官方产品。
