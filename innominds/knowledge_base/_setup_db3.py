"""Upload a shell script + SQL file via SFTP, then execute as root."""
import paramiko
HOST="192.168.204.65"; SSH_USER="root"; SSH_PASS="FRIDEbAsec"

SETUP_SQL = """\
-- Run as the postgres superuser. Idempotent.
DO $do$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='igle') THEN
    CREATE ROLE igle WITH LOGIN PASSWORD '12345' CREATEDB;
  ELSE
    ALTER ROLE igle WITH LOGIN PASSWORD '12345';
  END IF;
END $do$;

SELECT format('CREATE DATABASE %I OWNER %I', 'IGEL', 'igle')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname='IGEL') \\gexec
"""

SETUP_DB_SQL = """\
-- Run inside the IGEL database
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
GRANT ALL ON SCHEMA public TO igle;
"""

SETUP_SH = """\
#!/bin/bash
set -e
echo '--- Creating role + database ---'
su - postgres -c 'psql -v ON_ERROR_STOP=1 -f /tmp/igel_setup.sql'
echo '--- Installing extensions in IGEL db ---'
su - postgres -c 'psql -d IGEL -v ON_ERROR_STOP=1 -f /tmp/igel_db.sql'
echo '--- Reloading pg_hba.conf ---'
su - postgres -c 'psql -c "SELECT pg_reload_conf();"'
echo '--- Verification ---'
su - postgres -c 'psql -d IGEL -c "\\\\dx"'
su - postgres -c 'psql -c "\\\\du igle"'
"""

c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=SSH_USER, password=SSH_PASS, timeout=15, allow_agent=False, look_for_keys=False)

# Upload via SFTP
sftp = c.open_sftp()
def write_remote(path, body):
    with sftp.open(path, "w") as f: f.write(body)
    print(f"wrote {path} ({len(body)} bytes)")

write_remote("/tmp/igel_setup.sql", SETUP_SQL)
write_remote("/tmp/igel_db.sql", SETUP_DB_SQL)
write_remote("/tmp/igel_setup.sh", SETUP_SH)
sftp.chmod("/tmp/igel_setup.sh", 0o755)
sftp.close()

# Execute
def run(cmd):
    print(f"\n$ {cmd}")
    chan = c.get_transport().open_session(); chan.set_combine_stderr(True); chan.exec_command(cmd)
    while True:
        if chan.recv_ready(): print(chan.recv(8192).decode(errors="replace"), end="")
        if chan.exit_status_ready(): break
    while chan.recv_ready(): print(chan.recv(8192).decode(errors="replace"), end="")
    rc = chan.recv_exit_status(); print(f"\n[exit {rc}]"); return rc

# Make /tmp/*.sql world-readable so postgres user can read them
run("chmod 644 /tmp/igel_setup.sql /tmp/igel_db.sql")
run("/tmp/igel_setup.sh")
c.close()
