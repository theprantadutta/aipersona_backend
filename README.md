# AI Persona Backend API

Production-ready FastAPI backend for AI Persona app with Firebase Auth, Google Sign-In, Gemini AI proxy, and Google Play subscriptions.

## 🎯 Features

- ✅ **Authentication**: Firebase Auth + Google Sign-In (like pinpoint)
- ✅ **AI Proxy**: Gemini API with rate limiting and usage tracking
- ✅ **Subscriptions**: Google Play verification (NO Stripe)
- ✅ **File Storage**: Backend file storage (NO Firebase Storage)
- ✅ **Push Notifications**: Firebase Cloud Messaging (FCM)
- ✅ **Database**: PostgreSQL with SQLAlchemy ORM
- ✅ **Migrations**: Alembic for database versioning
- ✅ **Docker**: Production-ready deployment

## 📦 Tech Stack

- **Framework**: FastAPI 0.115.5
- **Database**: PostgreSQL (pranta.vps.webdock.cloud/aipersona)
- **ORM**: SQLAlchemy 2.0.36
- **Auth**: Firebase Admin SDK 6.6.0 + JWT
- **AI**: Google Gemini (google-generativeai 0.8.3)
- **Payments**: Google Play In-App Purchases
- **Server**: Uvicorn

## 🚀 Quick Start

### 1. Clone and Navigate
```bash
cd G:\MyProjects\aipersona_backend
```

### 2. Create Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate  # Windows
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

### 6. Create Database
```bash
# Create 'aipersona' database on your PostgreSQL server
createdb -h pranta.vps.webdock.cloud -U postgres aipersona
```

### 7. Run Database Migrations
```bash
alembic revision --autogenerate -m "Initial tables"
alembic upgrade head
```

### 8. Run the Server
```bash
python run.py
```

Or with uvicorn directly:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 🌐 Access Points

Once running:
- **API**: http://localhost:8000
- **Swagger Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## 🔐 API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Email/password registration
- `POST /api/v1/auth/login` - Email/password login
- `POST /api/v1/auth/firebase` - Firebase token auth
- `POST /api/v1/auth/google` - Google Sign-In
- `POST /api/v1/auth/link-google` - Link Google account
- `POST /api/v1/auth/unlink-google` - Unlink Google
- `GET /api/v1/auth/me` - Current user info
- `GET /api/v1/auth/providers` - List auth providers

### Coming Soon
- Persona management
- Chat & AI proxy
- Google Play subscriptions
- Usage tracking
- Marketplace
- Files & uploads
- Admin endpoints

## 🐳 Docker Deployment

### Build and Run
```bash
docker-compose up -d
```

### View Logs
```bash
docker-compose logs -f backend
```

### Stop
```bash
docker-compose down
```

## 📊 Database Schema

### Users Table
- Email/password authentication
- Firebase UID + Google ID
- Subscription tier (free, premium_daily, premium_monthly, premium_yearly)
- Usage tracking relationship

### Free Tier Limits
- **Messages**: 10 per day
- **Personas**: 2 maximum
- **History**: 7 days retention

### Premium Tier
- **Unlimited** messages
- **Unlimited** personas
- **Unlimited** chat history
- All premium features unlocked

## 🔧 Development

### Create a New Migration
```bash
alembic revision --autogenerate -m "Add new table"
alembic upgrade head
```

### Run Tests
```bash
pytest
```

## 📝 Project Structure

```
aipersona_backend/
├── app/
│   ├── api/v1/           # API endpoints
│   │   ├── auth.py
│   │   └── auth_firebase.py
│   ├── core/             # Security & dependencies
│   ├── models/           # Database models
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   └── scheduler.py
├── alembic/              # Database migrations
├── uploads/              # File storage
├── .env                  # Environment variables
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── run.py
```

## 🔒 Security Notes

**NEVER commit:**
- `.env` file
- `firebase-admin-sdk.json`
- `google-play-service-account.json`

These are already in `.gitignore`.

## 📚 Next Steps

1. ✅ Authentication system (DONE)
2. ⏳ Implement remaining endpoints:
   - Persona management
   - Chat & AI proxy
   - Google Play subscriptions
   - Usage tracking
   - Marketplace
   - Files & uploads

## 🆘 Troubleshooting

**Database connection error?**
- Check `.env` credentials
- Verify database exists: `psql -h pranta.vps.webdock.cloud -U postgres -l`

**Module not found?**
```bash
pip install -r requirements.txt
```

**Firebase error?**
- Ensure `firebase-admin-sdk.json` exists in project root
- Check Firebase project ID in `.env`

---

**Backend Status**: ✅ Foundation complete, authentication working!
**Frontend**: Integration with Flutter app pending
