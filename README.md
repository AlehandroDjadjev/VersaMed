# VersaMed

Starter monorepo with a Flutter frontend and Django backend.

## Structure

- `frontend/`: Flutter application scaffold
- `backend/`: Django API scaffold with `core`, `users`, and `api` apps

## Backend starter apps

- `apps.core`: shared base code like abstract timestamped models
- `apps.users`: custom user model from day one
- `apps.api`: API-facing routes like the health check endpoint

## Run locally

### Frontend

```powershell
cd frontend
flutter run
```

### Backend

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py migrate
python manage.py runserver
```

Health check: `GET /api/health/`

## Local HIS mock API

The backend includes a dev-only XML mock for the HIS test API. It does not connect
to `https://ptest-api.his.bg` and does not validate client certificates.

Run it on port `8001`:

```powershell
cd backend
python manage.py runserver 8001
```

Point the application at the local mock:

```env
HIS_API_BASE_URL=http://localhost:8001
```

Example request:

```bash
curl -X POST http://localhost:8001/v1/eimmunization/immunization/fetch \
  -H "Content-Type: application/xml" \
  -H "Authorization: Bearer mock-token" \
  -d "<Request><PatientId>123</PatientId></Request>"
```

Configuration:

```env
MOCK_AUTH_DISABLED=True
MOCK_LATENCY_MS=0
MOCK_FORCE_ERROR=False
MOCK_ERROR_STATUS=500
```

When `MOCK_AUTH_DISABLED=False`, requests to `/v1/...` must include an
`Authorization` header. The mock accepts bearer tokens but never verifies them.
Unknown `/v1/...` endpoints return an XML `501 MOCK_NOT_IMPLEMENTED` response.

This mock uses hardcoded fake data and simple XML responses. It does not validate
certificates, signatures, real authentication, real HIS schemas, or real
business rules. It is only for local development.
