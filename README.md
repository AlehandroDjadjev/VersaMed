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
