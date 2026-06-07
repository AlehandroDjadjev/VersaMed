# VersaMed Backend

Django API with token authentication, role-based users, synthetic hospital
records, transactional onboarding, a local XML HIS simulator, and AI-assisted
medical scan analysis.

## Run

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Scan Interpretation API

Set these backend environment variables:

```env
OPENAI_API_KEY=your-key
OPENAI_MODEL=gpt-4.1-mini
```

Routes:

- `GET /api/scans`
- `GET /api/scans/<scan_id>`
- `GET /api/scans/<scan_id>/image`
- `POST /api/analyze-scan/<scan_id>`

The provider-specific implementation is isolated in the AI vision service, so
another model provider can replace it without changing the API routes.
The current scan list contains a small, diverse public TCIA/NBIA sample covering
chest/lung CT, breast MRI, kidney CT, liver CT, and prostate MRI. All displayed
scan images are converted from downloaded DICOM series; placeholder graphics are
not kept in the served scan catalog. NBIA imaging endpoints do not provide
patient-reported symptoms, so the UI marks symptoms and complaints as unavailable
instead of inventing them. AI output is preliminary and not a final diagnosis.

### Refresh scans from TCIA/NBIA

Install the Node downloader and Python DICOM conversion dependencies:

```powershell
cd backend
npm install
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Fetch and convert the configured diverse TCIA series:

```powershell
npm run fetch:tcia
```

Optional limits:

```powershell
$env:TCIA_SCAN_LIMIT=3
$env:TCIA_MAX_SERIES_BYTES=83886080
npm run fetch:tcia
```

The downloader queries `getSeries` across five public collections, selects one
bounded diagnostic series per body part, downloads each series with `getImage`,
extracts DICOM files under `backend/downloads/`, converts one representative
slice, saves PNGs under `backend/media/scans/`, and replaces
`backend/scans.json` with successfully converted TCIA cases only. It also removes
stale image files that are not part of the refreshed catalog. If TCIA is
unavailable or no conversion succeeds, the existing scan list is preserved.

Converted PNGs are stored under `backend/media/scans/` and served through the
scan image endpoint. The analyze endpoint loads the local PNG, converts it to a
data URL, and sends the image plus metadata to OpenAI. Client applications never
receive the OpenAI API key.

Set `CORS_ALLOWED_ORIGINS` to a comma-separated list of browser-client origins
when cross-origin access is required.

## Integration Flow

1. `POST /api/auth/signup/` with `username`, `email`, `password`, and `role`.
2. Save the returned token.
3. `POST /api/onboarding/sync/` with `personal_identifier` for a patient or
   `uin` for a doctor.
4. Send `Authorization: Token <token>` to authenticated endpoints.
5. `GET /api/dashboard/` returns persisted records plus mock-HIS status.

Available synthetic onboarding identifiers:

- Patients: `9001010000`, `8505120001`, `0203150002`
- Doctors: `1234567890`, `2345678901`

Auth endpoints:

- `POST /api/auth/signup/`
- `POST /api/auth/login/`
- `POST /api/auth/logout/`
- `GET /api/auth/me/`
- `POST /api/onboarding/sync/`
- `GET /api/dashboard/`

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
  -d "<Request><PatientId>9001010000</PatientId></Request>"
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

This mock uses synthetic data and XML responses. It does not validate
certificates, signatures, real authentication, real HIS schemas, or real
business rules. It is only for local development.

## Laboratory result uploads

Authenticated users can create laboratory results containing structured values,
private file attachments, or both:

```bash
curl -X POST http://localhost:8000/api/laboratory/results/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -F "patient_id=1" \
  -F "laboratory_request=lab-request-123" \
  -F "laboratory_name=Example Laboratory" \
  -F "collected_at=2026-06-07T08:00:00Z" \
  -F "reported_at=2026-06-07T10:00:00Z" \
  -F 'test_results=[{"test_name":"CRP","value":18,"unit":"mg/L","flag":"HIGH"}]' \
  -F "attachments[]=@lab-report.pdf"
```

Allowed attachment extensions are PDF, JPG, JPEG, PNG, and WEBP. DICOM `.dcm`
uploads can be enabled with `LAB_RESULT_ALLOW_DICOM=True`. Configure the maximum
file size in bytes with `LAB_RESULT_MAX_FILE_SIZE`.

Files are stored under `PRIVATE_MEDIA_ROOT`. Creation responses contain only
attachment metadata and never expose a file path or public URL. Result owners
and staff can download an attachment through:

```text
GET /api/laboratory/results/attachments/{attachment_id}/download/
```

Every new laboratory result must include a `patient_id`. Patients may submit
results for themselves, assigned doctors may submit results for their assigned
patients, and admins or staff may submit results for any patient. The result,
structured values, and attachment metadata are stored in the database. Uploaded
file bytes remain in private file storage rather than inside the database.

## Email notifications

Doctors, admins, and Django staff can send an email notification through:

```text
POST /api/notifications/email/
```

Configure Gmail SMTP in `backend/.env`:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=versamedvm@gmail.com
EMAIL_HOST_PASSWORD=<google_app_password>
DEFAULT_FROM_EMAIL=VersaMed <versamedvm@gmail.com>
```

Developer setup:

1. Enable Google 2-Step Verification for `versamedvm@gmail.com`.
2. Create a Google App Password.
3. Place the App Password in `EMAIL_HOST_PASSWORD`.
4. Restart the backend.

SMTP credentials must never be committed. Notification delivery status and
internal failures are stored in the database, while API failure responses remain
generic.
