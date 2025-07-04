# Morph Server

A high-performance Starlette web server that integrates Claude Code SDK with GitHub for automated code generation and modification.

## Features

- **Fast Startup**: Optimized for minimal startup time using Starlette and uvicorn
- **JWT Authentication**: Secure endpoint access with JWT tokens
- **GitHub Integration**: Automated branch creation and file management
- **Claude Code SDK**: AI-powered code generation and modification
- **Git Patch Generation**: Tracks all file changes and generates patches
- **Callback Support**: Optional async callbacks for result delivery
- **Morph Cloud Ready**: Built-in support for Morph Cloud deployment

## Quick Start

```bash
# Run directly with uv (installs dependencies automatically)
uv run morph_server.py

# Or run directly from GitHub (replace with your repo URL)
curl -s https://raw.githubusercontent.com/eliseygusev/morph-server/main/morph_server.py | uv run -

# Or download first
curl -O https://raw.githubusercontent.com/eliseygusev/morph-server/main/morph_server.py
uv run morph_server.py
```

## Usage

### Local Development

```bash
# Run the server (uv handles all dependencies)
uv run morph_server.py

# With environment variables
PORT=8080 uv run morph_server.py
```

### Morph Cloud Deployment

See `MORPH_DEPLOYMENT.md` for detailed deployment instructions.

## API Endpoints

### Health Check
```
GET /health
```
No authentication required. Returns server status.

### Process Claude Request
```
POST /process
Authorization: Bearer <jwt-token>
Content-Type: application/json

{
  "access_token": "github-access-token",
  "repo_name": "owner/repo",
  "branch_name": "feature/new-feature",
  "prompt": "Add a new function to calculate fibonacci numbers",
  "callback_url": "https://your-server.com/callback"
}
```

#### Response
```json
{
  "status": "success",
  "branch_name": "feature/new-feature",
  "patch": "--- a/file.py\n+++ b/file.py\n...",
  "changed_files": {
    "added": {"new_file.py": "content..."},
    "modified": {"existing_file.py": "new content..."},
    "deleted": {}
  },
  "claude_messages": [
    {"type": "text", "content": "I've added the fibonacci function..."}
  ]
}
```

## JWT Token Generation

Generate a JWT token for authentication:

```python
import jwt
import datetime

secret = "your-secret-jwt-key"
payload = {
    "sub": "user123",
    "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
}
token = jwt.encode(payload, secret, algorithm="HS256")
print(f"Bearer {token}")
```

## Environment Variables

- `JWT_SECRET_KEY`: Secret key for JWT verification
- `PORT`: Server port (default: 8000)

## Architecture

1. **Authentication Layer**: JWT-based authentication middleware
2. **GitHub Integration**: PyGithub for repository operations
3. **Claude Processing**: Temporary workspace creation for Claude Code SDK
4. **Change Tracking**: Monitors all file modifications
5. **Patch Generation**: Creates unified diff patches

## Performance Optimizations

- Minimal dependencies for fast startup
- Async/await throughout for non-blocking operations
- Efficient file tracking with in-memory state
- Streaming responses where applicable

## Security

- JWT authentication required for `/process` endpoint
- GitHub access tokens never stored
- Temporary directories cleaned up automatically
- CORS enabled for cross-origin requests