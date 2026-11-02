# Playbook Testing — Codex Plugin

依据微软 ISE Engineering Playbook，按项目模块、风险和交付阶段选择测试动作，补建缺失测试，再接入 **Codex hooks、Git hooks 与 CI/CD 门禁**。已有测试用于发现和补齐缺口；新项目先建立验收标准与真实测试。

流程：验收标准 → 风险与用例 → 开发反馈 → 提交/推送检查 → PR 门禁 → 部署后冒烟 → 发布验证 → 生产回归。测试动作、check ID、触发阶段和待接入条件记录在项目 `TESTING.md` 或已有测试计划中。

## 安装

需要 Git、Python 3.10+ 和支持插件命令的 Codex CLI。统一使用原生插件命令，三平台使用同一来源和插件标识。

Windows PowerShell：

```powershell
codex plugin marketplace add JingchaoGu/Testing --ref main
if ($LASTEXITCODE -ne 0) { throw 'Marketplace registration failed' }
codex plugin add playbook-testing@testing-playbook
```

Linux / macOS：

```sh
codex plugin marketplace add JingchaoGu/Testing --ref main &&
codex plugin add playbook-testing@testing-playbook
```

安装或更新后，在目标项目开启新会话并运行 `$playbook-testing init`。Windows hooks 使用 `py -3`，Linux/macOS 使用 `python3`。曾安装同名独立 skill 时应停用旧副本，避免遮蔽插件入口。

### Hook 信任

