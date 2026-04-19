# Æther — System Design Overview

> A multi-tenant OSINT intelligence platform for collecting, enriching, and analysing Telegram data.

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLIENT                                      │
│                    React SPA (Vite + Mantine UI)                        │
│         /login  /cases  /cases/:id  /reports  /agent  /settings        │
└────────────────────────────┬────────────────────────────────────────────┘
                             │  HTTPS  (JWT Bearer — Keycloak token)
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         API GATEWAY                                      │
│               FastAPI  ·  Python 3.11  ·  Uvicorn                      │
│   /auth  /messages  /scrape  /queue  /casefiles  /osint  /events       │
└────┬──────────┬───────────┬──────────────┬───────────────┬─────────────┘
     │          │           │              │               │
     ▼          ▼           ▼              ▼               ▼
  Keycloak   Neo4j      Redis           Telethon        SSE stream
  (OIDC)    (Graph DB)  (Queue +       (Telegram       (pub/sub)
                         Cache)         scraper)
                                                           │
                                                           ▼
                                                    Modal LLM Service
                                                 (Codestral 22B · /agent)
```

---

## 2. Service Topology (Docker Compose)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  docker-compose                                                          │
│                                                                         │
│  ┌──────────┐   ┌──────────┐   ┌──────────────────────────────────┐   │
│  │ frontend │   │ backend  │   │            workers               │   │
│  │  :80/443 │   │  :8000   │   │  ┌────────────┐ ┌────────────┐  │   │
│  │  (Nginx) │   │ (FastAPI)│   │  │  telegram  │ │   image    │  │   │
│  └──────────┘   └────┬─────┘   │  │  worker×2  │ │   worker   │  │   │
│                      │         │  │ (Telethon) │ │ (EasyOCR)  │  │   │
│  ┌──────────┐        │         │  └────────────┘ └────────────┘  │   │
│  │  neo4j   │◄───────┤         │  ┌────────────┐ ┌────────────┐  │   │
│  │  :7474   │        │         │  │   audio    │ │translation │  │   │
│  │  :7687   │        │         │  │   worker   │ │   worker   │  │   │
│  └──────────┘        │         │  │ (Whisper)  │ │(NLLB-200 / │  │   │
│                      │         │  └────────────┘ │  Modal)    │  │   │
│  ┌──────────┐        │         │                 └────────────┘  │   │
│  │ postgres │◄───────┤         │  ┌────────────┐ ┌────────────┐  │   │
│  │  :5432   │        │         │  │  emotion   │ │classifier  │  │   │
│  └──────────┘        │         │  │   worker   │ │   worker   │  │   │
│                      │         │  │(local GPU /│ │(local GPU /│  │   │
│  ┌──────────┐        │         │  │  Modal)    │ │  Modal)    │  │   │
│  │  redis   │◄───────┤         │  └────────────┘ └────────────┘  │   │
│  │  :6379   │        │         │  ┌────────────┐ ┌────────────┐  │   │
│  └──────────┘        │         │  │   geo      │ │  report    │  │   │
│                      │         │  │   worker   │ │   worker   │  │   │
│  ┌──────────┐        │         │  │(GLiNER+GN) │ │  (PDF)     │  │   │
│  │keycloak  │◄───────┘         │  └────────────┘ └────────────┘  │   │
│  │  :8080   │                   └──────────────────────────────────┘   │
│  └──────────┘                                                          │
│                                                                         │
│  Modal.com (external, serverless GPU)                                   │
│  ┌─────────────────────────┐  ┌────────────────────────────────────┐   │
│  │ aether-llm-service      │  │  aether-classification / emotion / │   │
│  │ Codestral 22B Q4 (GGUF) │  │  translation workers               │   │
│  │ L40S · llama-cpp-python │  │  (T4 GPU · zero-shot / NLLB-200)   │   │
│  └─────────────────────────┘  └────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘

Deploy profiles:
  (default)   — image, audio, geo, report, telegram workers
  gpu-local   — translation, emotion, classification run locally with GPU
  modal       — translation, emotion, classification forwarded to Modal.com
```

