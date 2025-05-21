# HTIT-Monitor

### Installation

1. **Clone repository:**
   ##### SSH
   ```sh
   git clone git@github.com:hsfl-htit/monitor.git
   ```
   
2. **Navigate to directory:**
   ```sh
   cd monitor
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
├── keycloak/
│ └── realm/
│ └── HotTopics-realm.json
├── docker-compose.yml
├── .env.dev

````

---

## 📄 .env.dev (Beispiel)

```env
DB_USER=devuser
DB_PASSWORD=devpass

KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=admin

KEYCLOAK_HOSTNAME=keycloak
KEYCLOAK_CLIENT_ID=HotTopics
KEYCLOAK_CLIENT_SECRET=changeme
KEYCLOAK_ADMIN_CLIENT_ID=backend-admin-client
KEYCLOAK_ADMIN_CLIENT_SECRET=changeme
SWAGGER_TOKEN_URL=http://keycloak:8080/realms/HotTopics/protocol/openid-connect/token
KEYCLOAK_BASE_URL=http://keycloak:8080
````

Starten (lokal)
```
docker compose --env-file .env.dev up --build
```
Dann öffne:

    🔐 Keycloak UI: http://localhost:8080

    ⚙️ FastAPI Swagger UI: http://localhost:8000/api/docs