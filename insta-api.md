Bro, **now I completely understand the strategy.** 🔥

You’re not just building random demo projects. You’re creating a **public engineering portfolio that is directly mapped to real Upwork jobs**.

The goal is:

> **Client posts a job → you identify the underlying product → you build a credible version → push it publicly to GitHub → document it professionally → attach/reference it in your Upwork profile/proposals → repeat.**

Over time, your GitHub becomes evidence that says **“I don't just claim I can build this. Here is one I already built.”**

For this particular job, I would turn it into a proper product rather than a tiny `/verify` endpoint.

# 🚀 Product: InstaVerify API

**A self-hosted Instagram account verification and public-profile intelligence API with official Meta API support and a controlled public-web fallback.**

The product should solve a broader problem:

> Give websites and applications a simple API for determining whether an Instagram username exists and, where legally/technically available, retrieving publicly available account information such as account type and follower count.

The key differentiator is that the system **doesn't pretend Meta's API can access every Instagram account.**

Instead, it intelligently determines what can be verified.

---

# 1. The actual product

Imagine a company has a website where users submit their Instagram username.

They want to know:

```text
Instagram username:
[ @exampleuser ]

             VERIFY
```

Your API handles everything behind that button.

The application sends:

```http
GET /api/v1/verify/exampleuser
```

And gets something like:

```json
{
  "username": "exampleuser",
  "exists": true,
  "account_type": "professional",
  "followers": 15420,
  "source": "meta",
  "confidence": "high"
}
```

Or:

```json
{
  "username": "exampleuser",
  "exists": true,
  "account_type": "personal",
  "followers": null,
  "source": "public_web",
  "confidence": "medium"
}
```

Or:

```json
{
  "username": "doesnotexist",
  "exists": false,
  "account_type": null,
  "followers": null,
  "source": "public_web",
  "confidence": "high"
}
```

That is the core.

But we can make the product significantly better.

---

# 2. Product architecture

I'd build it like this:

```text
                    ┌──────────────────────┐
                    │     Client Website   │
                    │  Mobile App / SaaS   │
                    └──────────┬───────────┘
                               │
                               │ HTTPS
                               ▼
                 ┌───────────────────────────┐
                 │       InstaVerify API     │
                 │          FastAPI           │
                 └────────────┬──────────────┘
                              │
                    Verification Engine
                              │
              ┌───────────────┼────────────────┐
              │               │                │
              ▼               ▼                ▼
       ┌────────────┐  ┌──────────────┐  ┌─────────────┐
       │ Meta API   │  │ Public Web   │  │ Validation  │
       │ Provider   │  │ Provider     │  │ / Rules     │
       └────────────┘  └──────────────┘  └─────────────┘
              │               │
              └───────────────┼────────────────┘
                              ▼
                     Normalized Result
                              │
                              ▼
                       JSON API Response
```

The architecture should be **provider-based**.

That is important.

Because tomorrow Meta changes something, we don't want the entire application rewritten.

---

# 3. Provider system

We'll create an abstraction like:

```text
VerificationProvider
       │
       ├── MetaProvider
       │
       └── PublicWebProvider
```

Eventually we could add:

```text
       ├── BrowserProvider
       ├── CachedProvider
       └── FutureProvider
```

without changing the API itself.

For example:

```python
class InstagramProvider:
    async def verify(username):
        ...
```

Then:

```python
MetaProvider
PublicWebProvider
```

implement the interface.

This is proper software architecture rather than a one-off scraper.

---

# 4. Meta integration

This is the **official integration**.

The Meta provider handles accounts that Meta's API legitimately exposes.

For eligible professional accounts we can retrieve information such as:

```text
username
name
biography
followers_count
following_count
media_count
profile_picture
website
account type
```

depending on the permissions/API endpoint being used.

The important part is that we clearly document:

> Meta's official Instagram API does not provide unrestricted lookup of arbitrary personal Instagram accounts.

That becomes one of the strongest parts of the project.

We're demonstrating that we understand the API rather than blindly trying endpoints.

---

# 5. Public web verification

This is where we handle the broader requirement.

For an arbitrary username:

```text
@someuser
```

we can attempt to determine whether the public profile exists using a controlled browser/web adapter.

Something like:

```text
Instagram public profile
        ↓
Playwright
        ↓
Profile response/page
        ↓
Parse public information
        ↓
Normalized result
```

We should **not** try to bypass:

- authentication
- CAPTCHA
- private profiles
- access controls
- rate limits
- anti-bot mechanisms

If Instagram blocks the request, the API should honestly return:

```json
{
  "status": "unknown",
  "reason": "verification_unavailable"
}
```

rather than saying:

```json
{
  "exists": true
}
```

when we don't actually know.

That distinction makes the project much more professional.

---

# 6. Verification states

