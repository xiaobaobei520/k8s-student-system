# k8s 学习集群 · 环境说明

> 搭建完成时间：2026-10-17
> 状态：**3 节点集群已运行**，可直接开始学习

---

## 一、集群现状

```
NAME         STATUS   ROLES           VERSION    INTERNAL-IP      CONTAINER-RUNTIME
k8s-master   Ready    control-plane   v1.31.14   192.168.221.10   containerd://2.4.2
k8s-node1    Ready    <none>          v1.31.14   192.168.221.11   containerd://2.4.2
k8s-node2    Ready    <none>          v1.31.14   192.168.221.12   containerd://2.4.2
```

| 项目 | 配置 |
|---|---|
| 操作系统 | Rocky Linux 9.6 (Blue Onyx)，内核 5.14 |
| Kubernetes | v1.31.14（kubeadm 部署） |
| 容器运行时 | containerd 2.4.2（SystemdCgroup） |
| 网络插件 | Flannel v0.28.10，Pod 网段 `10.244.0.0/16` |
| 网卡 | `ens192`，静态 IP，网关 `192.168.221.2` |
| 账号 | `root` / `K8s@2026`（三台一致） |
| 已部署示例 | `web` Deployment（3 副本 nginx）+ NodePort Service |

**登录方式**：宿主机直接 `ssh root@192.168.221.10`，密码 `K8s@2026`。

---

## 二、虚拟机规格

| 主机名 | 角色 | vCPU | 内存 | 磁盘 | IP |
|---|---|---|---|---|---|
| k8s-master | 控制面 | 2 | 4 GB | 40 GB | 192.168.221.10 |
| k8s-node1 | 工作节点 | 2 | 3 GB | 40 GB | 192.168.221.11 |
| k8s-node2 | 工作节点 | 2 | 3 GB | 40 GB | 192.168.221.12 |

- 虚拟机目录：`D:\k8sstudey\vms\<主机名>\`
- 系统盘：精简置备，实际占用约 2 GB/台
- 引导方式：UEFI（Secure Boot 关闭）
- 网络：VMware NAT，`192.168.221.0/24`

---

## 三、常用操作

### 开机 / 关机（宿主机）

```bash
VMRUN="D:/vmware/vmrun.exe"

# 查看运行状态
"$VMRUN" -T ws list

# 开机（nogui 不弹窗口；写 gui 则同时打开控制台）
"$VMRUN" -T ws start "D:/k8sstudey/vms/k8s-master/k8s-master.vmx" nogui

# 关机（soft = 优雅关机）
"$VMRUN" -T ws stop "D:/k8sstudey/vms/k8s-master/k8s-master.vmx" soft
```

### 集群操作（在 master 上）

```bash
kubectl get nodes -o wide
kubectl get pods -A
kubectl get svc
```

### 加节点（token 24 小时过期，过期后重新生成）

```bash
# master 上重新生成
kubeadm token create --print-join-command
```

---

## 四、关键配置说明

### 1. 为什么关掉 swap
kubelet 硬性要求，`free -h` 应显示 Swap 全 0。分区时已用 `--noswap` 跳过。

### 2. SELinux 与防火墙
学习环境设为 permissive + 关闭 firewalld，避免 CNI 与端口问题。
生产环境应改为 enforcing + 放行 k8s 所需端口。

### 3. containerd 的两个关键点（containerd 2.x 配置结构变了）

```toml
# /etc/containerd/config.toml

# ① cgroup 驱动必须是 systemd，否则 kubeadm init 直接失败
[plugins.'io.containerd.cri.v1.runtime'.containerd.runtimes.runc.options]
  SystemdCgroup = true

# ② 沙箱镜像地址（2.x 里键名是 sandbox，不是旧版的 sandbox_image）
[plugins.'io.containerd.cri.v1.images'.pinned_images]
  sandbox = 'registry.aliyuncs.com/google_containers/pause:3.10'
