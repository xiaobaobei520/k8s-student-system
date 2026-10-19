import sys, paramiko, time

PASS = "K8s@2026"
USER = "root"

def connect(host, retries=40, delay=3):
    last = None
    for i in range(retries):
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(host, port=22, username=USER, password=PASS,
                      timeout=6, allow_agent=False, look_for_keys=False)
            return c
        except Exception as e:
            last = e
            time.sleep(delay)
    raise last

def run(client, cmd, timeout=600):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode('utf-8', 'replace')
    err = stderr.read().decode('utf-8', 'replace')
    rc = stdout.channel.recv_exit_status()
    return rc, out, err

if __name__ == '__main__':
    host = sys.argv[1]
    cmd = sys.argv[2] if len(sys.argv) > 2 else "hostname"
    c = connect(host)
    rc, out, err = run(c, cmd)
    print("rc=%d" % rc)
    if out.strip():
        print(out)
    if err.strip():
        print("[stderr]", err)
    c.close()
