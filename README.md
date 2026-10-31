# Dave University — Academic Management Portal

A full-stack institutional school portal engineered for universities, colleges, and polytechnics to manage students, academic faculties, course registries, and continuous assessment examinations.

> Built for SIWES (Students Industrial Work Experience Scheme) evaluation.

---

## 🏛️ System Features & Architectural Highlights

### Multi-Role RBAC (Role-Based Access Control)
- **Students**: Enrolment records, profile information, real-time semester result cards, download official transcript records (CSV).
- **Lecturers**: Course management, student assessment grading (40% continuous assessment + 60% exam), real-time grade computing, class group allocations.
- **Administrators**: University stats dashboard, dynamic classroom creation & assignment, staff provisioning, and student class enrollment.

### Robust Backend & Security Architecture
- **Expiring Token Authentication**: Secure token auth with configurable TTL (`API_TOKEN_TTL_SECONDS`) and auto-revocation upon logout/password changes.
- **HMAC OTP Password Recovery**: Multi-stage 6-digit OTP verification using salted SHA-256 digests (`account_digest` & `code_digest`) with anti-timing attacks (`constant_time_compare`) and 5-attempt rate lockouts.
- **Tiered Throttling**: 5 separate rate-limit scopes (login, registration, reset requests, reset confirmations, and email-hashed request throttles).
- **Database Integrity**: Dual-level validation utilizing Python model validators alongside database-level constraints (`CheckConstraint` and `UniqueConstraint`).

### Modern shadcn/ui Inspired Frontend
- **Tailwind CSS & shadcn/ui Design System**: Accessible UI primitives (Buttons, Inputs, Selects, Cards, Badges, Modals, Tables, Skeletons) styled with university institutional colors (Navy, Burgundy, Gold, Cream).
- **Responsive Mobile & Desktop Workspaces**: Interactive sidebar navigation, modal dialogs, search and filter toolbars, grade distribution previews, and zero-flicker transitions.

---

## 🛠️ Tech Stack

- **Backend**: Python 3, Django 6.1, Django REST Framework 3.18, WhiteNoise, Gunicorn
- **Frontend**: Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS, Lucide React, Radix UI Primitives
- **Databases**: SQLite (Development) / PostgreSQL (Production ready via `dj-database-url`)
- **Deployment**: Render (`render.yaml`) & Vercel (`school-frontend`)

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ and npm

### 2. Backend Setup (Django API)
```bash
# Clone the repository and enter directory
cd "school api"

# Activate virtual environment
# Windows:
.\env\Scripts\activate
# Linux/macOS:
source env/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create administrator account
python manage.py createsu
# or
python manage.py ensure_admin

# Run test suite
python manage.py test

# Start API server
python manage.py runserver
```
The Django REST API runs on `http://127.0.0.1:8000/`.

### 3. Frontend Setup (Next.js & shadcn/ui)
```bash
# Move to frontend folder
cd frontend

# Install packages
npm install

# Run type checks and build
npm run typecheck
npm run build

# Start frontend in development
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 🧪 Testing

The repository contains end-to-end integration tests covering:
- Authentication & Session expiry
- Role restrictions & permission boundaries
- OTP password recovery workflows & brute-force limits
- Grade calculations and check constraints

```bash
python manage.py test
```
