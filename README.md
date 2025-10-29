![Æthery Logo](/frontend/src/assets/images/ReadmeLogo.svg)

# Æthery - Telegram Monitoring and Analysis Tool

Aether is an OSINT (Open Source Intelligence) web application for creating and managing Telegram-based monitoring projects. It enables users to define cases, add and track Telegram channels/groups, collect messages automatically via scrapers, and analyze the data using full-text search and Neo4j-based graph visualizations.

![Demo](/frontend/src/assets/images/demo.png)


## 🔧 Prerequisites

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)

## 🚀 Installation

1. **Clone repository:**
   ```sh
   git clone git@github.com:hsfl-htit/Aether.git
   ```
   
2. **Navigate to directory:**
   ```sh
   cd Aether
   ```

3. **Create .env.dev with required variables (see below):**
   ```sh
   nano .env.dev
   ```
      
4. **Build and start the application:**
   ```sh
   docker compose --env-file .env.dev up --build
   ```

The application should now be running at [http://localhost/](http://localhost/).

| **Service**              | **URL**                      |
| ------------------------ | ---------------------- |
| 🖥️ **Frontend** | [http://localhost](http://localhost)           |
| 🔐 **Keycloak Admin UI** | [http://localhost:8080](http://localhost:8080)           |
| ⚙️ **FastAPI Swagger**   | [http://localhost:8000/docs](http://localhost:8000/docs) |
| 🧠 **Neo4j Browser**     | [http://localhost:7474](http://localhost:7474)           |

### ⚙️ Development

1. **Navigate to directory:**
   ```sh
   cd frontend
   ```

2. **Install npm packages:**
   ```sh
   npm install
   ```
   
3. **Start vite server with HMR (Hot Module Replacement):**
   ```sh
   npm run dev
   ```

Vite server with HMR is running at [http://localhost:5173](http://localhost:5173).

### 📄 .env.dev (Example)

```env
# Postgres
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

TG_API_ID=25718412
TG_API_HASH=ac7d797b83488d421bfe2eed87269481
# Replace with your phone number (used for telegram)
TG_PHONE=+49123456789
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

MEDIA_PATH=${PWD}/shared/media

FRONTEND_URL=http://localhost/
ENVIRONMENT=dev
```

## 🏗️ Architecture

### 📈 Diagram

![Architecture diagram](/frontend/src/assets/images/architecture_diagram.svg#gh-light-mode-only)
![Architecture diagram](/frontend/src/assets/images/architecture_diagram_dark.svg#gh-dark-mode-only)

### 🧱 Services
| **Service**      | **Description** |
| ---------------- | --------------------------------- |
| **backend**      | FastAPI-based API with Keycloak authentication                 |
| **keycloak**     | Identity provider with preconfigured realm import              |
| **postgres**     | Database used by `keycloak` and `backend`   |
| **neo4j**        | Graph database (e.g., for modeling channel relationships)      |
| **telegram-job** | Scraper worker, triggered via `job launcher` |
| **job-launcher** | API service responsible for starting `telegram-job` containers |
| **frontend**     | Single-page application built with React and served via Nginx   |

## 📘 User guide

**Getting started:**

1. Register or login here: [https://æthery.cloud](https://æthery.cloud) or if running locally here: [http://localhost](https://localhost)
2. Go to `Settings` and create a new telegram session
3. Enter your phone number and type in your `2FA-Code` that you will recieve on your `Telegram-App`
4. Switch to `Cases` and create a `new case` using the corresponding button
5. Enter a name, category and description
6. In the next step enter all the names of `Telegram channels or groups` you want to monitor
7. After creating a new case scrapers will automatically start and monitor your selected channels
8. Now you can start analysing the data, while new messages will be scraped in the backgroud
9. You can also add or modify the `widgets` on your `dashboard` to e.g. focus on specific keywords across cases and channels

