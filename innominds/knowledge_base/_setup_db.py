import paramiko
HOST="192.168.204.65"; SSH_USER="root"; SSH_PASS="FRIDEbAsec"
DB_NAME="IGEL"; DB_ROLE="igle"; DB_PASS="12345"

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

# --- Create role + database (use quoted identifier so DB name keeps uppercase IGEL) ---
sql_role = (
    f"DO $do$ BEGIN "
    f"  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='{DB_ROLE}') THEN "
    f"    CREATE ROLE {DB_ROLE} WITH LOGIN PASSWORD '{DB_PASS}' CREATEDB; "
    f"  ELSE "
    f"    ALTER ROLE {DB_ROLE} WITH LOGIN PASSWORD '{DB_PASS}'; "
    f"  END IF; "
    f"END $do$;"
)
run(f'sudo -u postgres psql -v ON_ERROR_STOP=1 -c "{sql_role}"')

# Create DB if not exists, with quoted IGEL to preserve case
run(
    'sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname=\'IGEL\'" '
    '| grep -q 1 || sudo -u postgres psql -v ON_ERROR_STOP=1 '
    f'-c \'CREATE DATABASE "{DB_NAME}" OWNER {DB_ROLE};\''
)

# Extensions inside IGEL
run(f'sudo -u postgres psql -d "{DB_NAME}" -c "CREATE EXTENSION IF NOT EXISTS vector;"')
run(f'sudo -u postgres psql -d "{DB_NAME}" -c "CREATE EXTENSION IF NOT EXISTS \\"uuid-ossp\\";"')

# Privileges (PG 15+: public schema is restricted by default)
run(f'sudo -u postgres psql -d "{DB_NAME}" -c "GRANT ALL ON SCHEMA public TO {DB_ROLE};"')
run(f'sudo -u postgres psql -d "{DB_NAME}" -c "ALTER DATABASE \\"{DB_NAME}\\" OWNER TO {DB_ROLE};"')

# --- pg_hba: allow igle from the client subnet (we know 192.168.223.3 reaches here) ---
HBA = "/etc/postgresql/17/main/pg_hba.conf"
run(f"grep -nE 'igle|192.168.223' {HBA}")

# Add a host rule allowing igle@IGEL from the client subnet, if not already present
run(
    f"grep -qE '^host\\s+IGEL\\s+igle\\s+192\\.168\\.223\\.0/24' {HBA} "
    f"|| echo 'host    IGEL    igle    192.168.223.0/24    md5' >> {HBA}"
)
# Also ensure replication-style same-subnet entry just in case
run(f"tail -5 {HBA}")
# Reload (no restart needed for pg_hba changes)
run('sudo -u postgres psql -c "SELECT pg_reload_conf();"')

# Verify
run(f'sudo -u postgres psql -d "{DB_NAME}" -c "\\dx"')
run(f'sudo -u postgres psql -d "{DB_NAME}" -c "\\dn+"')
run(f'sudo -u postgres psql -c "\\du {DB_ROLE}"')
c.close()
