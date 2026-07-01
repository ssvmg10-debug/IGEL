"""One-shot setup: install pgvector + create IGEL DB & igle user."""
import os
import paramiko
import sys

HOST = os.environ["DB_SSH_HOST"]
SSH_USER = os.environ.get("DB_SSH_USER", "root")
SSH_PASS = os.environ["DB_SSH_PASSWORD"]

DB_NAME = os.environ.get("DB_NAME", "IGEL")
DB_ROLE = os.environ.get("DB_ROLE", "igle")
DB_PASS = os.environ["DB_ROLE_PASSWORD"]


def run(client, cmd, hide_output=False):
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if not hide_output:
        if out.strip():
            print(out.rstrip())
        if err.strip():
            print(f"[stderr] {err.rstrip()}")
    print(f"[exit {rc}]")
    return rc, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {SSH_USER}@{HOST}...")
    client.connect(HOST, username=SSH_USER, password=SSH_PASS, timeout=15, allow_agent=False, look_for_keys=False)
    print("Connected.")

    run(client, "lsb_release -a 2>/dev/null || cat /etc/os-release")
    run(client, "psql --version")
    run(client, "dpkg -l | grep -i pgvector || echo 'pgvector pkg NOT installed'")

    print("\n=== Installing pgvector ===")
    run(client, "DEBIAN_FRONTEND=noninteractive apt-get update -y", hide_output=True)
    rc, _, _ = run(client, "DEBIAN_FRONTEND=noninteractive apt-get install -y postgresql-17-pgvector")
    if rc != 0:
        print("\npostgresql-17-pgvector install failed; trying alternate names...")
        run(client, "apt-cache search pgvector")
        sys.exit(1)

    print("\n=== Creating role and database ===")
    sql = (
        f"DO $$ BEGIN "
        f"  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='{DB_ROLE}') THEN "
        f"    CREATE ROLE {DB_ROLE} WITH LOGIN PASSWORD '{DB_PASS}' CREATEDB; "
        f"  ELSE "
        f"    ALTER ROLE {DB_ROLE} WITH LOGIN PASSWORD '{DB_PASS}'; "
        f"  END IF; "
        f"END $$;"
    )
    run(client, f'sudo -u postgres psql -c "{sql}"')
    run(client, f'sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname=\'{DB_NAME}\'"')
    run(client,
        f'sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname=\'{DB_NAME}\'" '
        f'| grep -q 1 || sudo -u postgres createdb -O {DB_ROLE} {DB_NAME}')
    run(client, f'sudo -u postgres psql -d "{DB_NAME}" -c "CREATE EXTENSION IF NOT EXISTS vector;"')
    run(client, f'sudo -u postgres psql -d "{DB_NAME}" -c "CREATE EXTENSION IF NOT EXISTS \\"uuid-ossp\\";"')
    run(client, f'sudo -u postgres psql -d "{DB_NAME}" -c "GRANT ALL PRIVILEGES ON SCHEMA public TO {DB_ROLE};"')
    run(client, f'sudo -u postgres psql -d "{DB_NAME}" -c "ALTER DATABASE \\"{DB_NAME}\\" OWNER TO {DB_ROLE};"')

    print("\n=== Verifying pg_hba allows igle from this client subnet ===")
    run(client, "grep -E '^host' /etc/postgresql/17/main/pg_hba.conf | head -20")

    print("\n=== Final verification ===")
    run(client, f'sudo -u postgres psql -d "{DB_NAME}" -c "\\dx"')
    run(client, f'sudo -u postgres psql -c "\\du {DB_ROLE}"')

    client.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
