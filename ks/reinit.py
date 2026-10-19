import paramiko, time

PASS = "K8s@2026"
MASTER = "192.168.221.10"

def conn(ip):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(ip, 22, "root", PASS, timeout=15, allow_agent=False, look_for_keys=False)
    return c

def run(c, cmd, timeout=1800):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', 'replace')
    err = stderr.read().decode('utf-8', 'replace')
    rc = stdout.channel.recv_exit_status()
    return rc, out, err

c = conn(MASTER)

print("=== reset ===")
rc, out, err = run(c, "kubeadm reset -f 2>&1 | tail -5; rm -rf /root/.kube /etc/cni/net.d /var/lib/etcd 2>/dev/null; systemctl restart containerd kubelet; sleep 3; echo reset-done", 300)
print(out.strip())

print("\n=== kubeadm init ===")
init_cmd = (
    "kubeadm init "
    "--apiserver-advertise-address=192.168.221.10 "
    "--control-plane-endpoint=192.168.221.10 "
    "--image-repository=registry.aliyuncs.com/google_containers "
    "--kubernetes-version=v1.31.14 "
    "--pod-network-cidr=10.244.0.0/16 "
    "--cri-socket=unix:///run/containerd/containerd.sock "
    "2>&1 | tail -25"
)
rc, out, err = run(c, init_cmd, 1800)
print(out.strip())

print("\n=== kubeconfig + nodes ===")
rc, out, err = run(c, "mkdir -p /root/.kube && cp -f /etc/kubernetes/admin.conf /root/.kube/config && sleep 3 && kubectl get nodes -o wide", 180)
print(out.strip())
print(err.strip()[:400])
c.close()
