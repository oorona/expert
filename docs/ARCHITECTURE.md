# Technical Architecture

This document delves into the application architecture, how data flows between components, and the inner workings of the AI diagnostic engine.

## 1. Core Stack
*   **Frontend**: Next.js (TypeScript) utilizing Tailwind CSS v4 for UI elements.
*   **Backend**: FastAPI (Python 3.11) utilizing `uvicorn` and Server-Sent Events (SSE).
*   **Database**: PostgreSQL 18 with `pgvector` and `pg_textsearch` extensions.
*   **AI Service**: Google Gemini Base SDK (supporting Gemini 3 Pro reasoning, 2.5 Flash, etc.).

## 2. Component Networking and Data Flow
The infrastructure relies on Docker's internal networking for isolated and secure connectivity:
*   External users access the **Next.js Frontend** via a Traefik reverse proxy mapped to `expert.home.iktdts.com`.
*   When a user submits an error (or accesses an API-ingested error), the frontend creates a proxy payload and forwards it using HTTP basic authorization to the **FastAPI Backend**.
*   The Backend operates inside an isolated `intranet` network and is never exposed directly.

### Streaming Lifecycle (SSE)
Since heavy LLM inference operations (like finding semantic matches or forcing Gemini to diagnose a 5,000-line stack trace) are slow, the backend heavily relies on **Server-Sent Events (SSE)**.
Endpoints like `POST /diagnose` and `POST /experts` stream status packets (e.g., `event: progress`, `data: {"step": 2, "message": "Analyzing with Gemini..."}`) so the UI remains highly responsive before the final JSON payload drops.

## 3. Database Operations (Source of Truth)
PostgreSQL is the single, indisputable source of truth. All models, vectors, schemas, and prompts live here.

### SQLAlchemy & Alembic Migrations
The backend utilizes asynchronous SQLAlchemy 2.0. To prevent manual database administration, the application utilizes an init script via `Alembic`. 
Upon boot, the Backend checks the connected PostgreSQL instances. If the required schemas are missing, `Alembic` automatically runs sequential `upgrade` scripts (located in `backend/migrations/versions/`) to create all tables, indexes, and vector topologies.

## 4. Advanced Search Methodologies
The bedrock of this diagnostic engine is context retrieval. It uses a **Hybrid Search Pipeline** utilizing Reciprocal Rank Fusion:

*   **Semantic (`pgvector`)**: Stores `768-dimensional` embeddings for every error, note, and article. Uses cosine similarity for deep semantic meaning retrieval.
*   **Keyword (`pg_textsearch` BM25)**: Stores sparse token indices across three independent fields (`error_text`, `markdown_content`, and `notes`). Picks the best localized score using `LEAST()`.
*   **RRF Fusion**: The system executes both queries in parallel, normalizes their ranks, and scores the combined list so users get the best of lexical and semantic matches.

## 5. RAG (Retrieval-Augmented Generation)
Expert agents are intrinsically tied to specific domains (e.g., "Kubernetes Expert"). Each Expert has a dedicated Google Gemini "File Search Store".
When a user uploads a `.pdf` running manual to the platform, a background task uploads, parses, and indexes this file into the Expert's RAG corpus, allowing the LLM to pull specific page citations during diagnosis.
