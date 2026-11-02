# 命令工作流

`$playbook-testing <命令>` 是用户向编码代理发出的 skill 请求。`init/plan/fix/ci/release` 需要代理结合项目执行；`testing.py` 只提供确定性操作，不用空脚本模拟推理或测试。

插件根目录为主 SKILL.md 所在目录的上两级。下文 `<python>` 指可用的 Python 3.10+：Windows 通常 `py -3`，Linux/macOS 通常 `python3`；`<plugin>` 是已安装插件的实际路径，`<repo>` 是当前目标 Git 仓库。命令参数作为独立 argv 传递。接入后也可使用项目 `.testing-tools/testing.py`，不依赖插件缓存路径。

## init

执行 [setup](../../setup/SKILL.md) 的完整接入流程。默认在当前项目映射真实的 edit、task-finish、commit、push 检查，验证后启用项目代理检查并安装 Git pre-commit/pre-push；用户明确排除的阶段不接入。CI 只在用户要求时配置。

先发现现有框架和 hook 管理器，再复制运行器并填写策略。无可用测试时明确缺口；只按当前任务验收要求补必要测试，不填假命令、不启用空阶段。默认初始模板的空数组不是已完成的初始化。已有文件相同则复用；有差异先评审合并，保留项目定制，不强制覆盖。已有管理器通过其链路调用同一运行器。

验证真实命令通过后运行 `<python> <plugin>/scripts/testing.py hooks on --repo <repo>`。该操作检查 edit/task-finish 的总超时预算（100/150 秒），为 120/180 秒的事件超时留出余量；长测试移到 Git/CI。通过项目的 install_git_hooks.py 安装适用 Git 包装脚本。说明用户仍需在 Codex `/hooks` 信任当前定义，无法从本地策略推断其信任状态。

最后运行 doctor；交付已配置阶段、实际结果及未完成条件。重复 init 不丢弃现有策略，不重复追加忽略项，不重建已有用例。

## plan

读取 [核心模型](core-model.md)，发现仓库能力并将验收标准映射到风险、用例、测试层次、阶段与退出条件。默认交付方案；用户要求落盘时采用测试计划模板。不自动安装 hooks 或修改门禁。

## check

将用户给定的阶段传给 `<python> <plugin>/scripts/testing.py check --repo <repo> --stage <阶段>`；未指定时用 task-finish。未知阶段列出支持值，不猜测其他含义。没有策略时报告需先 init，不静默建立新配置。

commit 使用真实暂存快照。push 必须由 Git pre-push 的真实 stdin ref 驱动；手动 check push 明确拒绝，不以当前 HEAD 替代待推送对象。部署/发布/生产阶段要求已授权的环境和不可变产物标识；未提供时报告缺口，不猜生产地址、不执行部署。展示退出状态、实际执行用例数、证据位置与阻塞；缺报告、零用例、全跳过不能通过。

## fix

读取指定阶段最新证据与日志，优先复现失败；区分产品缺陷、测试问题和依赖/环境问题，做最小修复并运行同一阶段。保持验收约束、断言和首次失败证据；缺陷应加入必要回归保护。不要无限重试，不用删除测试、降低阈值或盲目更新快照取绿。无阶段且无法从当前任务确定时先展示失败记录，请用户选定修复范围；不擅自修复全部历史失败。

## doctor

执行 `<python> <plugin>/scripts/testing.py doctor --repo <repo>`，只读输出配置、代理阶段就绪条件、Git 包装脚本及证据状态。配置错误返回非零；没有新测试结果时明确测试未运行。发现包装文件不能证明其真实执行；Codex 信任与远端 required checks 均需各自平台核对。检查只读，不以 doctor 自动修复任何配置。

## hooks

执行 `<python> <plugin>/scripts/testing.py hooks <status|on|off> --repo <repo>`；无操作参数时用 status。只变更当前项目策略的 agent_hooks 字段，保留其余配置；on 在空阶段或总超时超预算时拒绝。off 不删除 Git hooks、不影响其他项目，也不改 Codex hook 信任记录。用户要求 Git hook 调整时阅读 [Git hook 参考](git-hooks.md)，保留已有链路。

## ci

读取 [CI/CD 参考](ci-cd.md)，先识别已有平台，接入同一策略、锁定依赖、JUnit 与证据、不可跳过的最终 gate；按平台验证 PR/更新/合并队列触发。GitHub 模板仅在适用时使用。已授权的项目范围内完成文件与可运行验证；服务端 required checks 需要实际核对权限及仓库规则，未设置不宣称已经强制合并门禁。

## release

读取 [CI/CD](ci-cd.md) 与 [证据规则](evidence.md)。确认已有候选、目标环境、实际部署产物及授权范围，运行 release 阶段；首项必须为 smoke，失败停止后续检查。它验证候选，不代替部署、业务签署或人工批准。缺环境时完成可离线验证的配置并报告剩余条件，不伪造线上通过。

## pin / unpin

执行 `<python> <plugin>/scripts/testing.py pin check doctor --repo <repo>`，将所选命令注册为 `.agents/skills/pt-<命令>/SKILL.md`，用户可调用 `$pt-check`、`$pt-doctor` 等。支持菜单中的八个工作流命令；参数继续传给原工作流。无命令时显示可选列表，不默认注册全部。

unpin 使用相同参数，仅移除与生成内容完全一致的快捷 skill 文件，保留用户修改、同名外部 skill 与目录内其他文件。两者均为项目范围，不修改全局技能目录；内容相同的重复 pin/unpin 可安全重跑。发现同名冲突或链接目录时停止并报告，不自动覆盖或跟随到仓库外。项目可提交这些入口以共享；Codex 尚未刷新技能列表时开启新会话。快捷入口仍要求核心插件可用，不内嵌版本缓存路径。
