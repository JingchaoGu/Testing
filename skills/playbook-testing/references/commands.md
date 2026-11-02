# 命令路由

管理/诊断命令使用当前安装插件的 scripts/testing.py，避免旧项目 vendor 缺少新诊断能力；Git/CI 使用项目 .testing-tools/ 的独立运行器，升级前核对来源并保留定制。Python 使用可用的 3.10+ 解释器（Windows 通常 py -3）。命令是 skill 路由；终端通过真实 Python/路径运行。

## init / ci

init 执行 [初始化](init.md)。ci 复用同一流程，但将范围限制为现有项目 CI/CD 接入或调整，不重新创建应用。默认阶段、项目新建与缺项处理由 init 参考维护，避免另一份流程漂移。

## plan

读取 [测试动作决策](test-actions.md)，交付模块/风险、具体用例与预期、测试层次、阶段、check ID/命令、触发/退出条件及落地状态。新项目没有现成命令也应得到建议。只要求方案时不安装 hooks；要求落盘时使用 [测试计划模板](../assets/test-plan.template.md)。

## check / release

执行 `testing.py check --stage <阶段> --repo <仓库>`，默认 task-finish。没有策略则说明先 init，不静默创建。commit 测真实 index；push 仅由 Git pre-push 的真实 stdin refs 驱动，手动 check push 会拒绝。

环境阶段 deployed/release/production 共用 delivery_hook：从 TESTING_ENVIRONMENT、TESTING_ARTIFACT、TESTING_REVISION 读取真实上下文，要求干净候选；release 先验证 deployed。缺环境/产物时报告缺口，不猜生产地址。release 快捷命令完全复用 check release；不部署、晋级或代替人工签署。

报告实际执行数、失败/阻塞及证据位置，不将缺报告、零用例或全跳过写成通过。

## fix

先读指定阶段最新失败记录和日志，区分产品、测试与环境问题；尽量复现并做最小修复、补必要回归，再重跑该阶段。保存首次失败，重试有界；不降低验收约束、删断言或盲目更新快照。无法确定阶段/范围时展示相关失败让用户选定，不修复全部历史问题。

## hooks

`testing.py hooks status|on|off`：status 默认只读查询项目开关与 Codex 原生登记/信任；on/off 只改该项目 agent_hooks，保留其他配置与 Git 链。on 拒绝空阶段或超过预算的 edit/task-finish，不自动批准 hook 信任。

CLI 可传 --codex 指定当前宿主的可执行文件；检查结果标明路径与版本。status 在项目 opt-in 已开但原生 hooks 未确认 trusted 时返回非零；on/off 的成功仅表示开关设置成功，automatic_checks 仍可能 pending。按 [代理 hooks](agent-hooks.md) 排障。

## doctor

`testing.py doctor` 只检查本地策略、证据、Git 包装脚本和工作流文件；`--runtime [--codex <路径>]` 额外查询 Codex。项目 opt-in 开启但原生状态未确认时，运行时检查失败并说明原因。receipt 的 origin=direct 仅表示手工调用处理器，不能证明 Codex 派发。文件存在不证明 CI/CD 绑定、远端规则或审批生效。

## pin / unpin

`testing.py pin check doctor --repo <仓库>` 注册 .agents/skills/pt-<命令>/SKILL.md，使用 $pt-check 等入口并转发后续参数。未指定命令时列出可选项，不默认注册全部；列表未刷新时开启新会话。

unpin 只移除与生成内容一致的文件；保留用户修改、同名外部 skill、目录内其他文件及链接路径。操作局限于项目目录，不修改全局技能。
