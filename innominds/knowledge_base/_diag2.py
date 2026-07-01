import paramiko
import os
HOST = os.environ["DB_SSH_HOST"]; SSH_USER = os.environ.get("DB_SSH_USER", "root"); SSH_PASS = os.environ["DB_SSH_PASSWORD"]
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=SSH_USER, password=SSH_PASS, timeout=15, allow_agent=False, look_for_keys=False)

def run(cmd, t=120):
    print(f"\n$ {cmd}")
    _, out, err = c.exec_command(cmd, timeout=t)
    o = out.read().decode(errors="replace"); e = err.read().decode(errors="replace")
    rc = out.channel.recv_exit_status()
    if o.strip(): print(o.rstrip())
    if e.strip(): print("[stderr]", e.rstrip())
    print(f"[exit {rc}]")

# Is pg_config / dev headers there?
run("which pg_config && pg_config --pgxs && pg_config --includedir-server")
run("dpkg -l | grep postgresql-server-dev-17 || echo 'dev pkg NOT installed'")
run("which gcc make git || echo 'missing build tools'")

# Try the PGDG URL directly (maybe transient)
run("curl -sI https://apt.postgresql.org/pub/repos/apt/dists/focal-pgdg/Release | head -3")
run("curl -sI http://apt.postgresql.org/pub/repos/apt/dists/focal-pgdg/Release | head -3")

c.close()
