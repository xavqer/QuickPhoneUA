#!/usr/bin/env bash
set +x
set -euo pipefail
umask 027

PROJECT_DIR="/srv/quickphoneua"
SITE_DIR="$PROJECT_DIR/site"
VENV_DIR="$PROJECT_DIR/venv"
ENV_FILE="$SITE_DIR/.env.prod"
GUNICORN_SERVICE="quickphoneua"
BACKUP_DIR="$PROJECT_DIR/.tmp/deploy-backups/$(date -u +%Y%m%d-%H%M%S)"

if [[ "$(id -un)" != "deploy" ]]; then
    echo "Run this script as the deploy user." >&2
    exit 1
fi

cd "$PROJECT_DIR"
set -a
source "$ENV_FILE"
set +a

if [[ "${DJANGO_SETTINGS_MODULE:-}" != "config.settings.demo" ]]; then
    echo "First complete the demo switch in site/.env.prod; see the deployment guide." >&2
    exit 1
fi
: "${SECRET_KEY:?Set a private SECRET_KEY in site/.env.prod}"
: "${ALLOWED_HOSTS:?Set ALLOWED_HOSTS in site/.env.prod}"
: "${SITE_BASE_URL:?Set the HTTPS SITE_BASE_URL in site/.env.prod}"
[[ "$SITE_BASE_URL" == https://* ]] || { echo "SITE_BASE_URL must use HTTPS." >&2; exit 1; }

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    echo "Commit or back up tracked changes before deploying." >&2
    exit 1
fi

sudo nginx -t
source "$VENV_DIR/bin/activate"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
cp -p "$ENV_FILE" "$BACKUP_DIR/env.prod"
chmod 600 "$BACKUP_DIR/env.prod"
git rev-parse HEAD > "$BACKUP_DIR/commit.txt"

python - "$SITE_DIR/.demo/db.sqlite3" "$BACKUP_DIR/db.sqlite3" <<'PY'
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
source, backup = map(Path, sys.argv[1:])
if source.is_file():
    with closing(sqlite3.connect(source)) as old, closing(sqlite3.connect(backup)) as new:
        old.backup(new)
        assert new.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
PY

git pull --ff-only
cd "$SITE_DIR"
python -m pip install -r requirements.txt
npm ci
npm run build:css

python - <<'PY'
import sqlite3
from contextlib import closing
from pathlib import Path
seed = Path('db.sqlite3')
database = Path('.demo/db.sqlite3')
if not database.exists():
    with closing(sqlite3.connect(seed.resolve().as_uri() + '?mode=ro', uri=True)) as source:
        assert source.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert source.execute('SELECT username, email, phone FROM users_customuser').fetchall() == [
            ('demo_admin', 'admin@example.invalid', '')
        ], 'The bundled database must contain only the synthetic demo account.'
        assert source.execute('SELECT COUNT(*) FROM orders_order').fetchone()[0] == 0, 'The bundled database contains orders.'
        database.parent.mkdir(mode=0o750, exist_ok=True)
        temporary = database.with_suffix('.initializing')
        with closing(sqlite3.connect(temporary)) as target:
            source.backup(target)
            for table in ('django_session', 'django_admin_log', 'users_phoneverificationchallenge'):
                target.execute(f'DELETE FROM {table}')
            target.execute("UPDATE users_customuser SET password='!', is_active=0, last_login=NULL WHERE username='demo_admin'")
            target.commit()
            target.execute('VACUUM')
        temporary.replace(database)
    print('Initialized demo database. The published demo_admin account is disabled on the server.')
PY

python manage.py check --deploy --fail-level WARNING
python manage.py migrate --noinput
python manage.py collectstatic --noinput
sudo systemctl restart "$GUNICORN_SERVICE"
sudo systemctl is-active --quiet "$GUNICORN_SERVICE"
sudo systemctl reload nginx

HEALTH="$(curl --fail --silent --show-error --location --max-redirs 3 --max-time 10 --retry 5 --retry-connrefused --retry-delay 1 "${SITE_BASE_URL%/}/health/")"
[[ "$HEALTH" == "ok" ]] || { echo "Health check failed; inspect quickphoneua logs." >&2; exit 1; }
STATUS="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --max-time 10 "${SITE_BASE_URL%/}/users/register/")"
[[ "$STATUS" == "403" ]] || { echo "Demo registration check failed (HTTP $STATUS)." >&2; exit 1; }
echo "Demo updated. Backup: $BACKUP_DIR"
