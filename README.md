# K8s Auto Scaler Dashboard

Kubernetes 集群资源管理仪表盘，支持多集群、kubeconfig 加密存储、资源查询和定时扩缩容。

## 项目简介

本系统面向运维场景，用于集中管理多个 K8s 集群资源，并支持按 Cron 表达式自动执行 Deployment/StatefulSet 扩缩容。kubeconfig 以 Fernet 加密形式存储在 SQLite 数据库中，无需本地文件。前端提供亮/暗色主题、多集群侧边栏与资源列表，操作简便。

## 功能

- **集群管理**：添加/删除 kubeconfig，连接多个 K8s 集群，测试连接
- **资源查询**：查看多种 Kubernetes 资源，支持命名空间筛选
  - **工作负载**：Deployment、StatefulSet、Argo Rollout、Pod
  - **网络**：Service、Ingress、ApisixRoute、ApisixTls
  - **配置管理**：ConfigMap、Secret
  - **应用**：Helm Release
- **查看 YAML**：大部分资源支持查看原始 YAML
- **即时扩缩容**：在页面上直接调整 Deployment/StatefulSet 副本数
- **定时扩缩容**：通过 Cron 表达式设置定时任务，自动扩容或缩容
- **主题切换**：支持亮色/暗色模式

## 技术栈

- **后端**：Python + FastAPI + Kubernetes Python Client + APScheduler + SQLAlchemy (SQLite)
- **前端**：Vue 3 + TypeScript + Vite + Pinia

## 快速开始

### 1. 后端

- 支持 Python 3.11+（含 3.14）
- 生产环境建议设置 `KUBECONFIG_ENCRYPTION_KEY`（可用 `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` 生成）

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 http://localhost:5173，API 代理到 http://localhost:8000。

### 3. 使用

1. 打开 http://localhost:5173
2. 点击「添加集群」粘贴 kubeconfig 内容
3. 在侧边栏选择集群，进入对应资源页面
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
│   │   ├── main.py           # FastAPI 入口、生命周期
│   │   ├── config.py        # 配置（环境变量）
│   │   ├── crypto_utils.py  # kubeconfig 加解密
│   │   ├── database.py      # SQLAlchemy 引擎、迁移
│   │   ├── models.py        # 数据库模型
│   │   ├── schemas.py       # Pydantic 请求/响应模型
│   │   ├── scheduler.py     # APScheduler 定时扩缩容
│   │   ├── routers/         # API 路由
│   │   └── services/        # K8s 服务封装
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── views/           # 页面组件
│   │   ├── api/             # 接口封装
│   │   ├── stores/          # Pinia 状态
│   │   ├── router/          # 路由配置
│   │   └── styles/          # 全局样式
│   └── package.json
└── README.md
```

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

## API 文档

启动后端后访问 http://localhost:8000/docs 查看 Swagger API 文档。

## 安全说明

- kubeconfig 使用 Fernet 对称加密存储，密钥不落库
- 生产环境必须配置 `KUBECONFIG_ENCRYPTION_KEY`，并妥善保管
- API 响应不包含 kubeconfig 明文或路径
