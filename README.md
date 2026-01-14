# PolyWrite Backend

A trust and semantic-governance layer for AI-assisted writing.

## Core Principles

1. **Identity**: Every action is tied to a user identity
2. **No Anonymous AI**: Anonymous users cannot access AI functionality  
3. **Proposals Only**: AI NEVER overwrites content - it proposes changes
4. **Semantic Validation**: Meaning is validated before any edit is allowed
5. **Rate Limiting**: Per-user rate limits protect the system
6. **Auditability**: All AI interactions are logged

## Quick Start

### 1. Set Up Supabase

1. Go to [Supabase](https://supabase.com) and create a new project
2. Go to **SQL Editor**
3. Copy the entire contents of `database/schema.sql`
4. Paste and run it in the SQL Editor

### 2. Configure Environment

```bash
# Copy the example env file
copy .env.example .env

# Edit .env with your Supabase credentials:
# - SUPABASE_URL (from Settings > API)
# - SUPABASE_ANON_KEY (from Settings > API)
# - SUPABASE_SERVICE_ROLE_KEY (from Settings > API)
# - JWT_SECRET (from Settings > API > JWT Settings)
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Server

```bash
uvicorn src.main:app --reload
```

### 5. Test the API

Open http://localhost:8000/docs for interactive API documentation.

## API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/` | GET | No | Health check |
| `/health` | GET | No | Detailed health status |
| `/auth/signup` | POST | No | Create new user |
| `/auth/signin` | POST | No | Sign in, get token |
| `/auth/me` | GET | Yes | Get current profile |
| `/auth/usage` | GET | Yes | Get rate limit usage |
| `/api/rewrite` | POST | Yes | Rewrite text |
| `/api/thresholds` | GET | Yes | Get semantic thresholds |
| `/api/audit-logs` | GET | Yes | View audit logs |

## Testing

### Using curl

```bash
# 1. Sign up
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'

# 2. Sign in (save the token)
curl -X POST http://localhost:8000/auth/signin \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'

# 3. Rewrite text (use token from step 2)
curl -X POST http://localhost:8000/api/rewrite \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"text": "The quick brown fox jumps over the lazy dog.", "intent": "rewrite"}'
```

### Using pytest

```bash
# Set test credentials
set TEST_EMAIL=test@example.com
set TEST_PASSWORD=password123

# Run tests
pytest tests/ -v
```

### Using the test script

```bash
python tests/test_api.py
```

## Project Structure

```
polywrite/
├── database/
│   └── schema.sql              # SQL to run in Supabase
├── src/
│   ├── main.py                 # FastAPI app
│   ├── config.py               # Environment config
│   ├── middleware/
│   │   └── auth.py             # JWT authentication
│   ├── services/
│   │   ├── profile.py          # User profiles
│   │   ├── rate_limiter.py     # Rate limiting
│   │   ├── ai_provider.py      # AI interface (OpenAI, Anthropic, Gemini, DeepSeek)
│   │   ├── embeddings.py       # Embeddings interface
│   │   ├── semantic.py         # Semantic validation (master validator)
│   │   ├── entity_validator.py # Entity preservation (numbers, dates, names)
│   │   ├── claim_validator.py  # Claim & citation detection
│   │   ├── tone_analyzer.py    # Voice & tone preservation
│   │   ├── document_scanner.py # Document-level intelligence scan
│   │   ├── decision.py         # Decision engine
│   │   └── audit.py            # Audit logging
│   ├── models/
│   │   └── schemas.py          # Pydantic models
│   └── routes/
│       ├── auth.py             # Auth endpoints
│       └── rewrite.py          # Rewrite endpoints
├── tests/
│   └── test_api.py             # API tests
├── requirements.txt
├── .env.example
└── README.md
```

## Features Implemented

| Feature | Status | Description |
|---------|--------|-------------|
| Highlighted-text editing only | ✅ | Selection-based editing (20-1800 chars) |
| AI proposal-only edits | ✅ | AI never auto-writes, only proposes |
| User accept/reject every change | ✅ | Proposals require explicit approval |
| Semantic Meaning Validator | ✅ | Embedding-based similarity scoring |
| Meaning/scope drift detection | ✅ | Threshold-based risk classification |
| Entity & invariant locking | ✅ | Numbers, dates, names preservation |
| Contradiction & polarity flip | ✅ | Negation reversal detection |
| Claim & fact detection | ✅ | Flags unsupported factual claims |
| Citation requirement flagging | ✅ | Detects uncited assertions |
| Decision logic (allow/warn/block) | ✅ | Three-tier decision engine |
| Document-level intelligence scan | ✅ | Structure, consistency, clarity |
| Voice & tone preservation | ✅ | Formality shift detection |
| Audit trail (immutable) | ✅ | All interactions logged |
| Identity, access, rate limiting | ✅ | Auth + abuse control |

## Phases Implemented

| Phase | Name | Description |
|-------|------|-------------|
| 1 | Identity | Profiles table, auto-creation |
| 2 | Auth Enforcement | JWT validation middleware |
| 3 | Authority | Role-based access (free/internal) |
| 4 | Rate Limiting | Per-user limits in database |
| 5 | Input Control | Validation, intent detection |
| 6 | AI Proposal | Multi-provider AI (OpenAI, Anthropic, Gemini, DeepSeek) |
| 7 | Semantic Validator | Embeddings + entity + polarity + claims + tone |
| 8 | Decision Engine | Enhanced with entity/polarity blocking |
| 9 | Audit Logging | Immutable logs |

## What's Next

1. **Frontend**: Build UI to consume the API
2. **Admin Tools**: Dashboard to manage users and view audits
3. **Chrome Extension**: In-browser text editing

## License

Private - All rights reserved.

