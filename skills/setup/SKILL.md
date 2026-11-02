---
name: setup
description: 依据 Playbook 为新/旧项目各部分及阶段制定并建设测试，默认接入 Codex/Git/PR/部署/发布/生产检查，支持空目录引导并保留已有配置。
---

# 接入 Playbook Testing

这是 `$playbook-testing init` 和插件 onboarding 共用的接入流程。在用户指定的仓库工作；插件根目录是本文件所在目录的上两级。init 默认接入项目代理、Git、PR、部署、发布和生产检查，按 [默认阶段接入](references/default-hooks.md) 逐项完成或报告缺项，尊重用户明确排除的范围。不把接入授权当作执行真实部署、发布或修改无关仓库的授权。

先识别目标状态：已有项目按下列流程接入；空目录、未初始化 Git 的源码目录，或只有空测试骨架时，先按 [新项目初始化](references/new-project.md) 创建或接续项目，再回到测试映射与验证。用户已经提供技术栈和用途时直接继续；缺少关键信息时集中询问一次，不以“空目录/不是 Git 仓库”为由终止引导。

1. 读取需求、架构、AGENTS.md 与完成标准，按 [测试动作决策](../playbook-testing/references/test-actions.md) 给每个实际模块和阶段选择具体测试动作、用例及理由，写入 TESTING.md 或已有同类计划。再盘点已有测试与 hooks，识别需要补建的缺口；不以现有命令数量决定测试范围。
2. 使用插件的 `scripts/setup_repo.py --repo <目标仓库>` 复制独立执行器到 `.testing-tools/`；新项目建立本地 Git 时增加 `--init-git`。GitHub 项目默认增加 `--github-workflow` 准备 PR 及共享交付检查；已有同等 CI/CD 时合并原流程，其他平台沿其原生机制接线。脚本保留不同内容的已有文件；遇到冲突先检查并做最小合并，不强制覆盖。
3. 实现当前范围内必需且缺失的测试、数据/夹具和独立命令，再填写 `.testing-policy.json`，参考插件 [执行说明](../../docs/configuration.md)。required_stages 明确项目核心阶段，各动作 check ID 纳入相应 stages。命令用 argv 数组。测试命令必须把 JUnit XML 写入 `{report}`；不要把测试伪装成 command。已有 pytest、Vitest 等优先使用其 JUnit reporter；Python unittest 可调用复制的 `unittest_junit.py`。
4. 只为适用阶段配置检查。快速单元/集成用于 edit/task-finish；commit/push 验证真实快照；pr 执行必需回归。环境级阶段首项命名为 smoke，并提供实际环境、产物和测试命令。空阶段不能通过，不填假命令或默认覆盖率数字。
5. 执行适用阶段并检查报告、用例数及被测版本。启用代理检查时使用 `scripts/testing.py hooks on --repo <目标仓库>`，先验证非空阶段与总超时预算。提示用户通过 Codex `/hooks` 审阅并信任定义，不能替用户绕过信任。
6. init 默认或用户另行要求 Git hooks 时运行目标仓库中的 `.testing-tools/install_git_hooks.py --repo <目标仓库>`；只接入单一事件时传 `--events`。存在自定义 hook 管理器时在其链路接入同一个 `quality.py git-hook` 命令，不覆盖现有链。
7. 默认接入 CI 的锁定依赖、必需 gate 和 PR/合并队列事件，核对远端规则。按默认接入参考将交付检查绑定到实际 CD 的部署后、晋级前及生产发布后节点，传递同一产物与候选版本；按项目需要接定时探测。缺少实际部署/环境时完成文件并明确待绑定条件，不创建假的部署或发布作业。
8. 逐项核对 TESTING.md 中的动作 → 测试实现 → 阶段 → hook/CI 触发点，用隔离变更验证通过和失败路径、旧证据失效及适用事件。运行 `scripts/testing.py doctor --repo <目标仓库>` 检查核心阶段缺口。交付各阶段实际建议、已运行结果、待接入条件和不适用理由；不把配置文件或 doctor 成功写成真实门禁/业务验收通过。可提示使用 `$playbook-testing pin check doctor` 注册项目快捷入口，不默认写入未请求的快捷 skill。
