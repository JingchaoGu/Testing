# init：策略、测试与默认接入

在用户指定目录执行。已有项目直接分析；空目录或未完成骨架先按 [新项目](new-project.md) 补齐必要上下文，已给的信息不重复询问。

1. 读取需求、架构、AGENTS.md 和完成标准，按 [测试动作决策](test-actions.md) 给各实际模块/风险提出用例、层次及阶段，写入 TESTING.md 或已有同类计划。盘点已有测试以发现缺口。
2. 补建当前范围内必需测试、夹具和报告。复用合适实现，不把所有项目都压成单元测试；不为不存在的系统制造额外业务或环境。
3. 调用插件 `scripts/setup_repo.py --repo <目录>` 复制运行器；需要新建本地 Git 时加 --init-git。默认接入范围见 [阶段接入](default-hooks.md)：GitHub 项目自动选择 --github-workflow，已有其他平台沿原机制接线。已有同名不同内容的文件先评审合并，保留项目定制。
4. 填写唯一运行配置 .testing-policy.json，详见 [配置说明](../../../docs/configuration.md)。required_stages 表达当前里程碑的核心阶段，每项动作的 check ID 纳入相应 stages；测试产生真实 JUnit，空阶段不放行。
5. 运行适用本地检查，核对实际执行数与证据。使用 `testing.py hooks on` 开启项目 opt-in，确认 edit/task-finish 的预算；安装 Git pre-commit/pre-push 或接入原管理器链。
6. 核对原生 Codex：运行 `testing.py hooks status`。它通过只读 hooks/list 查询登记与信任，输出所用 CLI 路径/版本；优先使用当前宿主的 CLI，PATH 若指向另一版本则传 --codex 指定正确可执行文件。
7. 按状态处理：not-discovered 先查插件/清单/宿主版本，unknown 说明无法核实；review-required 明确请求用户在同一 Codex 的 /hooks 审阅 Playbook Testing。没有受支持的自动弹窗/批准接口，不通过写 trust/state、伪造 hash 或 bypass 参数代替用户操作。未完成信任时接入结果为“本地已配置，代理自动检查待信任”。
8. 默认完成适用 PR、部署、发布与生产接线。缺平台、实际 CD、环境、凭据或权限时，交付可评审文件与明确待绑定条件，保留原业务作业及审批。
9. 用隔离 fixture 验证失败会拒绝放行、旧证据失效及适用事件；保持用户索引/历史。运行 doctor --runtime 检查配置及原生状态；.testing-results/last-hook-event.json 只记录处理器收到的事件，直接脚本调用不算原生派发证据。

交付至少区分：测试实际结果、项目 opt-in、原生登记/信任、收到的事件、Git 与远端触发验证、外部待接入条件。用户审阅后可重新运行 hooks status；真实编辑/结束事件出现后再核对 receipt 和阶段证据。不能仅因生成文件或脚本返回 0 就声称所有 hooks 生效。
