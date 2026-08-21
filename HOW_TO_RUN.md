# How to Run LabHive

## Prerequisites

- Python 3.10+
- pip

## Setup

### 1. Clone the repository and navigate into it

```bash
git clone <repo-url>
cd labhive
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
.venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
FLASK_APP=run.py
FLASK_ENV=development

SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret-key

# Optional: defaults to SQLite (sqlite:///labhive.db)
DATABASE_URL=sqlite:///labhive.db

# Optional: seed script defaults shown below
ADMIN_EMAIL=admin@labhive.local
ADMIN_PASSWORD=changeme
ADMIN_FIRST_NAME=Admin
ADMIN_LAST_NAME=User
```

### 5. Apply database migrations

```bash
flask db upgrade
```

### 6. Seed the database (first run only)

Creates the initial super-admin account using the values from `.env`:

```bash
python seed.py
```

### 7. Run the development server

```bash
python run.py
```

The API will be available at `http://127.0.0.1:5000`.

---

## Running Tests

```bash
pytest
```

---

## Project Structure

```
labhive/          Application package (models, routes, schemas, utils)
migrations/     Alembic migration scripts
tests/          Unit and functional tests
run.py          Application entry point
seed.py         Database seeding script
```
