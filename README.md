# k8s-student-system

在本地 VMware 三节点 Kubernetes 集群上从零搭建并部署的学生管理系统。

整个项目包含两部分：**集群怎么搭**，以及**应用怎么部署**。

---

## 项目概览

```
┌─────────────────────────────────────────────────────────┐
│  VMware Workstation · 3 台 Rocky Linux 9.6 虚拟机        │
│                                                          │
│   k8s-master (.10)   k8s-node1 (.11)   k8s-node2 (.12)   │
│   control-plane      worker            worker            │
│   v1.31.14 / containerd 2.4.2 / Flannel                  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
                    学生管理系统
        frontend(nginx) → backend(FastAPI) → MySQL / Redis
```

应用访问地址：`http://<任一节点IP>:30080`

> 界面包含统计卡片、搜索栏、学生表格和增删改弹窗，右上角会实时显示数据来自 MySQL 还是 Redis。

---

## 目录结构

```
.
├── app/                      学生管理系统
│   ├── backend/              FastAPI 后端（CRUD + Redis 缓存）
│   ├── frontend/             nginx + 单页应用
│   ├── k8s/                  Kubernetes 清单
│   ├── build.py              构建镜像
│   ├── distribute.py         分发镜像到各节点
│   └── README.md             应用部署详细说明
│
├── ks/                       集群搭建自动化脚本
│   ├── ks.cfg                Kickstart 无人值守应答文件
│   ├── remaster.py           往 ISO 注入应答文件
│   ├── patch_grub.py         改写 UEFI 引导配置（关键一步）
│   ├── mydhcp.py             临时 DHCP 服务（绕过宿主机服务异常）
│   ├── configure.py          主机名与静态 IP 配置
│   ├── install_k8s.py        批量安装 containerd 与 k8s 组件
│   ├── fix_sandbox.py        修正 containerd 沙箱镜像源
│   ├── reinit.py             kubeadm 重置与初始化
│   ├── prepull.py            预拉取 Flannel 镜像
│   ├── join.py               工作节点加入集群
│   ├── remote.py             SSH 远程执行小工具
│   └── k8s集群搭建指南.md     完整搭建记录与踩坑总结
│
└── README.md
```

---

## 集群规格

| 主机名 | 角色 | vCPU | 内存 | 磁盘 | IP |
|---|---|---|---|---|---|
| k8s-master | control-plane | 2 | 4 GB | 40 GB | 192.168.221.10 |
| k8s-node1 | worker | 2 | 3 GB | 40 GB | 192.168.221.11 |
| k8s-node2 | worker | 2 | 3 GB | 40 GB | 192.168.221.12 |

| 组件 | 版本 |
|---|---|
| 操作系统 | Rocky Linux 9.6 |
| Kubernetes | v1.31.14（kubeadm） |
| 容器运行时 | containerd 2.4.2 |
| 网络插件 | Flannel v0.28.10，Pod 网段 `10.244.0.0/16` |

---

## 应用架构

| 组件 | 镜像 | 副本 | 说明 |
|---|---|---|---|
| frontend | `localhost/student-frontend:1.0` | 2 | nginx + 静态页面，`/api/` 反代到后端 |
| backend | `localhost/student-backend:1.0` | 2 | FastAPI，MySQL 读写 + Redis 缓存 |
| mysql | `mysql:8.0` | 1 | hostPath PV 持久化，初始化 SQL 由 ConfigMap 注入 |
| redis | `redis:7-alpine` | 1 | 列表缓存，TTL 20 秒 |

### API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查（MySQL / Redis 状态） |
| GET | `/api/stats` | 学生总数与班级分布 |
| GET | `/api/students?keyword=` | 列表 / 搜索 |
| POST | `/api/students` | 新增 |
| PUT | `/api/students/{id}` | 更新 |
| DELETE | `/api/students/{id}` | 删除 |

列表接口在无关键词时读 Redis 缓存，写操作主动失效。响应里的 `source` 字段标明数据来自
`mysql` 还是 `redis`，前端右上角的状态点会跟着变色 —— 连续刷新两次就能看到缓存生效。

---

## 快速开始

### 1. 搭建集群

参考 [`ks/k8s集群搭建指南.md`](ks/k8s集群搭建指南.md)，大致流程：

1. 手写 `.vmx` 创建 3 台虚拟机（UEFI + 精简磁盘 + NAT）
2. 用 `remaster.py` / `patch_grub.py` 把 `ks.cfg` 注入 ISO，实现无人值守安装
3. `configure.py` 配置主机名与静态 IP
4. `install_k8s.py` 批量安装 containerd 与 kubeadm/kubelet/kubectl
5. `reinit.py` 执行 `kubeadm init`，`join.py` 让两个 worker 加入

### 2. 部署应用

```bash
kubectl apply -f app/k8s/
kubectl get pods -n student-system -w
```

然后浏览器打开 `http://192.168.221.10:30080`。

### 3. 修改代码后重新发布

```bash
python app/upload.py            # 上传代码到 master
python app/build.py             # podman 构建镜像
python app/distribute.py        # 分发到三个节点并导入 containerd
kubectl rollout restart deploy/backend -n student-system
```

详细说明见 [`app/README.md`](app/README.md)。

---

## 值得记录的坑

| 问题 | 原因 | 解决 |
|---|---|---|
| UEFI 下 Kickstart 不生效 | grub 读的是 ISO 根目录的 `/EFI/BOOT/grub.cfg`，不是 `efiboot.img` 里那份 | 替换根目录那份并追加 `inst.ks=` |
| 装完重启又进安装程序 | 光盘仍连接且优先引导 | vmx 里 `sata0:0.startConnected = "FALSE"` |
| 虚拟机拿不到 IP | 宿主机 VMware DHCP 服务未启动 | 自建 DHCP 服务，之后统一改静态 IP |
| API Server 4 分钟起不来 | containerd 沙箱镜像指向 `registry.k8s.io` | 改 `sandbox` 指向阿里云镜像 |
| Flannel 卡在 Init:1/2 | ghcr.io 速度只有 60KB/s | 预拉取 + 换 daocloud 源 |
| 中文双重编码 | 初始化 SQL 客户端字符集是 latin1 | `init.sql` 开头加 `SET NAMES utf8mb4;` |
| 前后端镜像串了 | `podman save` 多镜像导出与 `ctr import` 不兼容 | 逐个导出、逐个导入 |

---

## 说明

这是学习用的实验环境，为了简化做了这些取舍：

- SELinux 设为 permissive、关闭 firewalld
- MySQL 单副本 + hostPath 存储，没有做高可用
- 镜像直接导入各节点 containerd，没有搭建私有仓库
- 密码明文写在 Secret 里，仅用于演示

生产环境需要相应加强。
