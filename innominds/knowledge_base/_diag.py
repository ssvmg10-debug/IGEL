import paramiko
HOST="192.168.204.65"; SSH_USER="root"; SSH_PASS="FRIDEbAsec"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=SSH_USER, password=SSH_PASS, timeout=15, allow_agent=False, look_for_keys=False)

def run(cmd):
    print(f"\n$ {cmd}")
    _, out, err = c.exec_command(cmd)
    o = out.read().decode(errors="replace"); e = err.read().decode(errors="replace")
    rc = out.channel.recv_exit_status()
    if o.strip(): print(o.rstrip())
    if e.strip(): print("[stderr]", e.rstrip())
    print(f"[exit {rc}]")

run("ls /etc/apt/sources.list.d/")
run("cat /etc/apt/sources.list.d/pgdg.list 2>/dev/null || echo NO_PGDG_LIST")
run("grep -r postgres /etc/apt/sources.list /etc/apt/sources.list.d/ 2>/dev/null | head")
run("apt-get update 2>&1 | tail -20")
run("apt-cache policy postgresql-17-pgvector")
c.close()
