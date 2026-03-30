# K8s Auto Scaler Dashboard

基于 React + TypeScript + shadcn/ui 的 Kubernetes 集群管理前端。

## 技术栈

| 类别 | 技术 |
|------|------|
| 框架 | React 18.3 + TypeScript |
| 构建 | Vite |
| UI | shadcn/ui (Radix + Tailwind) |
| 路由 | React Router v6 |
| 服务端状态 | TanStack Query v5 |
| 客户端状态 | Zustand |
| HTTP | axios |

## 项目结构

```
src/
├── api/                      # API 层
│   └── index.ts              # axios 实例和 API 方法
├── components/
│   ├── ui/                   # shadcn/ui 组件
│   ├── AppLayout.tsx         # 主布局 (Header + Sidebar + Outlet)
│   ├── LogViewer.tsx         # WebSocket 日志查看
│   └── YamlViewer.tsx        # YAML 查看器
├── features/
│   ├── clusters/             # 集群管理
│   │   ├── ClusterListPage.tsx
│   │   ├── ClusterDetailPage.tsx
│   │   └── components/
│   │       ├── ResourceTable.tsx
│   │       ├── AddClusterModal.tsx
│   │       └── ResourceDialogs.tsx
│   ├── workloads/            # 工作负载详情
│   │   └── WorkloadDetailPage.tsx
│   ├── schedules/            # 定时扩缩容
│   │   └── ScheduleListPage.tsx
│   ├── audit/                # 审计日志
│   │   └── AuditLogPage.tsx
│   └── dashboard/            # 仪表盘
│       ├── DashboardView.tsx
│       └── NodeMetricsView.tsx
├── lib/
│   └── utils.ts              # cn() 工具函数
├── stores/
│   └── themeStore.ts         # 主题状态 (Zustand)
├── router/
│   └── index.tsx             # 路由配置
├── App.tsx                   # 根组件
├── main.tsx                  # 入口文件
└── index.css                 # Tailwind + CSS 变量主题
```

## 功能特性

- **集群管理**: 添加/删除/测试连接/更新 kubeconfig Kubernetes 集群
- **资源浏览**: Deployment、StatefulSet、Rollout、Pod、Service、Ingress 等
- **节点 Top Pods**: 按节点筛选的 CPU/内存消耗 Top 5 Pods 排行
- **扩缩容**: 支持立即扩缩容和定时扩缩容
- **日志查看**: WebSocket 实时日志流
- **事件查看**: Pod 事件查看
- **定时任务**: Cron 表达式配置定时任务
- **审计日志**: 操作审计追踪
- **主题切换**:亮/暗色模式

## 开发

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build
```

## API 代理

开发环境通过 Vite 代理转发 API 请求到后端服务，配置见 `vite.config.ts`。
