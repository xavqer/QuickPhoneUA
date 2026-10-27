# Production Update Runbook

Use this runbook when you already have the site running in production behind `gunicorn` and `nginx`, and you want to deploy new code from this repository.

## Current public demo

The live demo at https://quickphone.com.ua uses `/srv/quickphoneua-demo` and `config.settings.demo`. Its private environment file is `site/.env.prod`; its writable database is `site/.demo/db.sqlite3`. Run updates as `deploy` from the new checkout:

```bash
cd /srv/quickphoneua-demo
bash deploy.sh
```

The deploy script resolves its own project directory, backs up the demo database and environment, updates dependencies/assets, applies demo migrations and checks HTTPS health and registration HTTP 403. Existing demo records are preserved. The published `demo_admin` credentials are for local development; this account is disabled in the hosted database.

The old `/srv/quickphoneua` checkout and PostgreSQL database are preserved. The initial switch was backed up under `/srv/quickphoneua-backup-*`. Gunicorn uses the `99-demo.conf` systemd override; Nginx serves static/media files from the new checkout.

The following sections describe the separate PostgreSQL production configuration. Do not apply those commands to the SQLite demo.

## Assumptions

- The production server already has:
  - a cloned repo
  - a Python virtual environment
  - Node.js and npm for the local Tailwind build
  - a working `gunicorn` service
  - a working `nginx` site
- You deploy by pulling from git on the server.
- Your production environment uses `config.settings.production`.

## Important Note About This Repo

`site/config/wsgi.py` defaults to:

```python
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
```

That is fine for local development, but in production your `gunicorn` service or environment file must explicitly set:

```bash
DJANGO_SETTINGS_MODULE=config.settings.production
```

If production does not set that explicitly, the server may boot with local settings.

## Replace These Placeholders First

- `PROJECT_DIR`: path to repo on the server, for example `/srv/quickphoneua`
- `VENV_DIR`: path to the virtualenv, for example `/srv/quickphoneua/venv`
- `GUNICORN_SERVICE`: systemd unit name, for example `quickphoneua-gunicorn`
- `NGINX_SERVICE`: usually `nginx`

The storefront now lives under `PROJECT_DIR/site`, so Django commands, `gunicorn --chdir`, `WorkingDirectory`, and any env-file paths must point there.

## Standard Deploy Steps

SSH into the production server, then run:

```bash
cd PROJECT_DIR
git status
git pull --ff-only

source VENV_DIR/bin/activate
cd site
pip install -r requirements.txt
npm ci
npm run build:css

export DJANGO_SETTINGS_MODULE=config.settings.production

python manage.py check --settings=config.settings.production
python manage.py migrate --settings=config.settings.production
python manage.py collectstatic --noinput --settings=config.settings.production

sudo systemctl restart GUNICORN_SERVICE
sudo systemctl reload NGINX_SERVICE
```

## Recommended Post-Deploy Checks

Run:

```bash
sudo systemctl status GUNICORN_SERVICE --no-pager
sudo systemctl status NGINX_SERVICE --no-pager
journalctl -u GUNICORN_SERVICE -n 100 --no-pager
curl -I https://your-domain.example/
```

Then manually verify:

- home page loads
- catalog page loads
- product detail loads
- checkout page loads
- static CSS/JS are updating as expected

## If The Release Includes Only Frontend Changes

You can still use the same sequence. `migrate` will simply do nothing if there are no new migrations.

Safe minimal version:

```bash
cd PROJECT_DIR
git pull --ff-only

source VENV_DIR/bin/activate
cd site
export DJANGO_SETTINGS_MODULE=config.settings.production

npm ci
npm run build:css
python manage.py collectstatic --noinput --settings=config.settings.production

sudo systemctl restart GUNICORN_SERVICE
sudo systemctl reload NGINX_SERVICE
```

## If Something Breaks

Check logs first:

```bash
journalctl -u GUNICORN_SERVICE -n 200 --no-pager
sudo tail -n 200 /var/log/nginx/error.log
```

Common causes:

- missing Python dependency after `git pull`
- migration not applied
- wrong `.env` values
- `DJANGO_SETTINGS_MODULE` still pointing to local settings
- stale static files because `collectstatic` was skipped

## Fast Rollback

If the latest deploy is bad and you need to restore the previous commit quickly:

```bash
cd PROJECT_DIR
git log --oneline -n 5
git checkout <previous-good-commit>

source VENV_DIR/bin/activate
cd site
export DJANGO_SETTINGS_MODULE=config.settings.production

npm ci
npm run build:css
python manage.py migrate --settings=config.settings.production
python manage.py collectstatic --noinput --settings=config.settings.production

sudo systemctl restart GUNICORN_SERVICE
sudo systemctl reload NGINX_SERVICE
```

After the incident, move the server back to a branch-based state instead of leaving it detached.

## Optional: One-Block Deploy Command

After you replace the placeholders with real values, this is the compact version:

```bash
cd PROJECT_DIR && \
source VENV_DIR/bin/activate && \
git pull --ff-only && \
cd site && \
pip install -r requirements.txt && \
npm ci && \
npm run build:css && \
export DJANGO_SETTINGS_MODULE=config.settings.production && \
python manage.py check --settings=config.settings.production && \
python manage.py migrate --settings=config.settings.production && \
python manage.py collectstatic --noinput --settings=config.settings.production && \
sudo systemctl restart GUNICORN_SERVICE && \
sudo systemctl reload NGINX_SERVICE
```
