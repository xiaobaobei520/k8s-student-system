import paramiko, threading

PASS = "K8s@2026"
JOIN = ("kubeadm join 192.168.221.10:6443 "
        "--token v790z5.i6ariszbecw10qms "
        "--discovery-token-ca-cert-hash sha256:fa929a43c7f0d845c2693b62fb2a3b5608ca855db8b9c125d565d42fedf069ac "
        "2>&1 | tail -12")

NODES = [("192.168.221.11", "k8s-node1"), ("192.168.221.12", "k8s-node2")]

def work(ip, name):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(ip, 22, "root", PASS, timeout=15, allow_agent=False, look_for_keys=False)
    stdin, stdout, stderr = c.exec_command(JOIN, timeout=900)
    out = stdout.read().decode('utf-8', 'replace')
    err = stderr.read().decode('utf-8', 'replace')
    print("=== %s ===" % name)
    print(out.strip())
    if err.strip():
        print("[err]", err.strip()[:400])
    c.close()

ts = [threading.Thread(target=work, args=(ip, n)) for ip, n in NODES]
for t in ts: t.start()
for t in ts: t.join()
