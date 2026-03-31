# K8s Auto Scaler Dashboard

Kubernetes 集群资源管理仪表盘，支持多集群、kubeconfig 加密存储、资源查询和定时扩缩容。

## 项目简介

本系统面向运维场景，用于集中管理多个 K8s 集群资源，并支持按 Cron 表达式自动执行 Deployment/StatefulSet 扩缩容。kubeconfig 以 Fernet 加密形式存储在 SQLite 数据库中，无需本地文件。前端提供亮/暗色主题、多集群侧边栏与资源列表，操作简便。

## 功能

### 基础功能
- **集群概览 Dashboard**：展示集群基本信息（节点数、命名空间数）、Pod 运行状态统计（总数/运行中/等待/异常/完成）、Deployment/StatefulSet 数量、Ingress/ApisixRoute/Traefik 资源数量、节点 CPU/内存使用量（需集群安装 metrics-server）、Pod CPU/内存请求量/Limit 量/实际使用量汇总、集群事件列表
- **节点概览**：节点汇总信息（节点数、CPU/内存总量及使用量）、节点详情表格（显示每个节点的 IP、CPU/Memory Request/Limit/Usage 及使用百分比）
- **集群管理**：添加/删除/更新 kubeconfig，连接多个 K8s 集群，测试连接
- **资源查询**：查看多种 Kubernetes 资源，支持命名空间筛选
  - **工作负载**：Deployment、StatefulSet、Argo Rollout、Pod
  - **弹性伸缩**：HPA（Horizontal Pod Autoscaler）
  - **网络**：Service、Ingress
  - **Apisix**：ApisixRoute、ApisixTls
  - **Traefik**：IngressRoute、IngressRouteTCP、IngressRouteUDP
  - **配置管理**：ConfigMap、Secret
  - **应用**：Helm Release（自动检测或下载 helm CLI）
- **查看 YAML**：大部分资源支持查看原始 YAML
- **即时扩缩容**：在页面上直接调整 Deployment/StatefulSet 副本数
- **定时扩缩容**：通过 Cron 表达式设置定时任务，自动扩容或缩容
- **主题切换**：支持亮色/暗色模式

### 深度故障排查 (Deep Debugging)
- **Pod 实时日志流**：通过 WebSocket 实时查看 Pod 日志，支持自动滚动、关键词高亮、暂停/继续、下载日志
- **Pod 事件时间轴**：以时间轴形式展示 Pod 事件，Warning 事件红色高亮，直观呈现事件流转

### 资源优化与成本洞察 (FinOps & Optimization)
- **资源健康度分析**：分析 Deployment/StatefulSet 的资源配置合理性，标记浪费资源（Limit 远大于 Usage）和风险资源（Usage 频繁接近 Limit）
- **Top N 资源排行**：在 Dashboard 展示 CPU/内存消耗最高的 Pod 列表

### 交互体验升级 (UX for Ops)
- **批量操作**：在 Pod 列表页支持批量选择和操作，包括批量重启、删除 Pod，批量更新 Labels
- **全局搜索**：在页面顶部提供跨命名空间的资源搜索功能
- **YAML Diff 视图**：对比查看 YAML 差异（简化版）

### 操作审计 (Audit Log)
- **操作记录**：记录所有通过 Dashboard 执行的写操作（扩缩容、删除、更新等），支持按操作类型筛选和分页查看

## 技术栈

- **后端**：Python + FastAPI + Kubernetes Python Client + APScheduler + SQLAlchemy (SQLite)
- **前端**：React 18 + TypeScript + Vite + shadcn/ui + TanStack Query

## 快速开始

### 1. 后端

- 支持 Python 3.11+（含 3.14）
- 生产环境建议设置 `KUBECONFIG_ENCRYPTION_KEY`（可用 `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` 生成）

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8082
```

### 2. 前端

前端位于 `frontend/` 目录，使用 shadcn/ui 组件库：

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 http://localhost:5173，API 代理到 http://localhost:8082。

### 3. 使用

1. 打开 http://localhost:5173
2. 点击「添加集群」粘贴 kubeconfig 内容
3. 在侧边栏选择集群，进入对应资源页面（默认显示集群概览 Dashboard）
4. 在「定时扩缩容」页面配置 Cron 任务

## 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DATABASE_URL` | 数据库连接串 | `sqlite+aiosqlite:///./k8s_dashboard.db` |
| `KUBECONFIG_ENCRYPTION_KEY` | kubeconfig 加密密钥（Fernet 格式） | 由 `SECRET_KEY` 派生 |
| `SECRET_KEY` | 开发环境密钥派生输入 | `dev-secret-change-in-production` |
| `DEBUG` | 调试模式（日志/SQL echo） | `True` |

