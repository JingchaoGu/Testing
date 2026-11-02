# 默认阶段接入

init 默认处理全部阶段的接线，不再要求用户额外提出“接 Git/CI/CD”。每项根据项目风险判断适用性：条件具备时完成配置和实际验证；缺少平台、部署、环境、凭据、权限或真实测试时记录待接入条件；不适用时说明理由。用户明确排除的范围保持排除。

| 默认阶段 | 创建或接入 | 生效所需条件 |
| --- | --- | --- |
| edit / task-finish | 插件自带 Codex hooks，配置实际测试并开启项目开关 | 可运行检查与预算，用户在 /hooks 信任定义 |
| commit / push | Git pre-commit / pre-push，保留已有 hook 管理器链 | 暂存/候选快照检查可独立运行；pre-push 保留真实 stdin refs |
| pr | 现有 CI 的 PR/更新/合并队列与最终 gate | 实际依赖、测试、报告及服务端 required checks |
| deployed | 实际候选部署完成后调用检查，先 smoke | 不可变产物、候选 commit、就绪环境与实际探针 |
| release | 晋级前等待 deployed/release 检查通过 | 相同候选/产物，适用深入测试和项目审批 |
| production | 实际生产发布后调用，按项目需要接定时监测 | 生产目标、授权身份/数据清理及告警接收方式 |

## 平台与文件

先识别现有 CI/CD 和远端平台并保留其流程。新项目尚未选择平台时，说明采用 GitHub Actions 默认文件，可按用户约束调整；已有其他平台则按原平台接入同一个执行器，不额外堆叠 GitHub 工作流。

GitHub 项目缺少对应接入时，setup 自动使用 `--github-workflow`，同时准备：

- `.github/workflows/playbook-quality.yml`：PR、main push、merge_group 与最终 gate。
- `.github/workflows/playbook-delivery.yml`：可被实际 CD 调用的 deployed/release/production 门禁，并保留手动验证入口。
- `.testing-tools/delivery_hook.py`：绑定环境、产物与候选版本，执行并复核每一阶段证据；release 先确认 deployed，通过后才做 release。

已有同等流水线时合并检查、依赖和调用关系，避免重复作业；已有同名不同内容的文件需要评审合并，脚本拒绝覆盖。低层 setup 的参数是 skill 的接入实现，用户入口仍是 `$playbook-testing init`。

## 实际 CD 绑定

可复用工作流的 `workflow_call` 需要由实际 CD 作业调用：候选部署 → deployed 检查 → release 检查 → 项目既有晋级/生产部署 → production 检查。使用真实 `needs` 依赖等待结果；验证失败时不执行依赖它的晋级。定时监测复用 production 入口，从项目实际产物登记处读取当前部署版本，不能用默认分支 HEAD 猜线上版本。

例如在现有 GitHub CD 的 jobs 中增加以下调用，并使用该部署作业的实际名称和输出：

```yaml
deployed-tests:
  needs: deploy-candidate
  uses: ./.github/workflows/playbook-delivery.yml
  with:
    stage: deployed
    environment: staging
    artifact: ${{ needs.deploy-candidate.outputs.artifact }}
    revision: ${{ needs.deploy-candidate.outputs.revision }}
```

release 调用传 `stage: release`，其成功是原有晋级作业的依赖；production 调用传 `stage: production`，依赖实际生产部署。参数 artifact 是不可变产物标识，revision 是该产物源码的完整 commit ID；测试命令还要核实实际环境运行的版本。按项目需要显式映射探针凭据，保留环境保护与人工审批。

没有实际 CD 时，完成可评审的工作流与执行器文件，并在 TESTING.md 明确记录“待绑定实际部署/晋级/发布事件”及具体缺项；不添加 echo 假部署、猜测生产地址或用定时运行默认分支来冒充发布后验证。创建文件、绑定事件、真实触发、测试通过、远端规则生效分别记录。

## 交付核对

逐阶段交付适用动作/check ID、触发点、配置文件、已验证证据或缺项。当前里程碑必需的阶段进入 required_stages；未来部署阶段也保留在默认接入清单中，直到条件具备后启用。doctor 的文件存在检查不证明实际调用或服务端保护；无法接入的必需阶段不能被宣称已完成。

平台机制：[GitHub 可复用工作流](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows)、[作业依赖](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-jobs)。
