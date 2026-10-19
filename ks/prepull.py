import paramiko, threading, time

PASS = "K8s@2026"
CMD = ("timeout 400 ctr -n k8s.io images pull --snapshotter overlayfs "
       "docker.m.daocloud.io/flannel/flannel:v0.28.10 2>&1 | tail -2")

NODES = [("192.168.221.11", "k8s-node1"), ("192.168.221.12", "k8s-node2")]

def work(ip, name):
    t0 = time.time()
    try:
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(ip, 22, "root", PASS, timeout=15, allow_agent=False, look_for_keys=False)
        stdin, stdout, stderr = c.exec_command(CMD, timeout=500)
        out = stdout.read().decode('utf-8', 'replace')
        err = stderr.read().decode('utf-8', 'replace')
        print("=== %s (%.0fs) ===" % (name, time.time() - t0))
        print(out.strip()[-400:])
        if err.strip():
            print("[err]", err.strip()[-300:])
        c.close()
    except Exception as e:
        print("=== %s FAILED: %s" % (name, e))

ts = [threading.Thread(target=work, args=(ip, n)) for ip, n in NODES]
for t in ts: t.start()
for t in ts: t.join()
print("pre-pull finished")
