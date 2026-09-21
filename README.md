# CareStance Admin

This repository contains the extracted CareStance administration surface:

- the `/admin` FastAPI router and admin-only authentication dependency;
- user, counsellor, ticket, moderation, appointment, payment, and career management services;
- the admin dashboard and bulk-onboarding templates;
- the shared SQLAlchemy models and database adapter required by those services.

## Run locally

1. Create a virtual environment and install dependencies:

	```powershell
	python -m venv .venv
	.\.venv\Scripts\Activate.ps1
	pip install -r requirements.txt
	```

2. Set the same `DATABASE_URL`, `SECRET_KEY`, `ADMIN_EMAIL`, and Appwrite variables used by the CareStance application. Do not commit `.env` files or credentials.

3. Start the admin service:

	```powershell
	uvicorn admin_server:app --reload
	```

The dashboard is available at `http://127.0.0.1:8000/admin/`.

## Integration contract

The admin service intentionally uses the existing CareStance database schema and session cookie format. Deploy it behind the same parent domain or reverse proxy as CareStance so the `user_id` session cookie is available to this service. `SECRET_KEY` must match the main application, and `ADMIN_EMAIL` or the database `users.role = 'admin'` must identify administrators.

The main CareStance repository still owns the public product routes. Until traffic is switched, its existing `/admin` router remains in place so production is not interrupted. Switch the `/admin` proxy route only after this service has been deployed and smoke-tested against the production schema.

## Tests

```powershell
pytest -q
```