![Æther Logo](/frontend/src/assets/images/ReadmeLogo.svg)

# Æther

### Architecture

![Architecture diagram](/frontend/src/assets/images/architecture_diagram.svg#gh-light-mode-only)
![Architecture diagram](/frontend/src/assets/images/architecture_diagram_dark.svg#gh-dark-mode-only)

### Installation

1. **Clone repository:**
   ##### SSH
   ```sh
   git clone git@github.com:hsfl-htit/Aether.git
   ```
   
2. **Navigate to directory:**
   ```sh
   cd Aether
   ```
      
3. **Build and start the application:**
   ```sh
   docker compose up --build
   ```

The application should now be running at [http://localhost/](http://localhost/).

The api should be available here [http://localhost/api](http://localhost/api).

4. **Start vite server with HMR:**
   ```sh
   npm run dev
   ```

Vite server with HMR is running at [http://localhost:5173](http://localhost:5173).
   
# 🛡️ Backend Setup – FastAPI + Keycloak + PostgreSQL

Dieses Backend verwendet FastAPI, Keycloak für Authentifizierung und PostgreSQL als Datenbank. Es ist vollständig containerisiert über Docker Compose und unterstützt lokale Entwicklung sowie Deployment via CI/CD.

---

## 🔧 Voraussetzungen

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)
- `.env.dev`-Datei mit den benötigten Variablen (siehe unten)

---

## 📁 Projektstruktur (Ausschnitt)

├── backend/
│ └── app/
│ └── main.py
├── telegram_scraper/ # Scraper-Dockerfile & Code
├── job_launcher/ # FastAPI API zum Starten von Jobs
├── keycloak/
│ └── exports/
│ └── HotTopics-realm.json # Realm für Keycloak
├── docker-compose.yml
├── .env.dev

````

---

## 📄 .env.dev (Beispiel)

```env
# Postgres
DB_USER=devuser
DB_PASSWORD=devpass

# Keycloak admin
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=admin
KEYCLOAK_HOSTNAME=keycloak
KEYCLOAK_HOSTNAME_STRICT=false

KEYCLOAK_INTERNAL_URL=http://keycloak:8080/realms/HotTopics

KEYCLOAK_URL=http://localhost:8080/realms/HotTopics
KEYCLOAK_CLIENT_ID=HotTopics
KEYCLOAK_CLIENT_SECRET=IVe53dL7kdbCLz8rpepuDEr1KaZnvNx0
PUBLIC_KEY_URL=/protocol/openid-connect/certs
KEYCLOAK_BASE_URL=http://keycloak:8080
SWAGGER_TOKEN_URL=http://localhost:8080/realms/HotTopics/protocol/openid-connect/token
KEYCLOAK_PUBLIC_URL=http://localhost:8080/realms/HotTopics

KEYCLOAK_ADMIN_CLIENT_ID=backend-admin-client
KEYCLOAK_ADMIN_CLIENT_SECRET=F0DVD1k2c9N6IBRxbhvCsHaUpQbXltHz

TG_API_ID=...
TG_API_HASH=...
TG_PHONE=+...
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=telegramdb
POSTGRES_USER=telegramuser
POSTGRES_PASSWORD=secretpass

NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=secretpass

JOB_LAUNCHER_URL=http://job-launcher:9001
JOB_SECRET_TOKEN=supersecure
# Hier pfad ins repo und /shared/media... Falls nicht vorhanden Bitte ordner anlegen...
MEDIA_PATH=${PWD}/shared/media

````

🧱 Dienste im Überblick
Dienst	Beschreibung
backend	FastAPI + Keycloak Auth API
keycloak	Identity Provider mit Realm Import
postgres	Datenbank für Keycloak
neo4j	Graphdatenbank (z. B. für Channel-Verbindungen)
telegram-job	Scraper-Worker (per Job-Launcher gestartet)
job-launcher	API, die telegram-job Container startet
frontend	Nginx + Vite SPA

🚀 Lokaler Start (inkl. Realm Import)
```
docker compose down -v  # -v entfernt bestehende Volumes → wichtig für erstmaligen Realm-Import
docker compose --env-file .env.dev up --build -d # --build stellt sicher, dass aktuelle Images verwendet werden
```
    

📡 Zugänge
Dienst	URL
🔐 Keycloak Admin UI	http://localhost:8080
⚙️ FastAPI Swagger	http://localhost:8000/docs
🧠 Neo4j Browser	http://localhost:7474

## Telegram Scraper
### Doku von diesem Github Repo geklaut: https://github.com/unnohwn/telegram-scraper

Getting Telegram API Credentials 🔑

Visit https://my.telegram.org/auth
Log in with your phone number
Click on "API development tools"
Fill in the form:
App title: Your app name
Short name: Your app short name
Platform: Can be left as "Desktop"
Description: Brief description of your app
Click "Create application"
You'll receive:
api_id: A number
api_hash: A string of letters and numbers
Keep these credentials safe, you'll need them to run the script!

### In Swagger UI mit USER und Passwort Authentifizieren -> Dann können similarity search und Scraper gestartet werden.
### Similarity macht eine Abfrage und schmeißt das Ergebnis in die NEO4j
### Scraper bleibt solange als Container am Leben bis er gekillt wird ...
#### TODO: Parameter für SCraper wie lange er am Leben bleibt

### Troubleshooting
Temporär: Sollte bei Starten des Scrapers folgender Fehler auftreten:
```
docker.errors.ImageNotFound: 404 Client Error for http+docker://localhost/v1.48/images/create?tag=latest&fromImage=telegram-job: Not Found ("pull access denied for telegram-job, repository does not exist or may require 'docker login'") 
```

Muss einmalig das "telegram-job" Image gebuilded werden:
```
cd telegram_scraper
docker build -t telegram-job:latest .
```

## 🕵️‍♂️ Telegram Scraper

### ✅ Features

- Supports multiple `MODE`s:
  - `similar` – recommends similar channels based on Telegram's API and optionally writes to Neo4j.
  - `scrape` – scrapes historical + live messages.
  - `full` – scrapes + finds similar channels + scrapes those too.
  - `live` – only listens for new messages (no backfill).
- Recursive scraping through invite links.
- Channels are only marked as `scraped` if actual messages are saved.
- Optional flag `SKIP_HISTORY=1` to ignore past messages and only do live tracking.
- Uses containerized scraper jobs triggered dynamically via `job-launcher`.

---

### ⚙️ ENV Parameters – Additions

```env
# Scraper control flags
MODE=full               # scrape | full | similar | live
CHANNELS=cryptovalleyweek
SESSION_NAME=default
RECURSIVE=1             # Enables invite link discovery
NEO4J_WRITE=1           # Writes similarity output to Neo4j
SKIP_HISTORY=1          # Disables historic backfill, useful for live-only

# Job Launcher
JOB_LAUNCHER_URL=http://job-launcher:9001
JOB_SECRET_TOKEN=supersecure
