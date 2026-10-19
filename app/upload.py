import os
import paramiko

PASS = "K8s@2026"
MASTER = "192.168.221.10"
LOCAL = r"D:\k8sstudey\app"
REMOTE = "/root/app"

FILES = [
    ("backend/main.py", "backend/main.py"),
    ("backend/requirements.txt", "backend/requirements.txt"),
    ("backend/Dockerfile", "backend/Dockerfile"),
    ("frontend/index.html", "frontend/index.html"),
    ("frontend/nginx.conf", "frontend/nginx.conf"),
    ("frontend/Dockerfile", "frontend/Dockerfile"),
    ("k8s/00-namespace.yaml", "k8s/00-namespace.yaml"),
    ("k8s/01-secret.yaml", "k8s/01-secret.yaml"),
    ("k8s/02-mysql.yaml", "k8s/02-mysql.yaml"),
    ("k8s/03-redis.yaml", "k8s/03-redis.yaml"),
    ("k8s/04-backend.yaml", "k8s/04-backend.yaml"),
    ("k8s/05-frontend.yaml", "k8s/05-frontend.yaml"),
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(MASTER, 22, "root", PASS, timeout=15, allow_agent=False, look_for_keys=False)

sftp = c.open_sftp()

def mkdirs(path):
    parts = path.strip("/").split("/")
    cur = ""
    for p in parts:
        cur += "/" + p
        try:
            sftp.stat(cur)
        except IOError:
            sftp.mkdir(cur)

for local_rel, remote_rel in FILES:
    remote_path = REMOTE + "/" + remote_rel
    mkdirs(os.path.dirname(remote_path))
    sftp.put(os.path.join(LOCAL, local_rel.replace("/", os.sep)), remote_path)
    print("uploaded", remote_rel)

sftp.close()

stdin, stdout, stderr = c.exec_command("find /root/app -type f | sort", timeout=30)
print(stdout.read().decode())
c.close()
