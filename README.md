# Biobank Bingo — Render edition

## What it does
Host creates a game and QR code. Players join from phones, get shuffled 4x4 cards, mark terms, and claim a verified line. The host calls clues and sees winners. The 16 terms are defined in `app.py`.

## Local test (Ubuntu / WSL)
```bash
cd biobank_bingo_app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
python app.py
```
Open http://localhost:5000 . Local games persist in `bingo.sqlite3`.

## Publish on Render
1. Create a GitHub repository and upload the **contents** of this folder (including `render.yaml`). Do not upload `.venv`, `.sqlite3` or secrets.
2. In https://dashboard.render.com select **New → Blueprint**, connect GitHub and select your repository.
3. Review the service, **paid Starter plan and persistent disk charges** and confirm creation. `render.yaml` configures Gunicorn, the disk, a secret key and health check.
4. Wait for the service to become Live. Open the `https://...onrender.com` URL Render assigns. Create a game and display its QR code.
5. Test on two separate phones before the event. QR code automatically uses the current public HTTPS host.

## Notes
- Persistent data is stored on the attached disk at `/var/data/bingo.sqlite3`. Keep `SECRET_KEY` unchanged across redeploys or host/player cookies become invalid.
- Single Gunicorn worker is intentional: the SQLite state updates and Socket.IO rooms are not configured for multiple worker instances. Do not scale workers/instances without migrating to Postgres and a shared event/message broker.
- Host access is tied to the browser that created the game. Keep that browser session open; there is no host account recovery in this edition.
- Participant names are optional. Avoid collecting real patient/sample information.
- The app is an event-ready baseline, not an audited high-scale platform. Test expected attendee load and use a reliable network.
- For substantial usage, use Postgres and a managed realtime/pubsub backend.
