import paramiko, time, sys

PASS = "K8s@2026"

HOSTS = [
    ("192.168.221.10", "k8s-master", "192.168.221.10"),
    ("192.168.221.11", "k8s-node1",  "192.168.221.11"),
    ("192.168.221.12", "k8s-node2",  "192.168.221.12"),
]

SCRIPT = r"""
set -e
DEV=ens192
CON=$(nmcli -t -f NAME,DEVICE con show --active | grep ':%s$' | head -1 | cut -d: -f1)
echo "active connection: $CON"
hostnamectl set-hostname %s
nmcli con mod "$CON" ipv4.method manual ipv4.addresses %s/24 ipv4.gateway 192.168.221.2 ipv4.dns "192.168.221.2 223.5.5.5"
nmcli con up "$CON" >/dev/null 2>&1 || true
sleep 2
echo "hostname: $(hostname)"
ip -4 addr show $DEV | grep inet
nmcli -g ipv4.method con show "$CON"
"""

for ip, name, addr in HOSTS:
    print("=" * 50)
    print("configuring %s (%s)" % (name, ip))
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(ip, 22, "root", PASS, timeout=10, allow_agent=False, look_for_keys=False)
    cmd = SCRIPT % ("ens192", name, addr)
    stdin, stdout, stderr = c.exec_command(cmd, timeout=120)
    out = stdout.read().decode('utf-8', 'replace')
    err = stderr.read().decode('utf-8', 'replace')
    rc = stdout.channel.recv_exit_status()
    print(out.strip())
    if err.strip():
        print("[stderr]", err.strip())
    print("rc=", rc)
    c.close()
    time.sleep(1)
