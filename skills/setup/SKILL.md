---
name: setup
description: 为指定仓库接入 Playbook Testing 插件的实际测试命令、Codex hooks、Git hooks 和可选 CI/CD，保留已有项目配置。
---

# 接入 Playbook Testing

这是 `$playbook-testing init` 和插件 onboarding 共用的接入流程。在用户指定的仓库工作；插件根目录是本文件所在目录的上两级。用户请求 init 时默认接入项目代理检查及 Git pre-commit/pre-push，尊重明确排除项；CI 按需配置。不把安装插件当作授权发布或修改无关仓库。

1. 读取仓库 AGENTS.md、测试与构建脚本、依赖锁、现有 hooks 和 CI，识别平台和团队完成标准。按核心技能建立验收目标与风险映射。
2. 使用插件的 `scripts/setup_repo.py --repo <目标仓库>` 复制独立执行器到 `.testing-tools/`。用户需要 GitHub CI 时增加 `--github-workflow`。脚本保留不同内容的已有文件；遇到冲突先检查并做最小合并，不强制覆盖。
3. 填写 `.testing-policy.json`，参考插件 [执行说明](../../docs/configuration.md)。命令用 argv 数组。测试命令必须把 JUnit XML 写入 `{report}`；不要把测试伪装成 command。已有 pytest、Vitest 等优先使用其 JUnit reporter；Python unittest 可调用复制的 `unittest_junit.py`。
4. 只为适用阶段配置检查。快速单元/集成用于 edit/task-finish；commit/push 验证真实快照；pr 执行必需回归。环境级阶段首项命名为 smoke，并提供实际环境、产物和测试命令。空阶段不能通过，不填假命令或默认覆盖率数字。
5. 执行适用阶段并检查报告、用例数及被测版本。启用代理检查时使用 `scripts/testing.py hooks on --repo <目标仓库>`，先验证非空阶段与总超时预算。提示用户通过 Codex `/hooks` 审阅并信任定义，不能替用户绕过信任。
6. init 默认或用户另行要求 Git hooks 时运行目标仓库中的 `.testing-tools/install_git_hooks.py --repo <目标仓库>`；只接入单一事件时传 `--events`。存在自定义 hook 管理器时在其链路接入同一个 `quality.py git-hook` 命令，不覆盖现有链。
7. CI 需要项目锁定依赖的准备步骤。核对必需 gate、merge_group 和远端分支规则；CD 需要既有部署步骤、不可变产物和环境审批，模板本身不执行部署或自动批准。
8. 用隔离变更验证通过和失败路径、旧证据失效及适用触发事件。运行 `scripts/testing.py doctor --repo <目标仓库>` 汇总状态。交付真实生效范围，明确尚缺的远端配置/环境；不把静态检查写成已在 Codex 或生产验证。可提示使用 `$playbook-testing pin check doctor` 注册项目快捷入口，不默认写入未请求的快捷 skill。