This is another thing I'd add.

Instead of only:

```text
true / false
```

we have:

```text
verified
not_found
unknown
restricted
unavailable
```

For example:

### Verified

```json
{
  "exists": true,
  "verification_status": "verified"
}
```

### Not found

```json
{
  "exists": false,
  "verification_status": "not_found"
}
```

### Unable to determine

```json
{
  "exists": null,
  "verification_status": "unknown"
}
```

This prevents misleading results.

---

# 7. Confidence system

We can also return:

```text
confidence:
high
medium
low
```

For example:

### Meta result

```json
{
  "confidence": "high",
  "source": "meta"
}
```

### Successfully parsed public profile

```json
{
  "confidence": "medium",
  "source": "public_web"
}
```

### Ambiguous result

```json
{
  "confidence": "low"
}
```

That's useful for real businesses.

---

# 8. Main API endpoints

I'd make the API a proper REST service.

### Health

```http
GET /health
```

Response:

```json
{
  "status": "ok"
}
```

---

### Verify account

```http
GET /api/v1/verify/{username}
```

Example:

```http
GET /api/v1/verify/natgeo
```

---

### Detailed verification

```http
GET /api/v1/accounts/{username}
```

Response:

```json
{
  "username": "natgeo",
  "exists": true,
  "account_type": "professional",
  "followers": 28300000,
  "following": 100,
  "posts": 9500,
  "is_private": false,
  "source": "meta",
  "confidence": "high"
}
```

Only return fields actually available.

---

### Batch verification

This would be a **very nice portfolio feature**.

```http
POST /api/v1/verify/batch
```

Request:

```json
{
  "usernames": [
    "user1",
    "user2",
    "user3"
  ]
}
```

Response:

```json
{
  "results": [
    {
      "username": "user1",
      "exists": true
    },
    {
      "username": "user2",
      "exists": false
    },
    {
      "username": "user3",
      "exists": null
    }
  ]
}
```

Then we can enforce:

```text
Maximum batch size: 50
```

or whatever limit we decide.

---

# 9. No database

This is actually one of the client's requirements.

So the initial product should be:

```text
FastAPI
+
Redis optional
+
Meta API
+
Playwright
+
No PostgreSQL
```

The API doesn't permanently store Instagram data.

Requests come in:

```text
request
   ↓
verification
   ↓
response
   ↓
discard
```

That makes deployment extremely simple.

---

# 10. Optional Redis

Although there is no database, I'd make Redis optional.

Why?

Suppose 500 users check:

```text
@nike
```

within five minutes.

We don't want:

```text
500 requests → Instagram
```

Instead:

```text
Request
   ↓
Redis cache
   ↓
Does result exist?
   │
   ├── YES → return result
   │
   └── NO
        ↓
      verify
        ↓
      cache
        ↓
      return
```

Example:

```text
Cache TTL = 10 minutes
```

This dramatically reduces unnecessary requests.

But **Redis isn't the source of truth** and isn't required to run the application.

---

# 11. Rate limiting

Very important.

We don't want someone discovering:

```text
https://api.yourdomain.com/api/v1/verify/
```

and hammering it thousands of times.

So:

```text
100 requests / minute / IP
```

for example.

For authenticated clients:

```text
1,000 requests / hour
```

depending on their API plan.

For the portfolio version, we can demonstrate configurable limits.

---

# 12. API authentication

I'd support API keys.

Example:

```http
X-API-Key: iv_live_xxxxxxxxx
```

Then clients can integrate it into their applications.

Example:

```javascript
fetch(
  "https://api.instaverify.dev/api/v1/verify/exampleuser",
  {
    headers: {
      "X-API-Key": "iv_live_xxxxx"
    }
  }
)
```

Again, no database is necessary for the basic architecture if API keys are environment-managed.

For a real SaaS product, we'd eventually add persistent API-key management.

---

# 13. Developer documentation

This is where your GitHub portfolio starts becoming **serious**.

We create:

```text
/docs
```

with:

```text
Getting Started
Authentication
Verify Account
Batch Verification
Meta Configuration
Public Web Provider
Rate Limits
Errors
Deployment
Docker
Security
Architecture
```

And FastAPI automatically gives us:

```text
/swagger
```

and:

```text
/redoc
```

So a client can literally open the deployed API and see interactive documentation.

---

# 14. Error system

Instead of random errors:

```text
500 Internal Server Error
```

we return structured errors.

Example:

```json
{
  "error": {
    "code": "VERIFICATION_UNAVAILABLE",
    "message": "Instagram verification could not be completed."
  }
}
```

Possible codes:

```text
INVALID_USERNAME
USERNAME_NOT_FOUND
META_AUTH_ERROR
META_UNAVAILABLE
RATE_LIMITED
VERIFICATION_UNAVAILABLE
PROVIDER_TIMEOUT
INVALID_API_KEY
BATCH_LIMIT_EXCEEDED
```

