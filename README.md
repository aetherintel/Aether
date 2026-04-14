![Æthery Logo](/frontend/src/assets/images/ReadmeLogo.svg)

# Æthery — Telegram Monitoring and Analysis Tool

Æthery is an open-source OSINT (Open Source Intelligence) platform for monitoring and analyzing Telegram channels and groups. Define cases, track channels, collect messages automatically via scrapers, and analyze data using full-text search, AI-assisted analysis, and graph visualizations.

![Demo](/frontend/src/assets/images/demo.png)

## 📖 Documentation

See the [Tutorial](aether_tutorial/README.md) for a step-by-step user guide.

## 🔧 Prerequisites

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)
- A Telegram account with API credentials ([my.telegram.org](https://my.telegram.org))

## 🚀 Installation

1. **Clone the repository:**
   ```sh
   git clone git@github.com:hsfl-htit/Aether.git
   cd Aether
   ```

2. **Create your environment file:**
   ```sh
   cp .env.example .env.dev
   nano .env.dev
   ```

3. **Build and start the application:**
   ```sh
   docker compose --env-file .env.dev up --build
   ```

The application is now running at [http://localhost](http://localhost).

| Service | URL |
|---------|-----|
| 🖥️ **Frontend** | [http://localhost](http://localhost) |
| 🔐 **Keycloak Admin UI** | [http://localhost:8080](http://localhost:8080) |
| ⚙️ **FastAPI Swagger** | [http://localhost:8000/docs](http://localhost:8000/docs) |
| 🧠 **Neo4j Browser** | [http://localhost:7474](http://localhost:7474) |

### ⚙️ Frontend Development (HMR)

```sh
cd frontend
npm install
npm run dev
```

Vite dev server with Hot Module Replacement runs at [http://localhost:5173](http://localhost:5173).

### 📄 .env.dev Example

> ⚠️ Never commit your `.env.dev` to version control.

```env
# PostgreSQL
DB_USER=devuser
DB_PASSWORD=devpass

# Keycloak
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=admin
KEYCLOAK_HOSTNAME=keycloak
KEYCLOAK_CLIENT_ID=Aether
KEYCLOAK_CLIENT_SECRET=IVe53dL7kdbCLz8rpepuDEr1KaZnvNx0
KEYCLOAK_ADMIN_CLIENT_ID=backend-admin-client
KEYCLOAK_ADMIN_CLIENT_SECRET=F0DVD1k2c9N6IBRxbhvCsHaUpQbXltHz
SWAGGER_TOKEN_URL=http://keycloak:8080/realms/Aether/protocol/openid-connect/token
KEYCLOAK_BASE_URL=http://keycloak:8080
KEYCLOAK_URL=http://localhost:8080/realms/Aether
KEYCLOAK_INTERNAL_URL=http://keycloak:8080/realms/Aether

# Telegram — get your credentials at https://my.telegram.org
TG_API_ID=your_api_id
TG_API_HASH=your_api_hash
TG_PHONE=+49123456789

# PostgreSQL (backend)
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=telegramdb
POSTGRES_USER=telegramuser
POSTGRES_PASSWORD=secretpass

# Neo4j
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=secretpass

# Job Launcher
JOB_LAUNCHER_URL=http://job-launcher:9001
JOB_SECRET_TOKEN=supersecure

# General
MEDIA_PATH=${PWD}/shared/media
FRONTEND_URL=http://localhost/
ENVIRONMENT=dev
```

## 🏗️ Architecture

### 📈 Diagram

![Architecture diagram (light)](/frontend/src/assets/images/architecture_diagram.svg#gh-light-mode-only)
![Architecture diagram (dark)](/frontend/src/assets/images/architecture_diagram_dark.svg#gh-dark-mode-only)

### 🧱 Services

| Service | Description |
|---------|-------------|
| **backend** | FastAPI REST API with Keycloak authentication |
| **keycloak** | Identity provider with preconfigured realm import |
| **postgres** | Relational database used by Keycloak and the backend |
| **neo4j** | Graph database for modeling channel relationships |
| **telegram-job** | Scraper worker, triggered by the job launcher |
| **job-launcher** | API service for spawning `telegram-job` containers |
| **frontend** | React SPA served via Nginx |

## 📘 Quick Start Guide

1. Register at [https://æthery.cloud](https://æthery.cloud) or [http://localhost](http://localhost)
2. Go to **Settings** → create a new **Telegram Session** and authenticate with your phone number
3. Go to **Cases** → click **New Case**, enter a name and category
4. Add the Telegram channel usernames you want to monitor
5. Scrapers start automatically — messages are collected in the background
6. Open a case and use the **Messages**, **Agent Chat**, and **Reports** tabs to analyze your data

For detailed instructions with screenshots, see the [Tutorial](aether_tutorial/README.md).

## 🔐 Full Setup & Relaunch

For production deployment including all required credentials and third-party service setup,
access to the internal setup guide can be requested from the maintainers:
[Full-Setup Guide](https://gist.github.com/FredErikFelsch/996e8dd4d3f1fc8be0530ce266a7a040).