---

## 3. Data Flow — Scrape Request (Happy Path)

```
User clicks "Start Scraper"
          │
          ▼
  POST /scrape  {channel, mode, workers, case_id}
          │
          ▼
  backend validates ──► enqueues ScrapeJob → Redis db=0 (telegram-jobs)
          │
          ▼
  ┌───────────────────────────────────────────┐
  │  telegram_worker (RQ, Redis db=0)          │
  │                                           │
  │  Telethon pulls messages + media          │
  │  ├─ writes Channel + Message nodes        │
  │  │   to Neo4j  (owner-scoped)             │
  │  │                                        │
  │  └─ chains downstream jobs:               │
  │      ├─ translation  → Redis db=1         │
  │      ├─ image_job    → Redis db=2         │
  │      ├─ audio_job    → Redis db=3         │
  │      ├─ emotion_job  → Redis db=4 ──► Modal.com (serverless GPU)
  │      ├─ classifier   → Redis db=5 ──► Modal.com (serverless GPU)
  │      └─ geo_job      → Redis db=6         │
  └───────────────────────────────────────────┘
          │
          ▼
  Each worker enriches the Neo4j node
  and publishes an SSE event → Redis pub/sub (db=7, channel: aether:events)
          │
          ▼
  GET /events/stream (SSE endpoint, filtered by owner_id)
          │
          ▼
  useSSE() hook → React state update → UI refreshes
```

---

## 4. Worker Pipeline

| # | Worker | Queue | Redis DB | Model / Library | Output (Neo4j) |
|---|--------|-------|----------|-----------------|----------------|
| 1 | **telegram_worker** ×2 | `telegram-jobs` | db=0 | Telethon | `Channel`, `Message`, `Media` nodes |
| 2 | **translation_worker** | `translation-jobs` | db=1 | NLLB-200-Distilled-600M (or Modal) | `translated_text` on Message |
| 3 | **image_worker** | `image-jobs` | db=2 | EasyOCR (Latin/Cyrillic/Arabic) | `ocr_text` on Message |
| 4 | **audio_worker** | `audio-jobs` | db=3 | OpenAI Whisper base + ffmpeg | `transcription` on Message |
| 5 | **emotion_worker** | `emotion-jobs` | db=4 | German-Emotions model (or Modal) | `emotion_labels[]` on Message |
| 6 | **classification_worker** | `classification-jobs` | db=5 | Custom classifier (or Modal) | `topic_labels[]` on Message |
| 7 | **geolocation_worker** | `geolocation-jobs` | db=6 | GLiNER NER + GeoNames index + ESRI | `Location` nodes, lat/lon |
| 8 | **report_worker** | `report-jobs` | — | PDF generation service | Report file on disk |

> Workers 2, 5 & 6 support **two deploy modes** via Docker Compose profiles:
> - `gpu-local` — model runs inside the container (requires GPU)
> - `modal` — thin HTTP forwarder to Modal.com serverless GPU endpoints (no local GPU needed)

---

## 5. Database Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  PostgreSQL 15  (relational — structured/operational data)   │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐               │
│  │  users   │  │casefiles │  │  reports   │               │
│  └──────────┘  └──────────┘  └────────────┘               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Neo4j 5.18  (graph — message relationships & enrichments)   │
│                                                             │
│  Channel ──HAS_MESSAGE──► Message ──HAS_ENTITY──► Entity   │
│                                   └──HAS_MEDIA──► Media     │
│                                   └──AT_LOCATION─► Location  │
│                                                             │
│  All nodes carry owner_id for multi-tenant isolation        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Redis 7  (ephemeral — queues & pub/sub)                     │
│                                                             │
│  DB 0  telegram-jobs          DB 4  emotion-jobs            │
│  DB 1  translation-jobs       DB 5  classification-jobs     │
│  DB 2  image-jobs             DB 6  geolocation-jobs        │
│  DB 3  audio-jobs             DB 7  pub/sub (SSE events)    │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Data Model (Neo4j Graph)