---

# 15. Username normalization

Users may enter:

```text
@john
```

or:

```text
john
```

or:

```text
https://instagram.com/john
```

or:

```text
https://www.instagram.com/john/
```

Our API normalizes everything:

```text
@john
       ↓
john
```

So the backend can accept:

```json
{
  "username": "@john"
}
```

or:

```json
{
  "username": "https://instagram.com/john/"
}
```

and resolve the username correctly.

That's a small feature but makes the API feel polished.

---

# 16. Security

We should also include:

```text
CORS
HTTPS
API key authentication
rate limiting
request timeout
input validation
maximum batch size
safe logging
secret management
```

And **never log Meta access tokens**.

---

# 17. Docker

One command:

```bash
docker compose up -d
```

and the whole thing starts.

Something like:

```text
Docker
 ├── FastAPI
 ├── Playwright
 └── Redis (optional)
```

This makes deployment to your VPS incredibly straightforward.

---

# 18. CI/CD

This is where your GitHub portfolio gets another level up.

We'll add:

```text
.github/
└── workflows/
    └── ci.yml
```

Pipeline:

```text
Push to GitHub
      ↓
Install dependencies
      ↓
Lint
      ↓
Type checking
      ↓
Unit tests
      ↓
Build Docker image
      ↓
PASS ✅
```

Then later:

```text
main branch
     ↓
GitHub Actions
     ↓
VPS
     ↓
Docker deployment
```

Now you aren't just showing code.

You're showing **production engineering**.

---

# 19. Test suite

We'll test:

### Username normalization

```text
@john → john
john → john
https://instagram.com/john → john
```

### Meta provider

Mock Meta API responses.

### Public provider

Mock profile responses.

### API

```text
200
400
401
404
429
500
```

### Batch

```text
valid batch
empty batch
too many usernames
duplicates
```

This gives us a respectable automated test suite.

---

# 20. Admin/debug endpoint

We don't need a dashboard yet.

But we can have:

```http
GET /health
GET /health/providers
```

Example:

```json
{
  "api": "healthy",
  "meta": "configured",
  "public_web": "available",
  "redis": "disabled"
}
```

Very useful during deployment.

---

# 21. Project UI

I actually recommend we build a **tiny frontend demo** too.

Not because the client asked for it.

Because you're building this for your portfolio.

Something like:

```text
┌───────────────────────────────────────────┐
│              InstaVerify                  │
│                                           │
│ Verify an Instagram account               │
│                                           │
│ ┌───────────────────────────────┐         │
│ │ @username                     │         │
│ └───────────────────────────────┘         │
│                                           │
│              [ Verify ]                   │
│                                           │
└───────────────────────────────────────────┘
```

Then:

```text
Account Found ✓

@username

Professional Account

15,420 followers

Source:
Meta Business Discovery

Confidence:
High
```

Or:

```text
Account Found ✓

@username

Account type:
Unknown

Follower count:
Unavailable

Source:
Public Web

Confidence:
Medium
```

This gives potential Upwork clients something they can **actually see and interact with**.

---

# 22. Project dashboard

We could eventually make the demo dashboard:

```text
InstaVerify
────────────────────────────────

Requests Today       1,284
Successful            1,173
Not Found               84
Unknown                 27

────────────────────────────────

Verification Sources

Meta                    61%
Public Web               39%

────────────────────────────────
```

But this should be **demo/observability data**, not permanent Instagram account storage.

---

# 23. Repository structure

The final public repository should look approximately like:

```text
instagram-account-verifier/
│
├── app/
│   ├── main.py
│   ├── config.py
│   ├── dependencies.py
│   │
│   ├── api/
│   │   ├── routes/
│   │   │   ├── verify.py
│   │   │   ├── batch.py
│   │   │   └── health.py
│   │   └── errors.py
│   │
│   ├── providers/
│   │   ├── base.py
│   │   ├── meta.py
│   │   ├── public_web.py
│   │   └── browser.py
│   │
│   ├── services/
│   │   ├── verifier.py
│   │   ├── normalizer.py
│   │   ├── cache.py
│   │   └── rate_limit.py
│   │
│   └── schemas/
│       ├── request.py
│       └── response.py
│
├── tests/
│   ├── test_api.py
│   ├── test_normalizer.py
│   ├── test_meta.py
│   └── test_public_web.py
│
├── frontend/
│
├── docs/
│   ├── architecture.md
│   ├── meta-api.md
│   └── deployment.md
│
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── pyproject.toml
├── LICENSE
└── README.md
```

That's a **real portfolio repository**.

---

# 24. README

The README should immediately communicate the interesting engineering problem.

Something like:

