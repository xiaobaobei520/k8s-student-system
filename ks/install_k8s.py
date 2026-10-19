import paramiko, threading, time, sys

PASS = "K8s@2026"
HOSTS = [("192.168.221.10", "k8s-master"),
         ("192.168.221.11", "k8s-node1"),
         ("192.168.221.12", "k8s-node2")]

INSTALL = r"""
set -e
echo "=== [1/4] 准备 dnf 插件 ==="
dnf install -y dnf-plugins-core >/dev/null 2>&1 || true

echo "=== [2/4] 安装 containerd ==="
dnf config-manager --add-repo https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo >/dev/null
dnf install -y containerd.io 2>&1 | tail -3
mkdir -p /etc/containerd
containerd config default > /etc/containerd/config.toml
sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
grep -c "SystemdCgroup = true" /etc/containerd/config.toml
systemctl enable --now containerd
systemctl is-active containerd

echo "=== [3/4] 配置 k8s 源 ==="
cat > /etc/yum.repos.d/kubernetes.repo <<'EOF'
[kubernetes]
name=Kubernetes
baseurl=https://mirrors.aliyun.com/kubernetes-new/core/stable/v1.31/rpm/
enabled=1
gpgcheck=0
EOF

echo "=== [4/4] 安装 kubelet kubeadm kubectl ==="
dnf install -y kubelet kubeadm kubectl --disableexcludes=kubernetes 2>&1 | tail -5
systemctl enable kubelet >/dev/null 2>&1
echo "--- versions ---"
kubeadm version -o short
kubectl version --client -o yaml 2>/dev/null | grep gitVersion | head -1
containerd --version
echo "=== DONE ==="
"""

results = {}

def work(ip, name):
    t0 = time.time()
    try:
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(ip, 22, "root", PASS, timeout=15, allow_agent=False, look_for_keys=False)
        stdin, stdout, stderr = c.exec_command(INSTALL, timeout=1800)
        out = stdout.read().decode('utf-8', 'replace')
        err = stderr.read().decode('utf-8', 'replace')
        rc = stdout.channel.recv_exit_status()
        results[name] = (rc, out, err, time.time() - t0)
        c.close()
    except Exception as e:
        results[name] = (-1, "", "EXCEPTION: %s" % e, time.time() - t0)

threads = [threading.Thread(target=work, args=(ip, n)) for ip, n in HOSTS]
for t in threads:
    t.start()
for t in threads:
    t.join()

for ip, n in HOSTS:
    rc, out, err, dur = results.get(n, (-1, "", "no result", 0))
    print("=" * 60)
    print("%s (%s)  rc=%s  %.0fs" % (n, ip, rc, dur))
    print(out.strip()[-1500:])
    if err.strip():
        print("[stderr]", err.strip()[-800:])
