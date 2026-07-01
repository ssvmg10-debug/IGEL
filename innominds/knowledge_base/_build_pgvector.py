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
            data = chan.recv(4096).decode(errors="replace")
            print(data, end="")
        if chan.exit_status_ready():
            break
    # drain
    while chan.recv_ready():
        data = chan.recv(4096).decode(errors="replace"); print(data, end="")
    rc = chan.recv_exit_status()
    print(f"\n[exit {rc}]")
    return rc

# Verify pgxs makefile actually exists
run("ls /usr/lib/postgresql/17/lib/pgxs/src/makefiles/pgxs.mk && ls /usr/include/postgresql/17/server/postgres.h")

# Clean any prior build attempt
run("rm -rf /tmp/pgvector_build && mkdir -p /tmp/pgvector_build")
# Use a known stable tag (v0.8.0) that supports PG17
run("cd /tmp/pgvector_build && git clone --depth 1 --branch v0.8.0 https://github.com/pgvector/pgvector.git")
run("cd /tmp/pgvector_build/pgvector && PG_CONFIG=/usr/bin/pg_config make 2>&1 | tail -30")
run("cd /tmp/pgvector_build/pgvector && PG_CONFIG=/usr/bin/pg_config make install 2>&1 | tail -30")

# Verify
run("ls -la /usr/share/postgresql/17/extension/vector* /usr/lib/postgresql/17/lib/vector* 2>&1 | head")
c.close()
