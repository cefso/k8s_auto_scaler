# k8s-auto-scaler Helm Chart

将 K8s Auto Scaler Dashboard（backend + frontend）部署到 Kubernetes 集群。

## 前置条件

- Kubernetes 1.24+
- Helm 3.10+
- 集群内可拉取镜像（默认 `ghcr.io/cefso/k8s-scaler-*`）
- 为 backend SQLite 提供 `ReadWriteOnce` 存储类（开启 `backend.persistence` 时）

## 快速安装

默认 `secrets.autoGenerate=true`：首次安装时自动生成 JWT、Fernet kubeconfig 加密密钥与初始 admin 密码，并写入 Kubernetes Secret；`helm upgrade` 会通过集群内 `lookup` 保留已有 Secret，不会轮换密钥。

```bash
helm upgrade --install k8s-scaler ./charts/k8s-auto-scaler \
  --namespace k8s-scaler --create-namespace
```

安装后执行 `helm status` 查看 NOTES（含从 Secret 读取初始密码的命令），默认需 `kubectl port-forward` 访问。

### 手动指定密钥（可选）

```bash
helm upgrade --install k8s-scaler ./charts/k8s-auto-scaler \
  --namespace k8s-scaler --create-namespace \
  --set secrets.autoGenerate=false \
  --set secrets.jwtSecretKey="$(openssl rand -hex 32)" \
  --set secrets.kubeconfigEncryptionKey="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
  --set secrets.initAdminPassword='your-secure-password'
```

## 使用 Ingress

APISIX 示例（`className: apisix` 时自动添加 `enable-websocket` 等注解）：

```bash
helm upgrade --install k8s-scaler ./charts/k8s-auto-scaler \
  --namespace k8s-scaler --create-namespace \
  --set ingress.enabled=true \
  --set ingress.className=apisix \
  --set ingress.hosts[0].host=scaler.example.com \
  --set backend.env.CORS_ORIGINS=https://scaler.example.com
```

nginx Ingress 示例：

```bash
helm upgrade --install k8s-scaler ./charts/k8s-auto-scaler \
  --namespace k8s-scaler --create-namespace \
  --set ingress.enabled=true \
  --set ingress.className=nginx \
  --set ingress.hosts[0].host=scaler.example.com \
  --set backend.env.CORS_ORIGINS=https://scaler.example.com
```

## 使用已有 Secret

```bash
kubectl create secret generic k8s-scaler-secrets \
  --namespace k8s-scaler \
  --from-literal=JWT_SECRET_KEY='...' \
  --from-literal=KUBECONFIG_ENCRYPTION_KEY='...' \
  --from-literal=INIT_ADMIN_PASSWORD='...'

helm upgrade --install k8s-scaler ./charts/k8s-auto-scaler \
  --namespace k8s-scaler \
  --set secrets.create=false \
  --set secrets.existingSecret=k8s-scaler-secrets
```

## 主要配置项

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `backend.replicaCount` | 后端副本数（须保持为 1） | `1` |
| `backend.image.repository` | 后端镜像 | `ghcr.io/cefso/k8s-scaler-backend` |
| `backend.persistence.enabled` | 是否挂载 PVC 持久化 SQLite | `true` |
| `frontend.image.repository` | 前端镜像 | `ghcr.io/cefso/k8s-scaler-frontend` |
| `secrets.autoGenerate` | 未填写 `secrets.*` 时自动生成并写入 Secret | `true` |
| `secrets.*` | 手动覆盖 JWT / kubeconfig 加密 / 初始 admin 密码 | 空（走自动生成） |
| `ingress.enabled` | 是否创建 Ingress | `false` |
| `ingress.websocket.enabled` | 是否按 Ingress 类型自动添加 WebSocket 注解 | `true` |
| `ingress.websocket.provider` | 显式指定 `nginx` / `apisix`；留空则根据 `ingress.className` 推断 | `""` |
| `ingress.websocket.timeoutSeconds` | WebSocket 代理读/写超时（秒） | `3600` |

完整参数见 [values.yaml](./values.yaml)。

## 卸载

```bash
helm uninstall k8s-scaler -n k8s-scaler
# 若需删除 PVC（会丢失 SQLite 数据）：
kubectl delete pvc -n k8s-scaler -l app.kubernetes.io/instance=k8s-scaler
```

## 故障排查

### Pod 日志 WebSocket 返回 404（仅 Helm / Ingress 环境）

常见原因有两类：

1. **前端 nginx 未正确转发 WebSocket 握手**（Helm 用 ConfigMap 覆盖镜像内配置）。旧配置会把 `Connection: upgrade` 写死，在 Ingress 剥掉 `Upgrade` 头后，后端会把请求当成普通 GET，对仅注册的 WebSocket 路由返回 404。请 `helm upgrade` 到包含 `00-upgrade-map.conf` 的 Chart 版本，前端 Pod 会随 `checksum/nginx-config` 自动滚动。
2. **后端镜像过旧**：若 `ghcr.io/cefso/k8s-scaler-backend:latest` 早于 PR #7（`logs` 路由不再挂全局 Bearer 依赖），需重新构建并推送镜像，或本地指定 `backend.image` 为自建 tag。

启用 Ingress 且 `ingress.websocket.enabled=true` 时，Chart 会按 `ingress.className`（或 `ingress.websocket.provider`）自动合并注解：`apisix` → `k8s.apisix.apache.org/enable-websocket`；`nginx` → `proxy-read/send-timeout`。APISIX 默认不转发 WebSocket，未加注解会导致日志 WS 404。

## 注意事项

- **backend 必须单副本**：定时扩缩容使用进程内 APScheduler，多副本会导致任务重复执行。
- **前端 nginx** 通过 ConfigMap 将 `/api`（含 WebSocket）代理到集群内 backend Service，无需单独暴露 backend。
- **自动生成密钥**：请备份 Secret 中的 `KUBECONFIG_ENCRYPTION_KEY`；删除 Secret 或在不保留密钥的情况下重装会导致已入库 kubeconfig 无法解密。
- `helm template` 离线渲染时每次会生成新随机值；以实际 `helm install/upgrade`（能访问集群 API）为准。
- 私有 GHCR 镜像请配置 `imagePullSecrets`。