```text
# InstaVerify

Self-hosted Instagram account verification API
with official Meta API integration and public-web fallback.

Features

✓ Instagram username normalization
✓ Professional account verification
✓ Meta Business Discovery integration
✓ Public profile verification
✓ Follower count when officially available
✓ Batch verification
✓ API key authentication
✓ Rate limiting
✓ Optional Redis caching
✓ Docker deployment
✓ OpenAPI documentation
✓ Automated tests
✓ GitHub CI
✓ No permanent Instagram data storage
```

Then:

> **Important API limitation**

> Meta's official Instagram API does not provide unrestricted lookup or follower-count access for arbitrary personal Instagram accounts. InstaVerify therefore distinguishes between information available through Meta's official API and best-effort public-web verification.

That paragraph alone shows potential clients that we know what we're doing.

---

# 25. The Upwork angle

This is where your bigger strategy becomes 🔥.

Don't just put:

> "Instagram API project"

on GitHub.

We package it like a **case study**.

Your Upwork portfolio entry becomes:

### Instagram Account Verification API

**Problem**

A client needed an API capable of verifying Instagram usernames and retrieving follower counts while avoiding third-party Instagram data providers.

**Solution**

Built a self-hosted FastAPI service integrating Meta's official Instagram API for eligible professional accounts, with a controlled public-web verification fallback for broader public-profile checks.

**Features**

- Meta API integration
- Instagram username verification
- Professional account follower count
- Public-profile fallback
- Batch verification
- API authentication
- Rate limiting
- Docker deployment
- Automated tests
- OpenAPI documentation
- No permanent database storage

**Important finding**

Meta's official API does not support unrestricted lookup of arbitrary personal accounts, so the system explicitly reports unavailable data instead of fabricating results.

That is **much stronger than saying "I built an Instagram scraper."**

---

# 26. Your portfolio strategy

And bro, **this is the part I really like about your idea.**

We should create a system for ourselves.

Every interesting Upwork job becomes:

```text
UPWORK JOB
     ↓
Extract requirements
     ↓
Identify underlying product
     ↓
Build portfolio-grade MVP
     ↓
GitHub
     ↓
README + screenshots
     ↓
Demo deployment
     ↓
Case study
     ↓
Upwork portfolio
     ↓
Proposal
```

So eventually your GitHub could contain:

```text
IODev-NG/
│
├── instagram-account-verifier
├── browser-order-automation
├── vendor-order-tracker
├── meta-ai-assistant
├── universal-web-scraper
├── whatsapp-remittance-api
├── cbt-exam-platform
├── media-downloader
├── social-media-automation
├── document-processing-api
└── ...
```

Now imagine a client posts:

> "Need a developer to build an Instagram/Facebook AI assistant."

You don't just tell them:

> "I have experience with Meta APIs."

You can point to your **Meta automation repository**.

Client says:

> "Need browser automation with Google Sheets."

You have:

> **ProcureTrack**

Client says:

> "Need a scraping API."

You have:

> **Universal Web Scraper**

Client says:

> "Need Instagram verification."

You have:

> **InstaVerify**

That is the portfolio flywheel.

---

# 27. The important rule for our projects

I would make one rule going forward:

**We don't build fake portfolio projects.**

We take the actual client's requirement and build a **realistic, independently useful implementation**, but we clearly label it as:

> **Independent portfolio implementation inspired by a real-world requirement.**

We don't claim:

> "Built this for Company X"

if we didn't.

That's important for your reputation.

---

# 28. What "done" means

For InstaVerify, I wouldn't call it finished until we have:

```text
[ ] FastAPI backend
[ ] Meta provider
[ ] Public-web provider
[ ] Username normalization
[ ] Verification states
[ ] Confidence levels
[ ] Batch endpoint
[ ] API authentication
[ ] Rate limiting
[ ] Optional Redis cache
[ ] Error handling
[ ] Unit tests
[ ] Integration tests
[ ] Docker
[ ] Environment configuration
[ ] OpenAPI docs
[ ] CI/CD
[ ] Demo frontend
[ ] README
[ ] Architecture documentation
[ ] Screenshots
[ ] GitHub repository
[ ] Public deployment
[ ] Upwork case study
```

Then it's not just **"a project you coded."**

It's a **shippable software product**.

---

## And this is exactly how I'd approach your GitHub from now on

Your GitHub shouldn't become a graveyard of:

```text
todo-app
calculator
weather-app
test-project
test-project-2
```

😂

Instead, it becomes a **catalogue of solutions to actual business problems**.

And because you're specifically targeting Upwork, every project should answer one question:

> **"If an Upwork client posts this exact job tomorrow, can I show them something I've already built?"**

If we consistently do that, your portfolio starts working **before you even send the proposal**.

For **InstaVerify**, the next development phase should therefore be the full production implementation above—not just the small API we initially scaffolded.