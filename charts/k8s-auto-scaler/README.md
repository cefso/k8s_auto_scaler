# k8s-auto-scaler Helm Chart

将 K8s Auto Scaler Dashboard（backend + frontend）部署到 Kubernetes 集群。

## 前置条件

- Kubernetes 1.24+
- Helm 3.10+
- 集群内可拉取镜像（默认 `ghcr.io/cefso/k8s-scaler-*`）
- 为 backend SQLite 提供 `ReadWriteOnce` 存储类（开启 `backend.persistence` 时）

## 快速安装

```bash
# 生成密钥
JWT_SECRET=$(openssl rand -hex 32)
KUBE_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
ADMIN_PASS='your-secure-password'

helm upgrade --install k8s-scaler ./charts/k8s-auto-scaler \
  --namespace k8s-scaler --create-namespace \
  --set secrets.jwtSecretKey="$JWT_SECRET" \
  --set secrets.kubeconfigEncryptionKey="$KUBE_KEY" \
  --set secrets.initAdminPassword="$ADMIN_PASS"
```

安装后按 `helm status` 输出的 NOTES 访问（默认需 `kubectl port-forward`）。

## 使用 Ingress

```bash
helm upgrade --install k8s-scaler ./charts/k8s-auto-scaler \
  --namespace k8s-scaler --create-namespace \
  --set secrets.jwtSecretKey="$JWT_SECRET" \
  --set secrets.kubeconfigEncryptionKey="$KUBE_KEY" \
  --set secrets.initAdminPassword="$ADMIN_PASS" \
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
| `secrets.*` | JWT / kubeconfig 加密 / 初始 admin 密码 | 安装时必填 |
| `ingress.enabled` | 是否创建 Ingress | `false` |

完整参数见 [values.yaml](./values.yaml)。

## 卸载

```bash
helm uninstall k8s-scaler -n k8s-scaler
# 若需删除 PVC（会丢失 SQLite 数据）：
kubectl delete pvc -n k8s-scaler -l app.kubernetes.io/instance=k8s-scaler
```

## 注意事项

- **backend 必须单副本**：定时扩缩容使用进程内 APScheduler，多副本会导致任务重复执行。
- **前端 nginx** 通过 ConfigMap 将 `/api` 代理到集群内 backend Service，无需单独暴露 backend。
- 私有 GHCR 镜像请配置 `imagePullSecrets`。
