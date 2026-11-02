# 核心测试模型与依据

## 原则与适用范围

Microsoft ISE 的 Playbook 是工程实践指南，包含原则、建议、团队示例和技术配方。此技能将其综合为跨平台流程，不声称是微软官方 hook 包。参考内容核对日期：2026-11-02。

核心闭环：验收标准 → 测试计划 → 可测试实现 → 分阶段执行 → 结果与缺陷 → 退出条件 → 上线反馈 → 回归保护。

| 环节 | 应有的输入 | 需要形成的结果 |
| --- | --- | --- |
| 项目准备 | 架构、交付与非功能目标 | 测试分类、可运行命令、环境、团队完成标准 |
| 故事设计 | 可测量的验收标准 | 用例及预期、范围、风险、退出条件 |
| 开发 | 用例、依赖边界 | 快速反馈，修复与回归保护 |
| PR | 候选变更、基线、测试策略 | 自动化证据与人工评审 |
| 部署 | 已构建产物、环境和配置 | 先确认就绪与冒烟，再深入验证 |
| 发布 | 候选版本及测试结果 | 验收与适用非功能目标达成、晋级决策 |
| 运行 | 生产指标与用户路径 | 持续探测、异常处置、缺陷回流 |

## 测试选择

| 目标 | 首选手段 | 主要限制 |
| --- | --- | --- |
| 纯业务逻辑和边界 | 单元测试 | 隔离外部依赖，快速且可重复 |
| 模块、数据库、外部服务交互 | 集成测试 | 环境、测试数据与资源清理；避免过度 mock |
| 消费者/提供者兼容 | CDC 契约测试 | 消费者生成预期，提供者验证；不取代双方沟通 |
| 完整系统行为 | 系统测试 | 系统及依赖就绪 |
| 跨系统用户旅程 | 少量关键 E2E | 成本较高，需要代表性环境与数据 |
| 操作、视觉、设备与可访问性 | 针对性的 UI/可访问性测试 | API 成功不代表界面可实际操作 |
| 判断是否值得继续验证 | 冒烟计划 | 只覆盖少量关键路径，不替代深入回归 |
| 预期负载下的目标 | 负载与性能测试 | 可比环境、明确指标、现实流量模型 |
| 极限、长期、突发负载 | stress、soak/endurance、spike | 专用预算和作业；不能一次短测包办 |
| 故障时的降级与恢复 | 故障注入、恢复演练 | 健康基线、假设、影响范围和恢复条件 |
| 新旧版本实际请求差异 | 影子测试 | 写入、外部副作用、隐私与流量成本需隔离 |
| 已上线服务持续健康 | 合成监测及真实用户监测 | 探针自身也要监控，二者互补 |
| 安全风险 | 凭据、静态分析、依赖/容器扫描及适用渗透测试 | 选择与风险匹配的检查，工具列表不等于统一要求 |

测试层次、测试目的和执行阶段是不同维度。冒烟、区域回归和全量回归可复用已有用例；不为每个 hook 复制测试实现。

## 计划、实施和结束

用例至少表达：标题、前置状态或数据、操作、可观察的预期。Given–When–Then 是可选表达；检查正向、负向、边界和相关非功能需求，自动化优先覆盖关键与高频路径。

E2E：需求与计划 → 环境、数据与退出条件 → 参与系统准备就绪 → 执行与记录 → 缺陷登记、修复复测 → 报告与退出条件评估。

性能：确定验收指标、负载与矩阵 → 准备环境和监测 → 执行并收集指标 → 关联应用/平台瓶颈 → 每次调整后复测。保存每轮代码、配置、环境和结果，不覆盖失败记录来制造改善。

可测试性属于设计：依赖边界明确，必要参数可配置，具备日志、关联 ID 和性能指标。配置及日志不得泄漏凭据。无需为了测试给所有对象增加抽象或依赖注入框架。

## 不应机械化的内容

- TDD 是推荐了解的方法，非所有任务的前置条件；只在适用时采用 Red–Green–Refactor。
- Checklist 的 `>90% if possible` 指组件覆盖建议；CI 章节还有 `80% coverage` 示例。不存在可据此推导的统一百分比门禁。
- 较旧对比表把 E2E 写为手工，专章又讨论自动化；遵循实际场景和专章，不禁止自动化 E2E。
- 单元测试章节允许足够快的集成测试承担部分行为覆盖；不强制所有逻辑都由某个固定层次负责。
- Definition of Done 的检查项由团队约定；产品签署与人工评审不能由测试进程退出码代替。

## 原文导航

- [项目定位](https://github.com/microsoft/code-with-engineering-playbook)；[Testing 总则与目标映射](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/)
- [测试计划](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/test-planning/)；[项目第一周](https://microsoft.github.io/code-with-engineering-playbook/the-first-week-of-an-ise-project/)
- [单元测试](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/unit-testing/)；[Mocking](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/unit-testing/mocking/)；[TDD](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/unit-testing/tdd-example/)
- [集成测试](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/integration-testing/)；[CDC](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/cdc-testing/)
- [E2E](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/e2e-testing/)；[测试层次对比](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/e2e-testing/testing-comparison/)；[UI](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/ui-testing/)
- [冒烟](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/smoke-testing/)；[性能](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/performance-testing/)；[负载](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/performance-testing/load-testing/)；[迭代记录](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/performance-testing/iterative-perf-test-template/)
- [故障注入](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/fault-injection-testing/)；[影子测试](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/shadow-testing/)；[合成监测](https://microsoft.github.io/code-with-engineering-playbook/automated-testing/synthetic-monitoring-tests/)
- [CI](https://microsoft.github.io/code-with-engineering-playbook/CI-CD/continuous-integration/)；[CD](https://microsoft.github.io/code-with-engineering-playbook/CI-CD/continuous-delivery/)；[DevSecOps](https://microsoft.github.io/code-with-engineering-playbook/CI-CD/dev-sec-ops/)
- [工程检查表](https://microsoft.github.io/code-with-engineering-playbook/engineering-fundamentals-checklist/)；[完成标准](https://microsoft.github.io/code-with-engineering-playbook/agile-development/team-agreements/definition-of-done/)；[评审指南](https://microsoft.github.io/code-with-engineering-playbook/code-reviews/process-guidance/reviewer-guidance/)
