# 3 分钟演示脚本

建议时长：2 分 35 秒至 2 分 50 秒。只录产品、代码仓库和 DataHub 写回结果。

## 0:00-0:18 问题

画面：ChangeGuard 首屏，停在默认变更请求。

旁白：

> 我准备删除 `raw_orders.total_amount`。这个字段后面接着 dbt 模型、管理层看板、机器学习特征和定时任务。手工检查这些依赖、负责人和修复代码，通常要在几个系统之间来回查。

## 0:18-0:42 读取 DataHub

画面：指向资产、字段、Owner、Domain 和 Criticality。

旁白：

> ChangeGuard 先从 DataHub 读取这个资产的 schema、owner、domain 和 criticality。连接真实实例时，它会通过 DataHub MCP 调用 `get_entities`、`list_schema_fields` 和 `get_lineage`，再用 GraphQL 读取结构化血缘。

## 0:42-1:10 运行预检

操作：点击 **Run preflight**。

画面：从源表依次指向 dbt、Looker、feature table、model 和 Airflow。

旁白：

> 这次预检找到六个下游资产。五个是高关键资产，Airflow 任务还没有 owner。规则引擎给出 100 分并阻止发布。分数来自变更类型、关键级别、依赖数量、传播深度和缺失 owner，不由语言模型决定。

## 1:10-1:36 检查依据

画面：展示 Agent Trace 和右侧影响资产列表。

旁白：

> 中间是字段传播路径，右侧列出每个资产的负责人、关键级别和受影响字段。这里可以看到 `total_amount` 先变成 `gross_revenue`，再进入特征表和 churn 模型。Agent Trace 记录了读取、遍历、评分、生成文件和准备写回五个步骤。

## 1:36-2:08 查看生成文件

画面：依次点击四个 artifact tab。

旁白：

> 预检会生成四个文件：兼容 SQL、dbt 测试、GitHub Actions 检查和变更记录。SQL 暂时保留旧字段，CI 会阻止没有审批文件的修改合并。仓库的 `examples/generated` 目录里放了同一场景的静态样例。

## 2:08-2:32 批准和写回

画面：展示 Repair plan，点击 **Approve DataHub writeback**。

旁白：

> Repair plan 先修最深的下游依赖，并单独安排缺失 owner 的处理。审核人批准后，ChangeGuard 把 incident 和证据链接写回 DataHub。Demo 模式只写本地审计记录，不会修改外部实例。

## 2:32-2:46 结束

画面：停在风险结果和血缘图。

旁白：

> 这个版本已经完成从变更申请、影响检查、修复文件生成到人工批准的完整流程。下一步是让它直接创建带修复文件的 pull request。

## 录制检查

- 视频少于 3 分钟。
- 使用 1080p，浏览器缩放 100%。
- 不展示 API Key、账号信息、浏览器历史或个人文件。
- 不使用版权音乐。
- 录制前先跑一次，避免在视频里等待接口。
- 旁白中明确出现 DataHub MCP、人工批准和 DataHub 写回。

