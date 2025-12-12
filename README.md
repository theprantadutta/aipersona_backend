# AI Persona Backend API

Production-ready FastAPI backend for AI Persona app with Firebase Auth, Google Sign-In, Gemini AI integration, and comprehensive persona management.

## Features

- **Authentication**: Firebase Auth + Google Sign-In with JWT tokens
- **AI Integration**: Gemini API proxy with rate limiting and usage tracking
- **Persona Management**: Full CRUD for personas with cloning support
- **Social Features**: Like system, favorites, user blocking, content reporting
- **Usage Analytics**: Comprehensive usage tracking with daily/monthly analytics
- **Subscriptions**: Tiered subscription system (Free, Basic, Premium, Pro)
- **File Storage**: Backend file storage with FileRunner integration
- **Activity Tracking**: User activity logging and feed
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Migrations**: Alembic for database versioning
- **Security**: Global exception handler with production-safe error messages
- **Background Tasks**: APScheduler for scheduled jobs (daily resets, cleanup)

## Tech Stack

- **Framework**: FastAPI 0.115.5
- **Database**: PostgreSQL with SQLAlchemy 2.0.36
- **Auth**: Firebase Admin SDK 6.6.0 + JWT (PyJWT)
- **AI**: Google Gemini (google-generativeai 0.8.3)
- **Validation**: Pydantic 2.x
- **Server**: Uvicorn with auto-reload support
- **Rate Limiting**: SlowAPI

## Quick Start

### 1. Clone and Navigate
```bash
cd aipersona_backend
```

### 2. Create Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables
Copy `.env.example` to `.env` and fill in your credentials:
```bash
cp .env.example .env
```

**Required variables:**
- `DATABASE_HOST`, `DATABASE_NAME`, `DATABASE_USERNAME`, `DATABASE_PASSWORD`
- `JWT_SECRET_KEY` (generate a strong random key)
- `FIREBASE_PROJECT_ID`, `GOOGLE_WEB_CLIENT_ID`
- `GEMINI_API_KEY`
- `ADMIN_EMAIL`, `ADMIN_PASSWORD`

### 5. Add Firebase Credentials
Download `firebase-admin-sdk.json` from Firebase Console and place it in the project root.

### 6. Run Database Migrations
```bash
alembic upgrade head
```

### 7. Run the Server
```bash
python -m app.main

# Or with auto-reload disabled
python -m app.main --no-reload
```

## Access Points

Once running:
- **API**: http://localhost:8001
- **Swagger Docs**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc
- **Health Check**: http://localhost:8001/health

## API Endpoints

### Authentication (`/api/v1/auth`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/register` | Email/password registration |
| POST | `/login` | Email/password login |
| POST | `/firebase` | Firebase token auth |
| POST | `/google` | Google Sign-In |
| POST | `/link-google` | Link Google account |
| POST | `/unlink-google` | Unlink Google account |
| GET | `/me` | Current user info |
| GET | `/providers` | List auth providers |

### Personas (`/api/v1/personas`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List user's personas |
| POST | `/` | Create new persona |
| GET | `/trending` | Get trending personas |
| GET | `/public` | Get public personas |
| GET | `/search` | Search personas |
| GET | `/{id}` | Get persona by ID |
| PUT | `/{id}` | Update persona |
| DELETE | `/{id}` | Delete persona |
| POST | `/{id}/clone` | Clone a persona |

### Social (`/api/v1/social`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/personas/{id}/like` | Toggle like on persona |
| GET | `/personas/{id}/like` | Check if liked |
| GET | `/favorites` | Get user's favorites (liked personas) |
| POST | `/users/{id}/block` | Block a user |
| DELETE | `/users/{id}/block` | Unblock a user |
| GET | `/blocked-users` | List blocked users |
| POST | `/report` | Report content |
| GET | `/activity-feed` | Get user's activity feed |

### Usage (`/api/v1/usage`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/current` | Get current usage stats |
| GET | `/history` | Get usage history (date range) |
| GET | `/analytics` | Get usage analytics with trends |
| POST | `/export` | Export usage data (JSON/CSV) |

