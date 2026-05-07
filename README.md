# MatchUp

## Tehnoloogiad

- Python
- Django
- PostgreSQL
- PowerShell (Windows)

## Paigaldus (Windows / PowerShell)

### 1. Klooni projekt

https://github.com/GervinAnsi/MatchUp.git

### 2. Seadista projekt

Powershelli käsud järjekorras:

1. python -m venv venv

2. .\venv\Scripts\Activate

Kui saad errori siis:

Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

ja proovi uuesti:

.\venv\Scripts\Activate

3. pip install -r requirements.txt

### 3. PostgreSQL andmebaasi seadistamine

1. Ava pgAdmin
2. Logi sisse
3. Lisa uus Database
4. Pane nimeks:
   matchup_db

# Nimi peab kattuma .env failiga

### 4. .env faili loomine

1. Lisa uus fail ning nimeta see:

.env

2. Kopeeri see sisu sinna sisse:

DEBUG=True

SECRET_KEY=change-me

ALLOWED_HOSTS=127.0.0.1,localhost

DB_NAME=matchup_db

DB_USER=YOUR_POSTGRES_USER

DB_PASSWORD=YOUR_POSTGRES_PASSWORD

DB_HOST=localhost

DB_PORT=5432

### 5. Andmebaasi migratsioonid

Kasuta Powershelli käske järjekorras:

1. python manage.py makemigrations

2. python manage.py migrate

3. python manage.py createsuperuser

### 6. Projekti käivitamine:

Powershelli käsk:

1. python manage.py runserver

Ava:

2. http://127.0.0.1:8000/
