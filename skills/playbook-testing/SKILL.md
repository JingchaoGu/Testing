---
name: playbook-testing
description: "依据 Microsoft Engineering Playbook，按模块风险与交付阶段制定、补建和执行测试，并接入 Codex/Git/CI/CD 门禁。支持 init、plan、check、fix、doctor、hooks 和项目快捷入口；用于新项目引导、测试缺口建设、分阶段验证与 hook 排障。"
---

# Playbook Testing

以验收标准和风险决定各部分该测什么、何时测及怎样放行，再补建测试、接入触发点并核实证据。已有测试是可复用资产，不决定测试范围。原文依据在 [核心模型](references/core-model.md)。

## 入口

显式调用 `$playbook-testing <命令> [参数或自然语言约束]`，按 [命令路由](references/commands.md) 执行。无参数时展示菜单与项目配置状态；插件引导中的项目接入请求使用 init。自然语言测试请求按实际目标选择相同流程。

| 命令 | 职责 |
| --- | --- |
| init | 测试策略、缺口建设、默认 hooks 与 CI/CD 接入 |
| plan | 各模块/风险的具体测试动作、阶段、触发点与退出条件 |
| check [阶段] | 执行已有阶段，默认 task-finish |
| fix [阶段] | 定位失败、最小修复、必要回归并复测 |
| doctor | 检查配置；--runtime 额外核对原生 Codex 发现/信任状态 |
| hooks status/on/off | 查看原生状态或切换当前项目 opt-in |
| pin/unpin <命令...> | 管理项目 $pt-check 等快捷入口 |

ci 是 init 的 CI/CD 范围快捷入口；release 是 check release 的快捷入口，沿用相同实现。终端与 hook 调用 Python 脚本，`$playbook-testing` 本身是 skill 调用，不是 shell 程序。

插件根目录为本文件所在目录的上两级。优先使用项目现有语言和测试工具，执行器需 Python 3.10+。平台行为以当前官方文档与实际宿主为准，不从其他代理的接口推断 Codex 支持能力。

## 按需加载

| 当前任务 | 参考 |
| --- | --- |
| init，包括空目录/未完成接入 | [初始化](references/init.md) |
| 选择模块与阶段的测试动作 | [测试动作决策](references/test-actions.md) |
| Codex hooks 发现、信任与触发诊断 | [代理 hooks](references/agent-hooks.md) |
| Git 快照与现有 hook 链 | [Git hooks](references/git-hooks.md) |
| PR、部署、发布、生产 | [CI/CD](references/ci-cd.md) |
| 报告、快照与放行依据 | [证据](references/evidence.md) |

## 执行规则

- 先读适用 AGENTS.md、需求、架构、完成标准与现有测试。将实际模块/边界映射到可观察用例、测试层次和阶段；使用 [测试动作决策](references/test-actions.md)，不统一套用固定覆盖率或固定测试比例。
- init 创建/更新 TESTING.md 或项目已有同类计划，记录动作/check ID、阶段/触发点、已落地/待接入/不适用与理由。补建当前范围内必需测试；部署环境缺失保留待接入，不填假命令。
- edit 给快速反馈并允许 TDD 暂时 Red；本地完成、提交、推送、合并及发布分别核验各自候选与退出条件。长测放到正式 CI/环境作业，不能悄悄删除必需检查。
- 测试必须实际执行并产生本轮报告；缺报告、零用例、全跳过、失败、超时或验证中输入变化均不通过。失败后保存首次证据、定位修复、重跑相关项；不删断言或反复重试取绿。
- Codex 项目开关、原生发现、用户信任和实际事件是四个不同状态。启用后必须查询 hooks status；待信任/未发现/未知时明确报告，不能把 doctor 静态成功或手工调用处理器当成自动触发已验证。
- 保留已有 hooks/流水线和用户配置，按实际授权推进。初始化不代替真实部署、人工签署或用户的 hook 信任审阅。交付只陈述实际完成与剩余条件。
