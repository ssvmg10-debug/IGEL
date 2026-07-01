import paramiko
import os
HOST = os.environ["DB_SSH_HOST"]; SSH_USER = os.environ.get("DB_SSH_USER", "root"); SSH_PASS = os.environ["DB_SSH_PASSWORD"]
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=SSH_USER, password=SSH_PASS, timeout=15, allow_agent=False, look_for_keys=False)

def run(cmd, t=600):
    print(f"\n$ {cmd}")
    chan = c.get_transport().open_session(); chan.set_combine_stderr(True); chan.exec_command(cmd)
    while True:
        if chan.recv_ready(): print(chan.recv(8192).decode(errors="replace"), end="")
        if chan.exit_status_ready(): break
    while chan.recv_ready(): print(chan.recv(8192).decode(errors="replace"), end="")
    rc = chan.recv_exit_status()
    print(f"\n[exit {rc}]")
    return rc

URL = "https://apt.postgresql.org/pub/repos/apt/pool/main/p/pgvector/postgresql-17-pgvector_0.8.2-1.pgdg11%2B1_amd64.deb"
# Download
run(f"cd /tmp && rm -f pgvector.deb && wget -q '{URL}' -O pgvector.deb && ls -la pgvector.deb")
# Inspect deps
run("dpkg-deb -I /tmp/pgvector.deb | grep -E 'Depends|Version'")
# Install
run("DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/pgvector.deb")
# Verify files installed
run("ls -la /usr/share/postgresql/17/extension/vector* /usr/lib/postgresql/17/lib/vector*")
c.close()
