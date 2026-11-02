# 配置与运行

## JSON 策略

执行器在 Git 仓库根读取 `.testing-policy.json`；它与技能中的概念性 YAML 模板不是同一个运行格式。setup 初始配置为空，任何空阶段都会拒绝执行，避免假绿。

Python unittest 项目示例（文件已由 setup 复制到 `.testing-tools/`）：

```json
{
  "version": 1,
  "agent_hooks": true,
  "checks": {
    "unit": {
      "kind": "test",
      "argv": ["{python}", "{repo}/.testing-tools/unittest_junit.py", "--start", "tests", "--report", "{report}"],
      "timeout": 60,
      "min_executed": 1
    }
  },
  "stages": {
    "edit": ["unit"],
    "task-finish": ["unit"],
    "commit": ["unit"],
    "push": ["unit"],
    "pr": ["unit"]
  }
}
```

pytest 的测试命令可用 `["{python}", "-m", "pytest", "--junitxml={report}"]`。其他框架采用其 JUnit reporter。使用现有项目框架，不要求切换到 Python 测试。

字段：

- `version`：必须为整数 1。
- `checks`：名称到检查定义的映射；名称使用字母、数字、下划线或短横线。
- `kind: test`：argv 必须含 `{report}`；进程成功且新报告中实际执行数量达到 `min_executed`、没有失败才能通过。
- `kind: command`：适用于构建、静态分析、依赖准备等非测试命令，依据进程退出码判断。不得把测试标为 command 来绕过用例计数。
- `argv`：非空参数数组；不经 shell 拼接。需要管道时放进经评审的项目脚本。
- `timeout`：每项秒数，默认 60，最大 3600。代理阶段所有检查的总耗时必须低于 hooks.json 的事件超时；长测放到 CI/发布。
- `min_executed`：测试的最小实际执行数，默认 1；它不代表覆盖充分。
- `stages`：阶段到有序检查名数组。数组内全部是必需项；首个失败即停止。只配置适用阶段；缺阶段不等于通过。
- `agent_hooks`：只有 true 才会让插件主动执行该仓库策略。目标仓库及策略命令应先被审阅。

支持参数占位符 `{python}`（本次解释器）、`{repo}`（当前被测快照根）、`{plugin}`（运行脚本所属分发根，vendored 后为目标仓库根）、`{report}`（本轮唯一的 JUnit 路径）。其他参数原样传递。执行目录固定为被测仓库根；多包项目在命令参数或项目脚本中指定包。

依赖安装作为普通 command 检查放在需要它的阶段前面，使用锁文件。提交/推送快照是干净的文件导出，不含原工作区 node_modules、虚拟环境和 Git 历史；检查可使用系统已安装工具/解释器及其包。新依赖需要在候选快照中可重复准备。

## 正式阶段与证据

```sh
python3 .testing-tools/quality.py run --stage pr
python3 .testing-tools/quality.py verify --stage pr
```

verify 核对阶段、运行器/Python、代码与策略指纹、必需检查库存、状态和原始 JUnit。它用于相同工作区的 PR/任务证据复核；Git index/ref 检查由原生 Git hook 同步运行，不能用工作区 verify 替代。复制或修改 JSON 不是可信远端验证；CI 的身份与策略由服务端保障。

指纹包含 Git 跟踪内容及未忽略的未跟踪文件，并额外包含策略文件。`.testing-results` 被排除，其他 Git 忽略内容不会自动计入；依赖须锁定，环境与外部数据变化应重跑测试。运行器不复用历史成功缓存。

报告和日志可能包含业务数据，按项目访问策略保管；不要把凭据写入 argv 或策略，应使用现有安全环境变量机制。结果目录默认不提交，也不进入分发包。

## Git hook 链

默认安装命令：

```sh
python3 .testing-tools/install_git_hooks.py --events pre-commit pre-push
```

存在管理器或已有 hook 时，在原链路加入下列命令并保留其退出码和 pre-push stdin：

```sh
python3 .testing-tools/quality.py git-hook pre-commit
python3 .testing-tools/quality.py git-hook pre-push
```

Windows 的安装器把当前解释器绝对路径写入 sh shim；更换解释器后重新运行安装器。移动或升级 vendored 运行器时需评审并重新安装对应包装脚本。安装器不修改全局 `core.hooksPath`，也不会覆盖无关 hook。

## 部署、发布与生产

这些阶段必须以命名为 `smoke` 的检查开头，并提供 `TESTING_ENVIRONMENT` 和 `TESTING_ARTIFACT`。命令要核实实际部署的版本与配置；仅填一个字符串不能证明线上运行的就是该版本。

之后按风险配置集成、E2E、性能、恢复等检查。退出码、JUnit 和代码快照规则相同，smoke 失败不执行后续检查。`templates/ci/release-gate.yml` 验证已有候选，不执行部署、流量切换或自动签署。复制模板时按项目调整依赖、时长、环境审批和产物来源。

PR 模板的最终 `gate` 无论前置作业是否被跳过都会执行，只有前置检查作业成功才通过。还需在仓库规则中将它设置为必需检查；本插件不擅自更改仓库保护策略。
