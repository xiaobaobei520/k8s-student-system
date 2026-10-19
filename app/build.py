import paramiko, time

PASS = "K8s@2026"
MASTER = "192.168.221.10"

CMD = r"""
set -e
echo "=== install podman ==="
dnf install -y podman >/dev/null 2>&1 || dnf install -y podman 2>&1 | tail -3
podman --version

echo "=== build backend ==="
cd /root/app
podman build -t student-backend:1.0 -f backend/Dockerfile backend 2>&1 | tail -12

echo "=== build frontend ==="
podman build -t student-frontend:1.0 -f frontend/Dockerfile frontend 2>&1 | tail -8

echo "=== images ==="
podman images --format "{{.Repository}}:{{.Tag}} {{.Size}}"
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(MASTER, 22, "root", PASS, timeout=15, allow_agent=False, look_for_keys=False)
t0 = time.time()
stdin, stdout, stderr = c.exec_command(CMD, timeout=1800)
out = stdout.read().decode('utf-8', 'replace')
err = stderr.read().decode('utf-8', 'replace')
rc = stdout.channel.recv_exit_status()
print(out[-4000:])
if err.strip():
    print("[stderr]", err.strip()[-1500:])
print("rc=%d, %.0fs" % (rc, time.time() - t0))
c.close()