### Chat (`/api/v1/chat`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/sessions` | List chat sessions |
| POST | `/sessions` | Create new session |
| GET | `/sessions/{id}` | Get session details |
| DELETE | `/sessions/{id}` | Delete session |
| GET | `/sessions/{id}/messages` | Get session messages |
| POST | `/sessions/{id}/messages` | Send message (AI response) |

## Database Schema

### Core Tables
- **users** - User accounts with subscription info
- **personas** - AI persona definitions
- **chat_sessions** - Conversation sessions
- **chat_messages** - Individual messages
- **usage_tracking** - Per-user usage metrics

### Social Tables
- **persona_likes** - Persona likes (also serves as favorites)
- **user_follows** - User follow relationships
- **user_blocks** - Blocked users
- **content_reports** - Reported content
- **user_activities** - Activity feed entries

## Subscription Tiers

| Feature | Free | Basic | Premium | Pro |
|---------|------|-------|---------|-----|
| Messages/day | 25 | 200 | 1,000 | Unlimited |
| Personas | 3 | 15 | 50 | Unlimited |
| Storage | 50MB | 500MB | 2GB | 10GB |
| Chat History | 3 days | 30 days | 90 days | Unlimited |

## Configuration

### Environment Variables

```env
# Server
HOST=0.0.0.0
PORT=8001
DEBUG=true

# Database
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=aipersona
DATABASE_USERNAME=postgres
DATABASE_PASSWORD=your_password

# Security
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# Firebase
FIREBASE_PROJECT_ID=your-project-id
FCM_CREDENTIALS_PATH=firebase-admin-sdk.json
GOOGLE_WEB_CLIENT_ID=your-client-id.apps.googleusercontent.com

# AI
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.0-flash-exp

# Admin
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=your-admin-password
```

### Security Features

- **Production Error Handling**: In production (`DEBUG=false`), detailed error messages are hidden from API responses. Errors are logged server-side with unique error IDs for tracking.
- **Rate Limiting**: API rate limiting via SlowAPI
- **JWT Authentication**: Secure token-based authentication
- **Input Validation**: Pydantic schema validation on all endpoints

## Development

### Create a New Migration
```bash
alembic revision --autogenerate -m "Description of changes"
alembic upgrade head
```

### Run with Auto-Reload (Default)
```bash
python -m app.main
```

### Run without Auto-Reload
```bash
python -m app.main --no-reload
```

### Run Tests
```bash
pytest
```

## Project Structure

```
aipersona_backend/
├── app/
│   ├── api/v1/              # API endpoints
│   │   ├── auth.py          # Authentication
│   │   ├── personas.py      # Persona management
│   │   ├── chat.py          # Chat & AI
│   │   ├── social.py        # Social features
│   │   └── usage.py         # Usage analytics
│   ├── core/                # Security & dependencies
│   ├── models/              # SQLAlchemy models
│   │   ├── user.py
│   │   ├── persona.py
│   │   ├── chat.py
│   │   └── social.py
│   ├── schemas/             # Pydantic schemas
│   ├── services/            # Business logic
│   │   ├── ai_service.py
│   │   ├── social_service.py
│   │   └── usage_service.py
│   ├── config.py            # Configuration
│   ├── database.py          # Database setup
│   ├── main.py              # Application entry
│   └── scheduler.py         # Background tasks
├── alembic/                 # Database migrations
├── uploads/                 # File storage
├── .env                     # Environment variables
├── requirements.txt
└── run.py                   # Alternate entry point
```

## Security Notes

**NEVER commit:**
- `.env` file
- `firebase-admin-sdk.json`
- `google-play-service-account.json`

These are already in `.gitignore`.

## Troubleshooting

**Database connection error?**
- Check `.env` credentials
- Verify database exists and is accessible

**Module not found?**
```bash
pip install -r requirements.txt
```

**Firebase error?**
- Ensure `firebase-admin-sdk.json` exists in project root
- Check Firebase project ID in `.env`

**500 errors in production?**
- Check server logs for the error ID
- Errors are logged with `[ERROR_ID: xxxxxxxx]` format

---

**Status**: Production-ready with full feature set
**Frontend**: [ai_persona](../ai_persona) Flutter app
