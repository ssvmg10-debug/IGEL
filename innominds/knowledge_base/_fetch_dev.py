import paramiko
import os
HOST = os.environ["DB_SSH_HOST"]; SSH_USER = os.environ.get("DB_SSH_USER", "root"); SSH_PASS = os.environ["DB_SSH_PASSWORD"]
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=SSH_USER, password=SSH_PASS, timeout=15, allow_agent=False, look_for_keys=False)

def run(cmd, t=600):
    print(f"\n$ {cmd}")
    chan = c.get_transport().open_session()
    chan.set_combine_stderr(True)
    chan.exec_command(cmd)
    while True:
        if chan.recv_ready():
            print(chan.recv(4096).decode(errors="replace"), end="")
        if chan.exit_status_ready():
            break
    while chan.recv_ready():
        print(chan.recv(4096).decode(errors="replace"), end="")
    rc = chan.recv_exit_status()
    print(f"\n[exit {rc}]")
    return rc

# Confirm exact installed pg-17 version
run("dpkg -l postgresql-17 | tail -3")
# List the pool directory for postgresql-17
run("curl -s 'https://apt.postgresql.org/pub/repos/apt/pool/main/p/postgresql-17/' | grep -oE 'postgresql-server-dev-17_[^\"]+\\.deb' | sort -u | tail -10")