```

> 如果 sandbox 还指向 `registry.k8s.io`，kubelet 会一直卡在
> `failed to pull image "registry.k8s.io/pause:3.10.2"`，API Server 永远起不来。

### 4. 国内网络绕行方案

| 用途 | 使用的源 |
|---|---|
| k8s 组件 RPM | `https://mirrors.aliyun.com/kubernetes-new/core/stable/v1.31/rpm/` |
| containerd | `https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo` |
| k8s 系统镜像 | `registry.aliyuncs.com/google_containers` |
| 业务镜像 / Flannel | `docker.m.daocloud.io`（docker.io 不通，ghcr.io 只有 60KB/s） |

---

## 五、搭建过程中踩的坑（对理解原理有帮助）

| 问题 | 原因 | 解决 |
|---|---|---|
| 装完重启又进安装程序 | CD 仍连接且优先引导 | vmx 里 `sata0:0.startConnected = "FALSE"` |
| UEFI 下 kickstart 不生效 | grub 实际读的是 ISO 根目录的 `/EFI/BOOT/grub.cfg`，不是 `efiboot.img` 里那份 | 直接替换 ISO 根目录的配置，加上 `inst.ks=` |
| BIOS 引导卡死 | pycdlib 重排 ISO 后 `isolinux.bin` 内的引导信息表 LBA 没更新 | 改走 UEFI 路线 |
| 虚拟机一直拿不到 IP | **宿主机 VMware DHCP 服务处于停止状态** | 见下方说明 |
| `kubeadm init` 报 conntrack 不存在 | minimal 安装没带 | `dnf install -y conntrack-tools socat iproute-tc` |
| API Server 4 分钟起不来 | containerd 沙箱镜像指向 registry.k8s.io 拉不动 | 改 `sandbox` 指向阿里云 |
| Flannel 卡在 Init:1/2 | ghcr.io 只有 60KB/s，30MB 镜像要 8 分钟 | 预拉取 + 换 daocloud 源 |

### ⚠️ 关于 VMware DHCP 服务

你机器上 `VMnetDHCP`（VMware DHCP Service）处于 **Stopped** 状态，虚拟机拿不到自动 IP。
本次是用自建 DHCP 临时解决的，之后已全部改成**静态 IP**，不影响使用。

以后如果要新建虚拟机并用自动获取 IP，需要以管理员身份启动该服务：

```powershell
# 管理员 PowerShell
Start-Service VMnetDHCP
Set-Service VMnetDHCP -StartupType Automatic
```

### 💡 性能提示

系统开了 VBS（内存完整性），VMware 只能跑在兼容模式，三台同时跑会略慢。
如需提速：`Windows 安全中心 → 设备安全性 → 内核隔离 → 关闭内存完整性`，重启生效。

---

## 六、建议的学习路径

1. **Pod 基础** — `kubectl run` / `exec` / 查看日志、进入容器
2. **Deployment 与 Service** — 扩缩容、滚动更新、ClusterIP / NodePort 区别
3. **配置管理** — ConfigMap、Secret 挂载
4. **存储** — emptyDir、hostPath、PV/PVC
5. **调度** — 节点亲和、污点与容忍
6. **探针** — liveness / readiness / startup
7. **排障** — `kubectl describe`、`kubectl logs -p`、`crictl ps -a`

现成的示例可以直接拿来玩：

```bash
kubectl get pods -o wide          # web 的 3 个副本分布在 node1/node2
kubectl scale deploy web --replicas=5
kubectl get svc web               # NodePort 31775
kubectl rollout status deploy/web
```

---

## 七、相关文件

| 路径 | 说明 |
|---|---|
| `D:\k8sstudey\vms\` | 三台虚拟机 |
| `D:\k8sstudey\Rocky-9.6-ks.iso` | 定制安装镜像（已注入 kickstart，可重复使用） |
| `D:\k8sstudey\ks\ks.cfg` | 无人值守应答文件 |
| `D:\k8sstudey\ks\` | 本次搭建用的自动化脚本 |
