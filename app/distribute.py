import os
import paramiko

PASS = "K8s@2026"
MASTER = "192.168.221.10"
NODES = ["192.168.221.11", "192.168.221.12"]
LOCAL_DIR = r"D:\k8sstudey\app\_img"
IMAGES = [("student-backend", "1.0"), ("student-frontend", "1.0")]

os.makedirs(LOCAL_DIR, exist_ok=True)


def conn(ip):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(ip, 22, "root", PASS, timeout=15, allow_agent=False, look_for_keys=False)
    return c


def run(c, cmd, timeout=900):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', 'replace')
    err = stderr.read().decode('utf-8', 'replace')
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


m = conn(MASTER)
print(">>> 清理 master 上导入错误的镜像条目")
run(m, "ctr -n k8s.io images rm localhost/student-backend:1.0 localhost/student-frontend:1.0 2>/dev/null; true")

for name, tag in IMAGES:
    ref = "localhost/%s:%s" % (name, tag)
    tar = "/tmp/%s.tar" % name
    rc, out, err = run(m, "rm -f %s && podman save -o %s %s >/dev/null 2>&1 && ls -l %s | awk '{print $5}'" % (tar, tar, ref, tar), 600)
    print("save %s -> %s bytes (rc=%d)" % (ref, out.strip(), rc))
    rc, out, err = run(m, "ctr -n k8s.io images import %s 2>&1 | tail -1" % tar, 600)
    print("  import:", out.strip()[:120])

rc, out, err = run(m, "crictl images 2>/dev/null | grep student", 60)
print(">>> master containerd:\n" + out.strip())

print(">>> 下载到本机")
sftp = m.open_sftp()
for name, _ in IMAGES:
    local = os.path.join(LOCAL_DIR, name + ".tar")
    sftp.get("/tmp/%s.tar" % name, local)
    print("  %s -> %.1f MB" % (name, os.path.getsize(local) / 1024**2))
sftp.close()

for ip in NODES:
    print(">>> 分发到 %s" % ip)
    n = conn(ip)
    run(n, "ctr -n k8s.io images rm localhost/student-backend:1.0 localhost/student-frontend:1.0 2>/dev/null; true")
    nsftp = n.open_sftp()
    for name, _ in IMAGES:
        local = os.path.join(LOCAL_DIR, name + ".tar")
        nsftp.put(local, "/tmp/%s.tar" % name)
    nsftp.close()
    for name, _ in IMAGES:
        rc, out, err = run(n, "ctr -n k8s.io images import /tmp/%s.tar 2>&1 | tail -1" % name, 600)
        print("  import %s: %s" % (name, out.strip()[:100]))
    rc, out, err = run(n, "crictl images 2>/dev/null | grep student; rm -f /tmp/student-*.tar", 60)
    print(out.strip())
    n.close()

print(">>> 清理 master 临时文件")
run(m, "rm -f /tmp/student-*.tar; echo done")
m.close()
print("完成")
