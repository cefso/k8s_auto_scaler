{{/*
Expand the name of the chart.
*/}}
{{- define "k8s-auto-scaler.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "k8s-auto-scaler.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "k8s-auto-scaler.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "k8s-auto-scaler.labels" -}}
helm.sh/chart: {{ include "k8s-auto-scaler.chart" . }}
{{ include "k8s-auto-scaler.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- range $key, $value := .Values.commonLabels }}
{{ $key }}: {{ $value | quote }}
{{- end }}
{{- end }}

{{- define "k8s-auto-scaler.selectorLabels" -}}
app.kubernetes.io/name: {{ include "k8s-auto-scaler.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "k8s-auto-scaler.backend.selectorLabels" -}}
{{ include "k8s-auto-scaler.selectorLabels" . }}
app.kubernetes.io/component: backend
{{- end }}

{{- define "k8s-auto-scaler.frontend.selectorLabels" -}}
{{ include "k8s-auto-scaler.selectorLabels" . }}
app.kubernetes.io/component: frontend
{{- end }}

{{- define "k8s-auto-scaler.backend.fullname" -}}
{{- printf "%s-backend" (include "k8s-auto-scaler.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "k8s-auto-scaler.frontend.fullname" -}}
{{- printf "%s-frontend" (include "k8s-auto-scaler.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "k8s-auto-scaler.secretName" -}}
{{- if .Values.secrets.existingSecret }}
{{- .Values.secrets.existingSecret }}
{{- else }}
{{- printf "%s-secrets" (include "k8s-auto-scaler.fullname" .) }}
{{- end }}
{{- end }}

{{/*
Fernet 密钥：32 字节标准 Base64（cryptography.Fernet 可接受）；upgrade 时默认保留已有 Secret
*/}}
{{- define "k8s-auto-scaler.secret.kubeconfigEncryptionKey" -}}
{{- if .Values.secrets.kubeconfigEncryptionKey -}}
{{- .Values.secrets.kubeconfigEncryptionKey -}}
{{- else -}}
{{- $existing := "" -}}
{{- if not .Values.secrets.forceRegenerate -}}
{{- $existing = lookup "v1" "Secret" .Release.Namespace (include "k8s-auto-scaler.secretName" .) -}}
{{- end -}}
{{- if and $existing $existing.data (index $existing.data "KUBECONFIG_ENCRYPTION_KEY") -}}
{{- $kubeKey := index $existing.data "KUBECONFIG_ENCRYPTION_KEY" | b64dec -}}
{{- /* 修复历史双层 Base64：解码一次后若仍像 Base64（约 60 字符），再解码一次 */ -}}
{{- if gt (len $kubeKey) 50 -}}
{{- $kubeKeyInner := $kubeKey | b64dec -}}
{{- if and $kubeKeyInner (ge (len $kubeKeyInner) 40) (le (len $kubeKeyInner) 48) -}}
{{- $kubeKey = $kubeKeyInner -}}
{{- end -}}
{{- end -}}
{{- $kubeKey -}}
{{- else if .Values.secrets.autoGenerate -}}
{{- randBytes 32 | b64enc -}}
{{- else -}}
{{- fail "secrets.kubeconfigEncryptionKey 未设置且 secrets.autoGenerate=false，请提供密钥或开启自动生成" -}}
{{- end -}}
{{- end -}}
{{- end }}

{{- define "k8s-auto-scaler.secret.jwtSecretKey" -}}
{{- if .Values.secrets.jwtSecretKey -}}
{{- .Values.secrets.jwtSecretKey -}}
{{- else -}}
{{- $existing := "" -}}
{{- if not .Values.secrets.forceRegenerate -}}
{{- $existing = lookup "v1" "Secret" .Release.Namespace (include "k8s-auto-scaler.secretName" .) -}}
{{- end -}}
{{- if and $existing $existing.data (index $existing.data "JWT_SECRET_KEY") -}}
{{- index $existing.data "JWT_SECRET_KEY" | b64dec -}}
{{- else if .Values.secrets.autoGenerate -}}
{{- randAlphaNum 64 -}}
{{- else -}}
{{- fail "secrets.jwtSecretKey 未设置且 secrets.autoGenerate=false" -}}
{{- end -}}
{{- end -}}
{{- end }}

{{- define "k8s-auto-scaler.secret.initAdminPassword" -}}
{{- if .Values.secrets.initAdminPassword -}}
{{- .Values.secrets.initAdminPassword -}}
{{- else -}}
{{- $existing := "" -}}
{{- if not .Values.secrets.forceRegenerate -}}
{{- $existing = lookup "v1" "Secret" .Release.Namespace (include "k8s-auto-scaler.secretName" .) -}}
{{- end -}}
{{- if and $existing $existing.data (index $existing.data "INIT_ADMIN_PASSWORD") -}}
{{- index $existing.data "INIT_ADMIN_PASSWORD" | b64dec -}}
{{- else if .Values.secrets.autoGenerate -}}
{{- randAlphaNum 24 -}}
{{- else -}}
{{- fail "secrets.initAdminPassword 未设置且 secrets.autoGenerate=false" -}}
{{- end -}}
{{- end -}}
{{- end }}

{{- define "k8s-auto-scaler.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "k8s-auto-scaler.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{- define "k8s-auto-scaler.corsOrigins" -}}
{{- if .Values.backend.env.CORS_ORIGINS -}}
{{- .Values.backend.env.CORS_ORIGINS -}}
{{- else if .Values.ingress.enabled -}}
{{- $scheme := "http" -}}
{{- if .Values.ingress.tls -}}
{{- $scheme = "https" -}}
{{- end -}}
{{- $origins := list -}}
{{- range .Values.ingress.hosts -}}
{{- $origins = append $origins (printf "%s://%s" $scheme .host) -}}
{{- end -}}
{{- join "," $origins -}}
{{- else -}}
http://localhost:5173
{{- end -}}
{{- end }}
