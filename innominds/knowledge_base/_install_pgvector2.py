import paramiko
HOST="192.168.204.65"; SSH_USER="root"; SSH_PASS="FRIDEbAsec"
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

# dpkg -i bypasses apt's full transitive dep check; only checks pkg's own declared deps
run("dpkg -i /tmp/pgvector.deb")
run("ls -la /usr/share/postgresql/17/extension/vector* /usr/lib/postgresql/17/lib/vector*")
c.close()
