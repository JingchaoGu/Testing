# Codex hooks：登记、信任和实际派发

本插件采用原生 .codex-plugin/plugin.json 和默认 hooks/hooks.json；JSON 的 Windows 字段为 commandWindows。安装后由 Codex 发现，项目 .testing-policy.json 中 agent_hooks 控制是否执行测试。避免再生成一份项目 .codex/hooks.json 导致重复运行。

| 事件 | 实际职责 |
| --- | --- |
| SessionStart | 读取策略与测试计划提示，建立该会话快照基线 |
| PostToolUse | 覆盖本地工具路径，文件快照改变后执行 edit；无变化不重复测试 |
| Stop | 本次存在改动时执行 task-finish；失败最多请求一次继续修复 |

四个状态分别核对：

1. **项目 opt-in**：hooks on/off 操作的仅是项目开关，不是 Codex 信任。
2. **原生发现**：hooks status 使用当前宿主 CLI 的只读 hooks/list，必须出现本插件三个事件；没有条目时先排查包和宿主，而不是要求信任不存在的 hook。
3. **用户信任**：trusted/managed 才具备自动执行资格；untrusted/modified 需要用户在同一 Codex 中 /hooks 审阅。Impeccable 同样要求这一步，插件没有自动弹出或代替用户批准的接口。
4. **实际派发**：检查 .testing-results/last-hook-event.json 的事件/时间/origin，并核对对应阶段新证据。origin=direct 是手工处理器调用；原生登记或脚本单测通过都不能单独证明宿主已经派发。

原生状态为 unknown 时输出具体原因与 CLI 路径/版本；不可从另一版本 CLI 或另一宿主的结果推断当前会话已启用。诊断只读，禁止写 trusted_hash、改 .hook-trust 或使用 bypass 参数制造“已信任”。

edit 的 TDD Red 可继续；Stop 失败继续次数有界，仍失败如实报告未完成。PLAYBOOK_TESTING_RUNNING 避免递归，快照和运行锁防止重复/并发检查。正式 Git/CI 门禁保持同步等待，代理提醒不替代服务端保障。

验证时分别记录原生加载、信任、事件与测试执行。隔离 fixture 可验证处理器语义；没有真实宿主派发时保持未验证状态。

依据：[官方 Hooks](https://learn.chatgpt.com/docs/hooks)、[Impeccable 安装与信任说明](https://github.com/pbakaus/impeccable#installation)。