```
          ┌─────────────┐
          │    User      │  (Keycloak ID, multi-tenant owner)
          └──────┬──────┘
                 │ OWNS
          ┌──────▼──────┐
          │  CaseFile    │  (title, description, tgchannels[])
          └──────┬──────┘
                 │ HAS_CHANNEL
     ┌───────────▼──────────┐
     │      Channel          │  (channel_id, username, message_count)
     └───────────┬──────────┘
                 │ HAS_MESSAGE
     ┌───────────▼──────────┐
     │       Message         │  (message_id, text, translated_text,
     │                       │   ocr_text, transcription, date,
     │                       │   emotion_labels[], topic_labels[])
     └───┬───────────┬───────┘
         │           │
   HAS_MEDIA    HAS_ENTITY
         │           │
   ┌─────▼──┐  ┌─────▼──────┐
   │ Media  │  │   Entity    │  (name, type: PER/ORG/LOC/...)
   └────────┘  └─────┬──────┘
                     │ AT_LOCATION
               ┌─────▼──────┐
               │  Location   │  (lat, lon, name, country)
               └────────────┘
```

All nodes carry an `owner_id` property — every Cypher query is scoped
`WHERE n.owner_id = $owner_id` to ensure strict tenant isolation.

---

## 7. Authentication & Authorization

```
  Browser                Keycloak               Backend
    │                       │                      │
    │── POST /auth/login ───►│                      │
    │◄── JWT (access_token) ─│                      │
    │                       │                      │
    │── API request + Bearer token ───────────────►│
    │                       │◄── introspect token ─│
    │                       │─── user claims ──────►│
    │                       │                      │ user_ctx() extracts
    │                       │                      │ sub, roles, username
    │◄────────── 200 + data ──────────────────────-│
```

- Roles: `admin` (sees all data), regular users (own data only)
- `ProtectedRoute` component in React blocks unauthenticated navigation
- `authFetch()` utility automatically attaches the Bearer token to every API call

---

## 8. Real-Time Updates (SSE)

```
  Worker completes job
        │
        ▼
  publish_event("message_status_changed", payload)
        │  Redis PUBLISH  channel="aether:events"  db=7
        ▼
  GET /events/stream  (SSE endpoint, filtered by owner_id)
        │  Redis SUBSCRIBE → yields Server-Sent Events
        │  heartbeat every 30s to keep connection alive
        ▼
  useSSE() hook (EventSource)
        │
        ▼
  React state updates → UI refreshes without polling
```

Events include: `message_status_changed`, `new_channel`, `new_message`, `heartbeat`

---

## 9. Geolocation Pipeline (OSINT Extension)

```
  Scraper finds geo-tagged message or named location
        │
        ▼
  geo_worker dequeues job (Redis db=5)
        │
        ├─ Photon geocoder (text → lat/lon)
        ├─ GeoNames reverse geocode
        └─ ESRI ArcGIS Feature Services (optional POI overlay)
              (queried via ESRI REST API, results shown on map)
        │
        ▼
  Location node written to Neo4j
        │
        ▼
  Frontend map component renders markers + ESRI tile layers
```

---

## 10. AI Agent

```
  User types query in AgentChat  (or /visualize  /showmap  /summarize)
        │
        ▼
  POST /agent/chat  →  AgentService (backend)
        │
        ├── intent: location map?  ──► hardcoded Cypher fallback / LLM-filtered query
        │
        └── default path
              │
              ▼
        Text2CypherService
              │
              ├─ 1. Build prompt (schema + few-shot examples from feedback.json)
              │
              ├─ 2. POST to Modal LLM Service  ──────────────────────────────────┐
              │       (CypherAgent  →  httpx  →  Modal endpoint)                 │
              │                                                                   │
              │       ┌─────────────────────────────────────────────────────┐   │
              │       │  Modal  "aether-llm-service"                        │◄──┘
              │       │  GPU: L40S (48 GB VRAM)                             │
              │       │  Model: Codestral-22B-v0.1-Q4_K_M  (GGUF)          │
              │       │  Runtime: llama-cpp-python  (CUDA)                  │
              │       │  Weights: Modal Volume  "aether-llm-models"         │
              │       │  Task: NL → structured JSON query plan              │
              │       │  Output: { nodes, relationships, filters,           │
              │       │            return_fields, order_by, limit }         │
              │       └─────────────────────────────────────────────────────┘
              │
              ├─ 3. Validate JSON plan  (node IDs, relationship whitelist)
              │
              ├─ 4. Translate plan → Cypher  +  inject owner_id filter
              │
              ├─ 5. Execute Cypher against Neo4j
              │
              ├─ 6. Choose visualisation type  (graph / table / location_map)
              │
              └─ 7. Generate natural-language summary
                       │  (second call to Modal LLM Service, temperature 0.7)
                       ▼
              AgentResponse  { message, widget_type, widget_data }
                       │
                       ▼
              AgentChat UI  — renders graph / table / map widget
```

