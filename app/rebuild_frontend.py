import os
import paramiko

PASS = "K8s@2026"
MASTER = "192.168.221.10"
NODES = ["192.168.221.11", "192.168.221.12"]
LOCAL = r"D:\k8sstudey\app\frontend\index.html"
TAR_LOCAL = r"D:\k8sstudey\app\_img\student-frontend.tar"


def conn(ip):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(ip, 22, "root", PASS, timeout=15, allow_agent=False, look_for_keys=False)
    return c


def run(c, cmd, timeout=900):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', 'replace')
    err = stderr.read().decode('utf-8', 'replace')
    return stdout.channel.recv_exit_status(), out, err


m = conn(MASTER)
s = m.open_sftp()
s.put(LOCAL, "/root/app/frontend/index.html")
s.close()
print("uploaded index.html")

rc, out, err = run(m, "cd /root/app && podman build -q -t student-frontend:1.0 -f frontend/Dockerfile frontend 2>&1 | tail -2", 900)
print("build rc=%d %s" % (rc, out.strip()[-80:]))

rc, out, err = run(m, "rm -f /tmp/fe.tar && podman save -o /tmp/fe.tar localhost/student-frontend:1.0 >/dev/null 2>&1 && ctr -n k8s.io images rm localhost/student-frontend:1.0 >/dev/null 2>&1; ctr -n k8s.io images import /tmp/fe.tar 2>&1 | tail -1", 600)
print("import master:", out.strip()[:100])

s = m.open_sftp()
s.get("/tmp/fe.tar", TAR_LOCAL)
s.close()
print("downloaded %.1f MB" % (os.path.getsize(TAR_LOCAL) / 1024**2))

for ip in NODES:
    n = conn(ip)
    ns = n.open_sftp()
    ns.put(TAR_LOCAL, "/tmp/fe.tar")
    ns.close()
    run(n, "ctr -n k8s.io images rm localhost/student-frontend:1.0 >/dev/null 2>&1; ctr -n k8s.io images import /tmp/fe.tar >/dev/null 2>&1; rm -f /tmp/fe.tar; echo ok", 600)
    rc, out, err = run(n, "crictl images 2>/dev/null | grep frontend", 60)
    print(ip, "->", out.strip())
    n.close()

run(m, "rm -f /tmp/fe.tar; kubectl -n student-system rollout restart deploy/frontend; kubectl -n student-system rollout status deploy/frontend --timeout=120s", 300)
rc, out, err = run(m, "kubectl get pods -n student-system -l app=frontend", 60)
print(out.strip())
m.close()
