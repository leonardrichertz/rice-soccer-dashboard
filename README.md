# Rice Soccer Dashboard

A Shiny for Python dashboard for analyzing Rice women's soccer team, player, opponent, and comparison data using Wyscout Event Level Data.

## Setup

1. Create and activate a virtual environment (recommended).

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start a local Postgres database:

```bash
docker compose up -d
```

4. Copy `.env.example` to `.env` (the default values already match `docker-compose.yml`):

```bash
cp .env.example .env
```

5. Create the schema and load whatever CSVs you currently have in `data/`:

```bash
python scripts/seed_db.py
```

Re-run with `--reset` if you need to drop and recreate the tables (e.g. after changing `db/schema.sql` or swapping in a new data export). The app itself reads from the database, not from `data/*.csv` directly.

## Run the application

From the project root:

```bash
python -m shiny run app.py
```

Shiny will print a local URL (for example `http://127.0.0.1:8000`). Open that address in your browser to use the dashboard.

To automatically reload when you change code:

```bash
python -m shiny run --reload app.py
```
