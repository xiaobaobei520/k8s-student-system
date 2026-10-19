# 学生管理系统 · 部署说明

一个前后端分离的示例应用，部署在本地 k8s 集群（k8s-master / node1 / node2）上。

## 访问地址

```
http://192.168.221.10:30080
```

宿主机直接打开即可（NodePort 会转发到任意一个节点上的 frontend Pod）。

---

## 架构

```
                    浏览器
                      │  http://192.168.221.10:30080
                      ▼
            ┌──────────────────────┐
            │ frontend (nginx ×2)  │  NodePort 30080
            │  静态页面 + 反向代理  │
            └──────────┬───────────┘
                       │  /api/*  →  http://backend:8000
                       ▼
            ┌──────────────────────┐
            │ backend (FastAPI ×2) │  ClusterIP 8000
            │  CRUD + Redis 缓存    │
            └───────┬──────┬───────┘
                    │      │
          ┌─────────▼──┐ ┌─▼──────────┐
          │   mysql    │ │   redis    │
          │ ClusterIP  │ │ ClusterIP  │
          │  3306 + PVC│ │   6379     │
          └────────────┘ └────────────┘
```

| 组件 | 镜像 | 副本 | 说明 |
|---|---|---|---|
| frontend | `localhost/student-frontend:1.0` | 2 | nginx + 静态页面，`/api/` 反代到后端 |
| backend | `localhost/student-backend:1.0` | 2 | FastAPI，连 MySQL 读写、Redis 做列表缓存 |
| mysql | `docker.m.daocloud.io/library/mysql:8.0` | 1 | 数据存 hostPath PV，初始化 SQL 由 ConfigMap 注入 |
| redis | `docker.m.daocloud.io/library/redis:7-alpine` | 1 | 无持久化，只做缓存 |

Pod 分布：backend 和 frontend 各有一个副本落在 node1、一个落在 node2；mysql 通过 nodeSelector 固定在 node2（因为 hostPath PV 有节点亲和性）；redis 在 node1。

---

## 目录结构

```
app/
├── backend/
│   ├── main.py              FastAPI 应用（CRUD + 缓存）
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── index.html           单页应用（原生 JS，无构建步骤）
│   ├── nginx.conf           静态资源 + /api 反向代理
│   └── Dockerfile
├── k8s/
│   ├── 00-namespace.yaml
│   ├── 01-secret.yaml       MySQL 密码
│   ├── 02-mysql.yaml        ConfigMap + PV + PVC + Deployment + Service
│   ├── 03-redis.yaml
│   ├── 04-backend.yaml
│   └── 05-frontend.yaml     NodePort 30080
├── build.py                 构建镜像（在 master 上执行）
├── distribute.py            导出镜像并分发到三个节点
├── upload.py                上传代码到 master
└── rebuild_frontend.py      只重建前端并滚动更新
```

---

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查，返回 MySQL/Redis 状态和 Pod 名 |
| GET | `/api/stats` | 学生总数与班级分布 |
| GET | `/api/students?keyword=` | 列表/搜索，支持姓名、学号、班级 |
| POST | `/api/students` | 新增 |
| PUT | `/api/students/{id}` | 更新 |
| DELETE | `/api/students/{id}` | 删除 |

列表接口在无关键词时会读 Redis 缓存（TTL 20 秒），写操作会主动失效缓存。
响应里的 `source` 字段会标明本次数据来自 `mysql` 还是 `redis`，前端右上角的圆点也会跟着变色 —— 刷新两次页面就能看到缓存生效。

```bash
# 命令行验证
curl http://192.168.221.10:30080/api/students          # 第一次 source=mysql
curl http://192.168.221.10:30080/api/students          # 第二次 source=redis
```

---

## 常用运维命令

```bash
# 查看状态
kubectl get pods -n student-system -o wide
kubectl get svc -n student-system
kubectl get pv,pvc

# 看日志
kubectl logs -n student-system deploy/backend -f
kubectl logs -n student-system deploy/mysql --tail=50

# 进容器
kubectl exec -it -n student-system deploy/mysql -- mysql -uroot -pRoot@2026 studentdb
kubectl exec -it -n student-system deploy/redis -- redis-cli

# 扩容
kubectl scale deploy backend --replicas=3 -n student-system

# 滚动更新（改了代码之后）
# 1. 重新构建镜像  2. 分发到三个节点  3. 触发滚动
kubectl rollout restart deploy/frontend -n student-system
kubectl rollout status deploy/frontend -n student-system

# 回滚
kubectl rollout undo deploy/frontend -n student-system
```

---

## 重新构建镜像

镜像不是从仓库拉的，而是本地构建后**直接导入三个节点的 containerd**，所以 manifest 里写的是
`localhost/student-xxx:1.0` + `imagePullPolicy: IfNotPresent`。

```bash
# 在 Windows 宿主机上执行
python app/upload.py            # 上传代码到 master
python app/build.py             # master 上 podman build
python app/distribute.py        # 导出 tar → 分发到 node1/node2 → 导入 containerd

kubectl rollout restart deploy/backend -n student-system
```

几个注意点：

1. **`podman save` 一次只能导出一个镜像**。同时传多个镜像名时，`ctr import` 会把多个 tag
   挂到同一个镜像 ID 上，导致前后端镜像串掉。必须逐个 save / import。
2. **镜像名要和 containerd 里的一致**。podman 构建出来的 tag 是 `localhost/xxx:1.0`，
   manifest 里就得写 `localhost/xxx:1.0`，否则 kubelet 会去 docker.io 找，然后拉取失败。
3. **三个节点都要导入**。镜像不在仓库里，Pod 调度到哪个节点就要在哪个节点上有镜像，
   否则会一直 `ErrImagePull`。

---

## 踩过的坑

| 问题 | 原因 | 解决 |
|---|---|---|
| 中文全变成 `é’±ä¸ƒ` | 初始化 SQL 执行时客户端字符集是 latin1，UTF-8 字节被当成 latin1 又转存了一次（双重编码） | 在 `init.sql` 开头加 `SET NAMES utf8mb4;` |
| 前后端镜像串了 | `podman save` 多镜像导出 + `ctr import` 的兼容问题 | 逐个导出、逐个导入 |
| MySQL 初始化 SQL 不执行 | 数据目录非空时 `docker-entrypoint-initdb.d` 会被跳过 | 清空 hostPath 目录后重建 PVC |

---

## 数据说明

- MySQL 数据落在 `k8s-node2:/data/mysql`（hostPath PV，回收策略 Retain）
- 删除 PVC 不会删数据，需要手动清理该目录才会重新初始化
- Redis 不持久化，重启后缓存丢失但不影响数据