生产环境务必设置 `KUBECONFIG_ENCRYPTION_KEY`，可用以下命令生成：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Cron 表达式示例

| 表达式 | 含义 |
|--------|------|
| `0 9 * * 1-5` | 周一至周五 9:00 |
| `0 18 * * 1-5` | 周一至周五 18:00 |
| `0 */2 * * *` | 每 2 小时 |
| `30 8 * * *` | 每天 8:30 |

## 目录结构

```
k8s_auto_scaler/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口、生命周期
│   │   ├── config.py            # 配置（环境变量）
│   │   ├── crypto_utils.py      # kubeconfig 加解密
│   │   ├── database.py           # SQLAlchemy 引擎、迁移
│   │   ├── models.py             # 数据库模型
│   │   ├── schemas.py            # Pydantic 请求/响应模型
│   │   ├── scheduler.py           # APScheduler 定时扩缩容
│   │   └── routers/
│   │       ├── clusters.py        # 集群管理 API
│   │       ├── resources.py      # 资源查询 API
│   │       ├── logs.py           # 日志流 WebSocket API
│   │       ├── scaling.py        # 定时扩缩容 API
│   │       ├── analysis.py       # 资源健康度分析 API
│   │       ├── batch_ops.py      # 批量操作 API
│   │       ├── search.py         # 全局搜索 API
│   │       └── audit.py          # 审计日志 API
│   └── services/
│       ├── k8s_service.py        # K8s API 封装
│       ├── log_service.py         # 日志流处理
│       ├── analysis_service.py    # 资源分析服务
│       └── batch_service.py      # 批量操作服务
├── frontend/
│   ├── src/
│   │   ├── api/                  # API 接口封装
│   │   ├── assets/               # 静态资源
│   │   ├── components/           # 通用组件
│   │   │   ├── AppLayout.tsx     # 应用布局
│   │   │   ├── LogViewer.tsx     # 日志查看
│   │   │   ├── YamlViewer.tsx    # YAML 查看
│   │   │   └── ui/               # shadcn/ui 基础组件
│   │   ├── features/             # 功能模块页面
│   │   │   ├── audit/            # 审计日志
│   │   │   ├── clusters/         # 集群管理（含批量操作对话框）
│   │   │   ├── dashboard/        # Dashboard 和节点概览
│   │   │   ├── schedules/        # 定时任务
│   │   │   └── workloads/        # 工作负载详情
│   │   ├── lib/                  # 工具函数
│   │   ├── providers/            # React Provider
│   │   ├── router/               # 路由配置
│   │   ├── stores/               # 状态管理（Zustand）
│   │   ├── index.css             # 全局样式
│   │   └── main.tsx              # React 入口
│   ├── public/                   # 静态资源
│   ├── package.json
│   ├── tailwind.config.js
│   ├── vite.config.ts
│   └── eslint.config.js
└── README.md
```

## 页面说明

### 集群概览（Dashboard）

集群概览页面展示以下信息：

1. **统计卡片**：15 个资源统计卡片
   - 基础信息：集群节点、命名空间
   - Pod 状态：总数、运行中（绿色）、等待中（黄色）、异常（红色）、完成（绿色）
   - 资源数量：Deployment、StatefulSet、Ingress、ApisixRoute、ApisixTls、IngressRoute、IngressRouteTCP、IngressRouteUDP

2. **Pod 资源汇总**：Pod 的 CPU/内存 Request、Limit、Usage（需 metrics-server 支持）

3. **集群事件**：最近 100 条集群事件，显示类型（Normal/Warning）、原因、对象、消息、时间

### 节点概览（NodeMetrics）

节点概览页面展示以下信息：

1. **汇总卡片**：节点数、CPU 总量/使用量、内存总量/使用量

2. **节点详情表格**：每个节点的详细信息
   - 节点名称、IP
   - CPU Request/Limit/Usage（含使用百分比，颜色区分：绿色<70%、黄色70-90%、红色>90%）
   - Memory Request/Limit/Usage（含使用百分比）

## 定时任务实现原理

### 技术选型

采用 **APScheduler** 的 `AsyncIOScheduler`，以 Cron 表达式驱动定时扩缩容。调度器与 FastAPI 共享同一事件循环，与异步后端天然兼容。

### 实现流程

1. **启动加载**：应用启动时（`main.py` lifespan）从数据库读取所有 `is_enabled=True` 的 `ScalingSchedule`，逐一调用 `add_schedule_to_scheduler` 注册到调度器。
2. **任务注册**：每个任务通过 `CronTrigger.from_crontab(cron_expression, timezone)` 生成触发器，以 `schedule_{id}` 为 job id 注册到 APScheduler。
3. **定时执行**：到达触发时间后，调度器调用 `_run_scale_job(schedule_id)`，根据任务配置调用 Kubernetes API 执行扩缩容。
4. **CRUD 联动**：
   - **创建**：若 `is_enabled=True`，立刻注册到调度器。
   - **更新**：先 `remove` 再 `add`，用新配置重新注册。
   - **删除**：从调度器移除对应 job。

