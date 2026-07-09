# Equipment Reservation System

A simple Django web app for organizations that share equipment — cameras, projectors, lab devices, laptops — and need a central place to reserve, approve, and track loans.

## Features

- **Catalog** of equipment with categories, total stock, and per-item image
- **Live availability** count on every listing and detail page
- **Reservations** with date range, quantity, and purpose
- **Admin workflow**: pending → approved → checked out → returned
- **Race-condition guard** — re-checks free units at approval time
- **Borrowing history** per user and per equipment
- **Borrowers can cancel** their own pending or approved requests
- **Monthly calendar view** of all active reservations, filterable by equipment
- **REST API** at `/api/` for programmatic access (session or basic auth, browsable in dev)
- **Overdue report** via `manage.py mark_overdue` — lists reservations checked out past their end date (does not auto-flip status; status is computed from `is_overdue`)

## Stack

- Python 3.10+ (tested on 3.14)
- Django 6.x
- SQLite (file-based, zero-config)
- Server-rendered HTML + a single hand-rolled stylesheet — no JS framework, no Bootstrap

## Quickstart

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Apply database migrations
python manage.py migrate

# 3. Seed an admin user + demo data
python manage.py seed_data

# 4. Run the dev server
python manage.py runserver
```

Then open <http://127.0.0.1:8000/> in your browser.

## Default credentials

After `seed_data`:

| User    | Password    | Role  | Department |
|---------|-------------|-------|------------|
| `admin` | `admin12345` | superuser + is_admin | Operations |
| `alice` | `demo12345`  | user   | Media Lab  |
| `bob`   | `demo12345`  | user   | Biology    |
| `carol` | `demo12345`  | user   | IT Support |

> **Change the admin password before deploying anywhere public.** You can do this at `/admin/password_change/` or via `python manage.py changepassword admin`.

## Project layout

```
myproject/
├── manage.py
├── requirements.txt
├── config/                  Django project package
│   ├── settings.py
│   └── urls.py
├── accounts/                custom User, registration, profile, history
│   ├── models.py
│   ├── views.py
│   ├── forms.py
│   ├── decorators.py        @admin_required
│   └── management/commands/seed_data.py
├── equipment/               catalog (Category, Equipment)
│   ├── models.py
│   ├── views.py
│   ├── forms.py
│   └── templatetags/equipment_extras.py
├── reservations/            request / approve / check-out / return
│   ├── models.py
│   ├── views.py
│   ├── forms.py
│   ├── services.py          availability + conflict helpers
│   ├── api.py               DRF serializers + viewsets
│   ├── api_urls.py          /api/ routes
│   ├── tests_api.py         REST API tests
│   └── management/commands/mark_overdue.py
├── templates/               one tree, grouped by app
│   ├── base.html
│   ├── home.html
│   ├── registration/
│   ├── accounts/
│   ├── equipment/
│   └── reservations/        includes calendar.html
└── static/css/styles.css
```

## Where to look

- **Custom user model with `is_admin` flag:** `accounts/models.py`
- **Reservation state machine (status field + helpers):** `reservations/models.py`
- **Workflow views (approve, check out, return):** `reservations/views.py`
- **Availability calculation:** `reservations/services.py`
- **Admin decorator:** `accounts/decorators.py`

## URLs at a glance

| Path | Who | What |
|------|-----|------|
| `/`                             | anyone         | landing page |
| `/equipment/`                   | anyone         | catalog |
| `/equipment/<id>/`              | anyone         | item detail |
| `/accounts/register/`           | anyone         | sign up |
| `/accounts/login/`              | anyone         | log in |
| `/accounts/profile/`            | logged-in      | edit profile |
| `/accounts/history/`            | logged-in      | full borrowing history |
| `/reservations/`                | logged-in      | my reservations (pending / active / past) |
| `/reservations/request/<id>/`   | logged-in      | submit a reservation request |
| `/reservations/<id>/`           | owner or admin | single reservation view |
| `/reservations/manage/`         | admin          | pending requests queue |
| `/reservations/calendar/`       | admin          | monthly calendar of all reservations |
| `/reservations/<id>/approve/`   | admin          | approve request (POST) |
| `/reservations/<id>/reject/`    | admin          | reject request (POST) |
| `/reservations/<id>/checkout/`  | admin          | mark checked out (POST) |
| `/reservations/<id>/mark-returned/` | admin      | mark returned (POST) |
| `/api/`                         | authenticated  | REST API root (browsable in dev) |
| `/api/equipment/`               | authenticated  | list / filter equipment |
| `/api/reservations/`            | owner or admin | list reservations (own / all) |
| `/api/reservations/<id>/cancel/`| owner or admin | cancel a reservation (POST) |
| `/admin/`                       | superuser      | Django admin (backup) |

## Management commands

| Command | What it does |
|---------|--------------|
| `python manage.py seed_data`      | create admin/user accounts and demo equipment |
| `python manage.py mark_overdue`   | list reservations checked out past their end date (read-only) |
| `python manage.py changepassword <user>` | change a user's password |

Schedule `mark_overdue` from cron if you want a periodic report — it does not mutate state.

## Out of scope (deliberately not built)

Email notifications · password reset · image upload by users · overdue auto-detection (status is computed on read, not auto-flipped) · multi-organization · automated tests beyond `reservations/tests_api.py` (other `tests.py` files are empty stubs) · reports/analytics · i18n · Docker · production deployment.

## License

MIT (or whatever your organization prefers — adjust as needed).
