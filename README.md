# Travel Planner API

A backend CRUD application built with **FastAPI**, **SQLAlchemy (async)**, and **SQLite** to manage travel projects, import desired places from the **Art Institute of Chicago API**, and attach notes.

## Features

- **Project Management**: Create, update, read, and delete travel projects.
- **Artwork Integration**: Search/validate and add places from the third-party Art Institute of Chicago API.
- **Interactive Checklists**: Travelers can check off visited places and write custom planning notes.
- **Completeness Tracker**: Automatically marks a project as `is_completed=True` when all associated places are visited (and resets to `False` if new unvisited places are added).
- **Deletion Safeguards**: Prevents deleting a project if any of its places are already visited.
- **Caching**: Integrates a robust in-memory TTL (Time-To-Live) cache to optimize API calls to the Art Institute, avoiding rate-limiting.
- **Security**: Basic Authentication protection on all API endpoints.
- **Robust Validation**: Enforces limits (1 to 10 places per project) and prevents duplicate place imports.
- **Docker Ready**: Standardized setup using Docker and Docker Compose.
- **Testing**: Over 95%+ test coverage using `pytest` and `pytest-asyncio` with an in-memory SQLite database.
- **Postman Collection**: Pre-configured JSON collection file for endpoint exploration.

---

## Tech Stack

- **Framework**: FastAPI (Python 3.12)
- **Database ORM**: SQLAlchemy 2.0 (asyncio) + aiosqlite (SQLite)
- **Validation**: Pydantic v2
- **Testing**: Pytest + Pytest-Asyncio
- **HTTP Client**: HTTPX

---

## Project Structure

```text
travel/
├── backend/
│   ├── app/
│   │   ├── auth.py         # Basic authentication dependencies
│   │   ├── config.py       # Configuration and Env variables (Pydantic Settings)
│   │   ├── crud.py         # Database operations and business rules
│   │   ├── database.py     # SQLAlchemy async database setup
│   │   ├── main.py         # FastAPI app initialization and routes
│   │   ├── models.py       # Database models (Project, Place)
│   │   ├── schemas.py      # Pydantic validation schemas
│   │   └── services.py     # External API client & TTL caching
│   ├── tests/
│   │   ├── conftest.py     # Test database configurations & API mocks
│   │   └── test_api.py     # API endpoint unit & integration tests
│   ├── Dockerfile          # Multistage container builder
│   └── requirements.txt    # Python dependencies
├── postman/
│   └── Travel_Planner.postman_collection.json  # Postman API Collection
├── docker-compose.yml      # Orchestrates local container deployment
└── README.md               # Setup and documentation
```

---

## Setup & Running Locally

### Prerequisites
- Python 3.10+
- SQLite3

### 1. Local Python Environment Setup
Navigate to the root directory and create a virtual environment:

```bash
# Navigate to the backend directory
cd backend

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create a `.env` file in the `backend/` directory or run with default environment values.
Supported configurations (defined in [config.py](file:///Users/premananda/travel/backend/app/config.py)):

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `sqlite+aiosqlite:///./travel_planner.db` | Async SQLAlchemy Database URL |
| `API_USERNAME` | `admin` | Username for Basic Auth |
| `API_PASSWORD` | `travelsecret` | Password for Basic Auth |
| `ART_API_BASE_URL` | `https://api.artic.edu/api/v1` | Art Institute API Base Endpoint |
| `CACHE_TTL_SECONDS`| `300` | TTL in seconds for cached API calls |

### 3. Run the Server
From the `backend/` directory, launch the server using Uvicorn:

```bash
# Run server
PYTHONPATH=. uvicorn app.main:app --reload
```
The server will start at **`http://localhost:8000`**.

### 4. Run Tests
Ensure the server is running correctly and passes the test suite:

```bash
# Run pytest with PYTHONPATH pointing to backend folder
PYTHONPATH=. pytest tests/
```

---

## Running with Docker (Recommended)

You can run the entire application using Docker Compose with zero local installations:

```bash
# From the root directory (where docker-compose.yml is located)
docker-compose up --build
```
This builds the image, starts the backend API service, exposes it at `http://localhost:8000`, and binds a named volume `db_data` to `/app/data` to persist your SQLite database.

---

## API Documentation

FastAPI auto-generates interactive API documentation:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Authentication
All routes under `/api/...` are protected using **HTTP Basic Authentication**.
Default credentials:
- **Username**: `admin`
- **Password**: `travelsecret`

*Note: You can authorize directly in the Swagger UI by clicking the "Authorize" button and inputting the credentials.*

### Summary of Endpoints

#### Projects:
- `POST /api/projects`: Create a project.
- `POST /api/projects/with-places`: Create a project with an array of imported place IDs.
- `GET /api/projects`: List projects (supports pagination `skip` & `limit` and filtering `is_completed`).
- `GET /api/projects/{project_id}`: Get project details (and its places).
- `PUT /api/projects/{project_id}`: Update project details (Name, Description, Start Date).
- `DELETE /api/projects/{project_id}`: Delete a project (fails if any place is visited).

#### Places:
- `POST /api/projects/{project_id}/places`: Add a place (validates existence, limit <= 10, duplicate check).
- `GET /api/projects/{project_id}/places`: List places for a project.
- `GET /api/projects/{project_id}/places/{place_id}`: Get place details.
- `PATCH /api/projects/{project_id}/places/{place_id}`: Update place notes / toggle `is_visited` (updates completeness).
- `DELETE /api/projects/{project_id}/places/{place_id}`: Remove a place.

---

## Postman Collection

A complete Postman collection is supplied to test and explore the API.
File location: [Travel_Planner.postman_collection.json](file:///Users/premananda/travel/postman/Travel_Planner.postman_collection.json).

### How to use:
1. Open Postman.
2. Click **Import** and select `Travel_Planner.postman_collection.json`.
3. The collection is pre-configured with Basic Auth at the collection level using variables: `api_username` and `api_password`.
4. It sets a default `base_url` variable to `http://localhost:8000`. You can configure these in the collection's "Variables" tab.