### 执行逻辑（`_run_scale_job`）

- 根据 `schedule_id` 查询任务与集群信息。
- 校验：任务存在且 `is_enabled`、集群存在且 `is_active`，否则跳过。
- 使用集群的 kubeconfig 构建 Kubernetes API 客户端。
- 根据 `resource_type`（`Deployment` / `StatefulSet`）调用 `scale_deployment` 或 `scale_statefulset`。
- 成功或失败均写入日志，异常时记录异常堆栈。

### 支持资源类型

当前支持 **Deployment** 和 **StatefulSet**。扩缩容通过 Kubernetes 标准 `apps/v1` API 的 `patch replicas` 实现。

### 时区

任务支持 `timezone` 字段（默认 `Asia/Shanghai`），Cron 触发时间按该时区计算。

---

## 数据库 (SQLite)

默认数据库文件：`backend/k8s_dashboard.db`，首次启动时自动创建。

### 表结构

#### clusters（集群配置）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | 主键 |
| name | VARCHAR(255) | UNIQUE, NOT NULL | 集群唯一标识名 |
| display_name | VARCHAR(255) | NULL | 显示名称（可为空，默认用 name） |
| kubeconfig_encrypted | TEXT | NOT NULL | kubeconfig 内容（Fernet 对称加密存储） |
| is_active | BOOLEAN | DEFAULT 1 | 是否启用 |
| created_at | DATETIME | DEFAULT utcnow | 创建时间 |
| updated_at | DATETIME | DEFAULT utcnow, ON UPDATE utcnow | 更新时间 |

**kubeconfig 加密**：kubeconfig 以 Fernet 对称加密存储于数据库，不再使用本地文件。加密密钥通过环境变量 `KUBECONFIG_ENCRYPTION_KEY` 配置；未设置时从 `SECRET_KEY` 派生（仅限开发环境）。

#### scaling_schedules（定时扩缩容任务）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | 主键 |
| cluster_id | INTEGER | FK(clusters.id), NOT NULL | 所属集群 |
| namespace | VARCHAR(255) | NOT NULL | 目标资源命名空间 |
| resource_type | VARCHAR(50) | NOT NULL | 资源类型（Deployment / StatefulSet） |
| resource_name | VARCHAR(255) | NOT NULL | 目标资源名称 |
| target_replicas | INTEGER | NOT NULL | 目标副本数 |
| cron_expression | VARCHAR(100) | NOT NULL | Cron 表达式（如 `0 9 * * 1-5`） |
| timezone | VARCHAR(50) | DEFAULT 'Asia/Shanghai' | 时区 |
| description | VARCHAR(500) | NULL | 任务描述 |
| is_enabled | BOOLEAN | DEFAULT 1 | 是否启用 |
| created_at | DATETIME | DEFAULT utcnow | 创建时间 |
| updated_at | DATETIME | DEFAULT utcnow, ON UPDATE utcnow | 更新时间 |

#### audit_logs（操作审计日志）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | 主键 |
| operator | VARCHAR(100) | DEFAULT 'admin' | 操作者 |
| action | VARCHAR(50) | NOT NULL | 操作类型（scale/delete/create/update/restart） |
| resource_type | VARCHAR(50) | NOT NULL | 资源类型 |
| resource_name | VARCHAR(255) | NOT NULL | 资源名称 |
| namespace | VARCHAR(255) | NULL | 命名空间 |
| cluster_id | INTEGER | FK(clusters.id), NULL | 所属集群 |
| details | TEXT | NULL | 变更详情（JSON 格式） |
| timestamp | DATETIME | DEFAULT utcnow | 操作时间 |

## API 文档

启动后端后访问 http://localhost:8082/docs 查看 Swagger API 文档。

### Metrics API

| 接口 | 说明 |
|------|------|
| `GET /api/resources/{cluster_id}/metrics/overview` | 集群基础统计（节点数、命名空间数、Pod 统计、Deployment/StatefulSet/Ingress 数量） |
| `GET /api/resources/{cluster_id}/metrics/nodes` | 节点资源使用量（需 metrics-server 支持） |
| `GET /api/resources/{cluster_id}/metrics/pods` | Pod 资源请求量/Limit 量/实际使用量汇总及明细（需 metrics-server 支持） |
| `GET /api/resources/{cluster_id}/metrics/top-pods` | Top N 资源消耗 Pod 列表 |

