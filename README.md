# REDO AI Chat

A secure, production-ready chat application that provides conversational AI through the REDO AI DASH API. Features Firebase authentication, credit-based usage, and a ChatGPT-like interface.

## Features

- **ChatGPT-like Interface**: Clean, responsive UI with markdown support
- **Firebase Authentication**: Email/password authentication with email verification
- **Credit System**: 1 credit per message with atomic deduction
- **Admin Panel**: User management, credit administration, and usage analytics
- **Rate Limiting**: Configurable per-user and per-IP rate limits
- **Security**: Input sanitization, XSS protection, and secrets management
- **Real-time Updates**: Live credit counts and conversation history

## Quick Start

### Prerequisites

- Python 3.8+
- Firebase project with Authentication and Firestore enabled
- REDO AI API key

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Redo.AI
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Firebase**
   - Create a Firebase project at https://console.firebase.google.com
   - Enable Authentication (Email/Password) and Firestore
   - Download service account key and save as `firebase-config.json`
   - Or use environment variables (see `.env.example`)

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

5. **Run the application**
   ```bash
   python server.py
   ```

6. **Open your browser**
   Navigate to `http://localhost:5000`

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Firebase Configuration
FIREBASE_PROJECT_ID=your-firebase-project-id
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
FIREBASE_CLIENT_EMAIL=your-service-account-email

# REDO AI Provider
REDO_AI_API_KEY=your-redo-ai-api-key
REDO_AI_API_URL=https://api.redo.ai/v1/chat

# Application Settings
SECRET_KEY=your-flask-secret-key
MAX_MESSAGE_LENGTH=4096
RATE_LIMIT_MESSAGES_PER_30S=5
RATE_LIMIT_MESSAGES_PER_DAY=100

# Credit Policy
CREDIT_POLICY=refund_on_provider_failure
```

### Firebase Setup

1. **Authentication**: Enable Email/Password authentication
2. **Firestore**: Create database with the following collections:
   - `users` - User profiles and credit balances
   - `usage_logs` - System usage and admin action logs
   - `shared_chats` - Public conversation sharing (future feature)

### Admin Users

To make a user an admin:
1. User must first sign up normally
2. In Firestore, edit the user document and set `isAdmin: true`

## API Endpoints

### User Endpoints
- `POST /api/user/info` - Get user information and credits
- `POST /api/chat` - Send message to AI (consumes 1 credit)
- `POST /api/conversations` - Get user's conversation history
- `POST /api/user/rate-limit` - Get current rate limit status

### Admin Endpoints
- `POST /api/admin/users` - Search users
- `POST /api/admin/users/{uid}/credits` - Add/remove credits
- `POST /api/admin/logs` - Get usage logs
- `POST /api/admin/logs/export` - Export logs as CSV
- `GET /api/admin/health` - System health metrics

## Data Model

### Users Collection
```javascript
{
  email: "user@example.com",
  displayName: "User Name",
  credits: 10,
  isAdmin: false,
  emailVerified: true,
  createdAt: "2024-01-01T00:00:00Z"
}
```

### User Chats Subcollection
```javascript
{
  messageText: "Hello, AI!",
  role: "user", // or "assistant"
  timestamp: "2024-01-01T00:00:00Z",
  creditUsed: true,
  conversationId: "uuid-string",
  aiResponseMetadata: {
    providerStatus: "success",
    latencyMs: 250
  }
}
```

### Usage Logs Collection
```javascript
{
  uid: "user-id",
  endpoint: "chat",
  inputPreview: "Hello, AI!",
  resultStatus: "success",
  timestamp: "2024-01-01T00:00:00Z",
  creditsConsumed: 1,
  adminAction: false
}
```

## Credit Policy

The application supports two credit policies:

1. **`refund_on_provider_failure`** (default): Credits are refunded if the AI provider fails
2. **`consume_on_failure`**: Credits are consumed even if the provider fails

Set via `CREDIT_POLICY` environment variable.

## Rate Limiting

Default limits (configurable):
- 5 messages per 30 seconds per user
- 100 messages per day per user
- IP-based limits for additional protection

## Security Features

- **Input Sanitization**: Message length limits and control character filtering
- **XSS Protection**: HTML sanitization for markdown rendering
- **Content Security Policy**: Restrictive CSP headers
- **Firebase Security**: Server-side token verification
- **Rate Limiting**: Per-user and per-IP throttling
- **Audit Logging**: All admin actions and system events logged

## Deployment

### Production Deployment

1. **Set environment variables** in your production environment
2. **Use a production WSGI server**:
   ```bash
   gunicorn -w 4 -b 0.0.0.0:5000 server:app
   ```
3. **Set up reverse proxy** (nginx recommended)
4. **Enable HTTPS** (required for Firebase Auth)
5. **Configure Firebase security rules**

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "server:app"]
```

## Testing

### Manual Test Cases

1. **Sign Up Flow**
   - Create account → verify email → sign in → check credits = 0

2. **Chat Flow**
   - Admin adds credits → user sends message → credits decrement → AI responds

3. **Admin Flow**
   - Admin searches users → adds credits → views logs → exports CSV

4. **Error Handling**
   - Send message with 0 credits → insufficient credits error
   - Rapid message sending → rate limit error
   - Provider timeout → graceful error message

5. **Security Tests**
   - XSS in message → content sanitized
   - Long message → validation error
   - Invalid token → authentication error

### Concurrent Credit Test

Test atomic credit deduction:
```python
# Send 2 simultaneous requests with 1 credit available
# Expected: 1 succeeds, 1 fails with insufficient credits
```

## Monitoring

### System Health Metrics

Available in admin panel:
- Total requests (24h)
- Failed requests (24h)
- Provider failures (24h)
- Rate limited requests (24h)
- Credits consumed (24h)
- Success rate

### Log Analysis

Usage logs include:
- User actions and outcomes
- Admin operations with reasons
- Provider response times and failures
- Rate limiting events

## File Structure

```
├── server.py              # Main Flask application
├── auth_middleware.py     # Firebase authentication
├── chat_service.py        # AI provider integration
├── admin_service.py       # Admin functionality
├── database.py            # Firestore operations
├── rate_limiter.py        # Rate limiting logic
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── firebase-config.json.example  # Firebase config template
├── index.html            # Main application page
├── static/
│   ├── css/
│   │   └── styles.css    # Application styles
│   └── js/
│       ├── app.js        # Main application logic
│       ├── auth.js       # Authentication handling
│       ├── chat.js       # Chat functionality
│       └── admin.js      # Admin panel
└── README.md             # This file
```

## Troubleshooting

### Common Issues

1. **Firebase Connection Error**
   - Check `firebase-config.json` path and permissions
   - Verify environment variables are set correctly

2. **Provider API Error**
   - Check `REDO_AI_API_KEY` is valid
   - Verify `REDO_AI_API_URL` is correct

3. **Authentication Issues**
   - Ensure email verification is completed
   - Check Firebase project settings

4. **Rate Limiting**
   - Adjust limits in environment variables
   - For production, consider Redis for distributed rate limiting

### Debug Mode

Set `DEBUG=true` in environment for detailed error messages.

## License

This project is licensed under the MIT License. See LICENSE file for details.

## Support

For issues and feature requests, please create an issue in the repository.
