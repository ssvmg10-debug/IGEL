import os
import paramiko
HOST = os.environ["DB_SSH_HOST"]
SSH_USER = os.environ.get("DB_SSH_USER", "root")
SSH_PASS = os.environ["DB_SSH_PASSWORD"]
DB_NAME = os.environ.get("DB_NAME", "IGEL")
DB_ROLE = os.environ.get("DB_ROLE", "igle")
DB_PASS = os.environ["DB_ROLE_PASSWORD"]

c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=SSH_USER, password=SSH_PASS, timeout=15, allow_agent=False, look_for_keys=False)

def run(cmd, t=120):
    print(f"\n$ {cmd}")
    chan = c.get_transport().open_session(); chan.set_combine_stderr(True); chan.exec_command(cmd)
    while True:
        if chan.recv_ready(): print(chan.recv(8192).decode(errors="replace"), end="")
        if chan.exit_status_ready(): break
    while chan.recv_ready(): print(chan.recv(8192).decode(errors="replace"), end="")
    rc = chan.recv_exit_status(); print(f"\n[exit {rc}]"); return rc

def pg(sql, db="postgres"):
    """Run SQL as postgres OS user via su; returns the same `run` rc.
    Single quotes in SQL must be escaped already."""
    cmd = f"""su - postgres -c "psql -d '{db}' -v ON_ERROR_STOP=1 -c \\"{sql}\\""  """
    return run(cmd)

# Role
sql_role = (
    "DO \\$do\\$ BEGIN "
    f"IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='{DB_ROLE}') THEN "
    f"CREATE ROLE {DB_ROLE} WITH LOGIN PASSWORD '{DB_PASS}' CREATEDB; "
    "ELSE "
    f"ALTER ROLE {DB_ROLE} WITH LOGIN PASSWORD '{DB_PASS}'; "
    "END IF; "
    "END \\$do\\$;"
)
pg(sql_role)

# Database
run(
    "su - postgres -c \"psql -tAc \\\"SELECT 1 FROM pg_database WHERE datname='IGEL'\\\"\" "
    "| grep -q 1 "
    "|| su - postgres -c 'psql -v ON_ERROR_STOP=1 -c \\\"CREATE DATABASE \\\\\\\"IGEL\\\\\\\" OWNER igle;\\\"'"
)

# Extensions
pg("CREATE EXTENSION IF NOT EXISTS vector;", db=DB_NAME)
pg('CREATE EXTENSION IF NOT EXISTS \\\\\\"uuid-ossp\\\\\\";', db=DB_NAME)
pg(f"GRANT ALL ON SCHEMA public TO {DB_ROLE};", db=DB_NAME)

# Reload pg_hba (entry was added by previous run)
pg("SELECT pg_reload_conf();")

# Verify
run(f'su - postgres -c "psql -d \\"{DB_NAME}\\" -c \\\"\\\\dx\\\"\"')
run(f'su - postgres -c "psql -c \\\"\\\\du {DB_ROLE}\\\""')

c.close()