**Persona modes** (selectable in AgentChat):
`default` · `data_analyst` · `storyteller` · `programmer` · `investigator`

**Feedback loop:** thumb-up ratings save `(question, cypher)` pairs to `feedback.json`;
these are injected as few-shot examples in subsequent prompts to improve accuracy over time.

**Model choice rationale:** Codestral 22B is a code-specialist model with strong structured
output (JSON) and Cypher generation — better suited for this task than a general-purpose LLM.
Modal scales to zero when idle; an L40S spins up on demand within ~15 s.

---

## 11. Tech Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | React 18, Vite, TypeScript | SPA framework |
| **UI Library** | Mantine v7 | Component library |
| **Routing** | React Router v6 | Client-side routing |
| **Backend** | FastAPI, Python 3.11, Uvicorn | REST API + SSE |
| **Auth** | Keycloak 24 (OIDC/OAuth2) | Identity provider |
| **Graph DB** | Neo4j 5.18 | Knowledge graph |
| **Relational DB** | PostgreSQL 15 | Case files, reports, users |
| **Queue** | Redis 7 + RQ (Redis Queue) | Async job processing (8 queues) |
| **Scraping** | Telethon | Telegram MTProto client |
| **OCR** | EasyOCR | Image text extraction (multi-script) |
| **ASR** | OpenAI Whisper (base) + ffmpeg | Audio/video transcription |
| **Translation** | NLLB-200-Distilled-600M | Multilingual text translation |
| **NER** | GLiNER | Named entity recognition |
| **Emotion** | German-Emotions transformer | 20-label emotion classification |
| **Classification** | Custom transformer | Topic / threat classification |
| **Geocoding** | GeoNames index + ESRI ArcGIS | Location resolution + POI services |
| **GPU Inference** | Modal.com (serverless) | Translation, emotion, classification |
| **AI Agent** | Codestral 22B Q4 (self-hosted on Modal, llama-cpp-python, L40S GPU) | NL → Cypher query planner + OSINT reasoning assistant |
| **Containerisation** | Docker + Docker Compose | Service orchestration |
| **CI/CD** | GitHub Actions | Build, test, deploy |

---

## 12. Scalability Considerations

```
Current (single node)           Future (horizontal scale)
─────────────────────           ─────────────────────────
Redis (single instance)    →    Redis Cluster / Sentinel
Neo4j (single instance)    →    Neo4j Causal Cluster / AuraDB
Workers (1× each)          →    Multiple RQ worker replicas per queue
Backend (1× Uvicorn)       →    Load-balanced Uvicorn pool
Modal.com GPU workers      →    Already horizontally auto-scaled
```

**Key bottlenecks at scale:**
1. Neo4j write throughput during mass scrapes (batch writes mitigate this)
2. Whisper / EasyOCR are CPU-heavy — worker count drives throughput
3. Telegram rate limits per session — multiple sessions parallelize channel scraping

---

## 13. Security Notes

- All API endpoints protected by JWT validation (Keycloak)
- Multi-tenant data isolation enforced at the Neo4j query layer (`owner_id` filter)
- Media files served from a controlled `/media` path, not exposed directly
- Telegram sessions stored server-side only; credentials never sent to the browser
- Modal.com inference calls authenticated with `Modal-Key` / `Modal-Secret` headers