与 [Impeccable](https://github.com/pbakaus/impeccable) 一样，使用 `.codex-plugin/plugin.json`、默认 `hooks/hooks.json` 和统一 skill 命令。**安装插件与项目启用均不授予 hook 信任**；用户需在同一 Codex 的 `/hooks` 审阅 Playbook Testing。没有受支持的自动批准接口，skill 不写入信任记录。机制见 [Codex Hooks](https://learn.chatgpt.com/docs/hooks)。

`$playbook-testing hooks status` 通过原生只读接口核实发现/信任状态，输出所用 CLI 路径与版本。PATH 指向另一版本时，诊断脚本可用 `--codex <当前宿主的可执行文件>`。未发现应先排查加载；待信任应完成用户审阅；无法查询则明确报告未知。项目开关开启但原生状态未确认时返回非零。

版本 0.6.0 修复旧包“skill 可加载、原生 hooks 为零”的打包兼容问题，并改用 JSON 的 `commandWindows` 字段。使用当前宿主复核后，才报告 hooks 已登记。`.testing-results/last-hook-event.json` 记录处理器收到的事件；`origin=direct` 的手工调用不证明 Codex 派发。

## 使用

只有一个主 skill，`setup` 已合并进 `init`：

```text
$playbook-testing init
$playbook-testing plan
$playbook-testing check pr
$playbook-testing fix
$playbook-testing doctor --runtime
$playbook-testing hooks status
$playbook-testing pin check doctor fix
```

| 命令 | 用途 |
| --- | --- |
| 无参数 | 展示菜单和配置状态 |
| `init` | 制定策略、补建测试并默认处理各阶段接入 |
| `plan` | 按模块/风险提出具体用例、测试层次、阶段与退出条件 |
| `check [阶段]` | 运行真实检查；默认 task-finish |
| `fix [阶段]` | 根据失败证据最小修复、补回归并复测 |
| `doctor [--runtime]` | 静态配置诊断；runtime 额外查询原生 hooks |
| `hooks status/on/off` | 核实状态或切换当前项目 opt-in，保留 Git hooks |
| `pin/unpin <命令...>` | 注册/移除项目 `$pt-check` 等快捷 skill |

`ci` 是 init 的 CI/CD 范围快捷入口；`release` 复用 check release。它们没有独立的重复流程。`$playbook-testing` 和 `$pt-check` 是 skill 调用，不是 shell 程序或新增内置斜杠命令。快捷入口写在项目 `.agents/skills/`，保留外部或用户修改的文件。

空目录先确认技术栈和最小功能，再创建代码、真实测试及本地 Git；已提供的信息不重复询问。仅生成空策略不算完成初始化。初始化不自动提交、推送或部署。详见 [初始化](skills/playbook-testing/references/init.md) 与 [测试动作决策](skills/playbook-testing/references/test-actions.md)。

## 默认阶段

| 阶段 | 默认接入 | 生效条件 |
| --- | --- | --- |
| edit / task-finish | Codex PostToolUse / Stop；SessionStart 加载上下文 | 实际检查、预算、项目 opt-in、原生发现和用户信任 |
| commit / push | Git pre-commit / pre-push，保留已有链路 | 实际 index / 各候选 commit 的独立快照检查 |
| pr | PR、更新、合并队列和最终 gate | 实际 CI 作业及服务端 required checks |
| deployed / release / production | 真实部署后、晋级前和生产发布后检查 | CD 调用、环境、完整 commit、不可变产物及权限 |

GitHub 默认准备 `playbook-quality.yml` 和可复用的 `playbook-delivery.yml`；已有其他平台沿原机制接线。release 先验证 deployed，通过后才运行 release。没有真实 CD/环境时，交付可接入文件并记录具体待绑定条件。文件存在、实际触发和执行通过分别报告，见 [默认阶段接入](skills/playbook-testing/references/default-hooks.md)。

edit 仅用于快速反馈，允许 TDD 暂时失败；task-finish 验证本地完成，失败最多自动请求一次修复。edit/task-finish 配置超时总和上限分别为 100/150 秒；长测进入 Git/CI。Git 本地 hooks 可绕过，正式合并与发布依赖服务端规则和环境审批。

## 运行器与证据

skill 的管理/诊断使用当前安装插件 `scripts/testing.py`；项目 Git/CI 使用 `.testing-tools/` 中的独立副本，升级时保留项目定制。手工接入入口为 `scripts/setup_repo.py --repo <项目> [--init-git] [--github-workflow]`；实际运行配置只有 `.testing-policy.json`。

阶段名：`edit`、`task-finish`、`commit`、`push`、`pr`、`deployed`、`release`、`production`。push 必须使用 Git pre-push 的真实 stdin refs。环境阶段经 delivery_hook 绑定真实候选；不接受缺失的环境和产物。

`.testing-results/` 保存每轮日志、JUnit、证据与阶段记录，应保持 Git 忽略。失败、零测试、全跳过、缺报告、超时或验证中输入改变都不能通过；先保留首次失败再修复。配置、JUnit 和 JSON 均不构成防篡改证明。

- [配置](docs/configuration.md)
- [Playbook 原则与来源](skills/playbook-testing/references/core-model.md)
- [代理 hooks 排障](skills/playbook-testing/references/agent-hooks.md)
- [信任边界与限制](docs/limitations.md)

## 开发与分享

```sh
python3 scripts/quality.py run --stage pr
python3 scripts/quality.py verify --stage pr
python3 scripts/package_plugin.py
```

默认输出 `dist/playbook-testing-0.6.0.zip`，包含一个主 skill、原生插件清单、hooks、脚本、模板、说明和本地 marketplace，不包含凭据、目标项目策略或报告。解压后可用 `codex plugin marketplace add ./playbook-testing` 注册，再执行相同的 plugin add 命令。

本仓库 CI 在 Windows/Linux/macOS 验证 Git 快照、失败路径、证据和**真实 Codex 插件安装及 hook 发现**；原生测试保持待信任状态，不代替用户批准，也不宣称已验证桌面端实际事件派发。执行器仅使用 Python 标准库。

带 hooks 的插件分发与公共目录支持以 [OpenAI 打包说明](https://developers.openai.com/plugins/build/plugins) 为准。本插件不是微软或 OpenAI 官方产品。
