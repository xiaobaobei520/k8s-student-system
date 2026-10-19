import paramiko, threading

PASS = "K8s@2026"
HOSTS = [("192.168.221.10", "k8s-master"),
         ("192.168.221.11", "k8s-node1"),
         ("192.168.221.12", "k8s-node2")]

FIX = r"""
set -e
CFG=/etc/containerd/config.toml
sed -i "s|sandbox = 'registry.k8s.io/pause:3.10.2'|sandbox = 'registry.aliyuncs.com/google_containers/pause:3.10'|" $CFG
grep -n "sandbox = " $CFG
systemctl restart containerd
sleep 3
systemctl is-active containerd
ctr -n k8s.io images pull registry.aliyuncs.com/google_containers/pause:3.10 2>&1 | tail -2 || true
"""

def work(ip, name):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(ip, 22, "root", PASS, timeout=15, allow_agent=False, look_for_keys=False)
    stdin, stdout, stderr = c.exec_command(FIX, timeout=600)
    out = stdout.read().decode('utf-8', 'replace')
    err = stderr.read().decode('utf-8', 'replace')
    print("=== %s ===" % name)
    print(out.strip())
    if err.strip():
        print("[err]", err.strip()[:400])
    c.close()

ts = [threading.Thread(target=work, args=(ip, n)) for ip, n in HOSTS]
for t in ts: t.start()
for t in ts: t.join()
