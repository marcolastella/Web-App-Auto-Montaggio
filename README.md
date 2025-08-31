# AutoVideo Interview – Web App (URL support, fresh)

Questa versione accetta **URL diretti** (es. Dropbox con `dl=1`) al posto dell'upload.

## Render env
- PORT=8000
- MAX_CONTENT_LENGTH_MB=4096
- GUNICORN_CMD_ARGS=--timeout 1800 --graceful-timeout 120 --keep-alive 120 -k gthread --threads 4 --worker-tmp-dir /dev/shm
- WEB_CONCURRENCY=1 (consigliato)

## Health
- `/health` → `ok`
