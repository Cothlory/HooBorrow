# HooBorrow

HooBorrow is a Django‑powered web application designed to let university users seamlessly borrow and manage sporting equipment. It supports two user roles—**Patrons** and **Librarians**—and leverages Google social authentication for signup/login.

---

## Table of Contents

1. [Features](#features)  
2. [Tech Stack](#tech-stack)  
3. [Getting Started](#getting-started)  
   - [Prerequisites](#prerequisites)  
   - [Installation](#installation)  
   - [Environment Variables](#environment-variables)  
   - [Database & Migrations](#database--migrations)  
   - [Static & Media Files](#static--media-files)  
   - [Run Development Server](#run-development-server)  
4. [Usage](#usage)  
5. [Running Tests](#running-tests)  
6. [Deployment](#deployment)  
7. [Contributing](#contributing)  
8. [License](#license)

---

## Features

- **Browse & Search** equipment by name, category, quantity, or condition  
- **Borrow Requests** for simple (bulk) and individual (complex) items  
- **Approval Workflow** for librarians to approve/reject borrow or collection access requests  
- **Collections**: group items into public or private collections with per‑user permissions  
- **Reviews & Ratings** for borrowed items  
- **Real‑time notifications**: unread message badge via AJAX  
- **Google OAuth2** signup/login via django‑allauth  
- **Role Management**: Promote Patrons to Librarians in the admin

## Tech Stack

- Python & Django 5  
- Django REST-style views & class-based views  
- django‑bootstrap5 & Bootstrap 5 for responsive UI  
- django‑allauth for social authentication (Google)  
- PostgreSQL (production) / SQLite (dev)  
- AWS S3 (via django‑storages) for media storage  
- Whitenoise for static file serving  
- CSP via django‑csp for security headers  

## Getting Started

### Prerequisites

- Python 3.10+
- Git 
- AWS S3 bucket (for production media)

### Installation

1. Clone the repo  
   ```bash
   git clone https://github.com/uva-cs3240-s25/project-a-15.git
   cd project-a-15
   ```
2. Create & activate a virtual environment  
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
3. Install Python dependencies  
   ```bash
   pip install -r requirements.txt
   ```

### Environment Variables

Create a `.env` file in the project root:

```env
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG=True
DATABASE_URL=postgres://user:pass@host:port/dbname  # optional
GOOGLE_CLIENT_ID=…
GOOGLE_CLIENT_SECRET=…
AWS_ACCESS_KEY_ID=…
AWS_SECRET_ACCESS_KEY=…
AWS_STORAGE_BUCKET_NAME=…
AWS_S3_REGION_NAME=…
```

### Database & Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### Static & Media Files

Collect static assets and configure media storage:

```bash
python manage.py collectstatic --noinput
```

- In development, media files go to `MEDIA_ROOT` (local)  
- In production, S3 handles media via django‑storages

### Run Development Server

```bash
python manage.py runserver
```

Visit `http://localhost:8000` and log in via Google.

## Usage

- **Home** page: browse available items  
- **Register** / **Login**: via Google popup  
- **Patrons**: request borrows, write reviews, view messages  
- **Librarians**: review/approve requests, manage inventory & collections  
- **Admin site**: `/admin/` for advanced user & site configuration

## Running Tests

```bash
python manage.py test
```

Unit tests cover models, views, and the borrow/return workflow.

## Deployment

A typical Heroku deployment uses:

- `Procfile` with `web: gunicorn HooBorrow.wsgi`  
- `requirements.txt` pinned  
- Heroku config vars for environment variables  
- AWS S3 bucket for media  
- Whitenoise for static files  

Refer to `django-heroku` docs for further configuration.

## Contributing

1. Fork the repository  
2. Create a feature branch  
3. Open a pull request with a clear description  
4. Ensure tests pass and add new tests for your changes  

Please follow the existing code style and write meaningful commit messages.

## License

This project is released under the [MIT License](LICENSE).

## Github Classroom
[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/hLqvXyMi)