### Resources API

| 接口 | 说明 |
|------|------|
| `GET /api/resources/{cluster_id}/events` | 集群事件列表（最近 100 条） |
| `GET /api/resources/{cluster_id}/namespaces` | 命名空间列表 |
| `GET /api/resources/{cluster_id}/deployments` | Deployment 列表 |
| `GET /api/resources/{cluster_id}/statefulsets` | StatefulSet 列表 |
| `GET /api/resources/{cluster_id}/rollouts` | Argo Rollout 列表 |
| `GET /api/resources/{cluster_id}/pods` | Pod 列表 |
| `GET /api/resources/{cluster_id}/pods/{namespace}/{pod_name}/events` | 特定 Pod 的事件列表 |
| `GET /api/resources/{cluster_id}/services` | Service 列表 |
| `GET /api/resources/{cluster_id}/ingresses` | Ingress 列表 |
| `GET /api/resources/{cluster_id}/apisixroutes` | ApisixRoute 列表 |
| `GET /api/resources/{cluster_id}/apisixtlses` | ApisixTls 列表 |
| `GET /api/resources/{cluster_id}/ingressroutes` | Traefik IngressRoute 列表 |
| `GET /api/resources/{cluster_id}/ingressroutetcps` | Traefik IngressRouteTCP 列表 |
| `GET /api/resources/{cluster_id}/ingressrouteudps` | Traefik IngressRouteUDP 列表 |
| `GET /api/resources/{cluster_id}/helm` | Helm Release 列表 |
| `GET /api/resources/{cluster_id}/configmaps` | ConfigMap 列表 |
| `GET /api/resources/{cluster_id}/secrets` | Secret 列表 |
| `GET /api/resources/{cluster_id}/yaml` | 获取资源 YAML |

### Logs API

| 接口 | 说明 |
|------|------|
| `GET /api/logs/{cluster_id}/pod` | 获取 Pod 历史日志 |
| `GET /api/logs/{cluster_id}/pod/containers` | 获取 Pod 的容器列表 |
| `WebSocket /api/logs/ws/{cluster_id}/pod` | WebSocket 流式获取 Pod 实时日志 |

### Analysis API

| 接口 | 说明 |
|------|------|
| `GET /api/resources/{cluster_id}/analysis/workload-health` | Deployment/StatefulSet 资源健康度分析 |

### Batch API

| 接口 | 说明 |
|------|------|
| `POST /api/batch/restart-pods` | 批量重启 Pod |
| `POST /api/batch/delete-pods` | 批量删除 Pod |
| `POST /api/batch/update-labels` | 批量更新 Pod Labels |

### Search API

| 接口 | 说明 |
|------|------|
| `GET /api/search` | 全局搜索资源（支持 Pod/Deployment/StatefulSet/Service/Ingress/ConfigMap/Secret） |

### Audit API

| 接口 | 说明 |
|------|------|
| `GET /api/audit/logs` | 获取审计日志列表 |

## 安全说明

- kubeconfig 使用 Fernet 对称加密存储，密钥不落库
- 生产环境必须配置 `KUBECONFIG_ENCRYPTION_KEY`，并妥善保管
- API 响应不包含 kubeconfig 明文或路径

## 日志说明

后端使用 Python 标准 `logging` 模块记录日志，日志级别由 `DEBUG` 环境变量控制。

### 日志级别

| 环境变量 | 日志级别 | 说明 |
|---------|---------|------|
| `DEBUG=True` | DEBUG | 包含详细操作信息 |
| `DEBUG=False` | INFO | 包含关键操作和警告 |

### 日志格式

```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

示例：
```
2026-03-26 10:30:00 - app.routers.clusters - INFO - 集群创建成功: id=1, name=prod-cluster
2026-03-26 10:31:00 - app.routers.scaling - INFO - 定时任务创建成功: id=1, cluster=prod-cluster, resource=default/nginx, replicas=3, cron=0 9 * * 1-5
```

### 主要日志事件

| 模块 | 事件 | 级别 |
|------|------|------|
| clusters | 创建/更新/删除集群 | INFO |
| clusters | kubeconfig 更新 | INFO |
| clusters | 连接测试成功/失败 | INFO/WARNING |
| scaling | 创建/更新/删除定时任务 | INFO |
| scaling | 立即扩缩容成功/失败 | INFO/WARNING |
| scheduler | 定时扩缩容执行成功/失败 | INFO/WARNING/ERROR |
| k8s_service | helm CLI 下载成功/失败 | INFO/WARNING/ERROR |
| k8s_service | Deployment/StatefulSet 扩缩容 | INFO/ERROR |
| batch_ops | 批量重启/删除/更新标签 | INFO |
