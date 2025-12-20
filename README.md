# Companion AI Framework

A professional-grade AI companion system with modular architecture, conversation management, and extensible agent framework.

## Features

- **Modular Architecture**: Clean separation between frontend, backend, and AI components
- **Conversation Management**: Persistent chat history with SQLite database storage
- **Agent System**: Extensible agent framework for various AI tasks
- **Multiple LLM Providers**: Support for Groq, local models, and fallback responses
- **Professional UI**: Modern chat interface with streaming, agent transparency, and error handling
- **Security**: JWT authentication, API key protection, and permission management
- **Deployment Ready**: Docker, cloud deployment configurations included

## Quick Start

1. **Setup Environment**
   ```bash
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure API Keys**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Start the API Server**
   ```bash
   cd companion_baas/api
   python api_server.py
   ```

4. **Open the Chat Interface**
   Open `website/frontend/pages/chat.html` in your browser

## Architecture

### Backend (`companion_baas/`)
- **API Layer** (`api/`): FastAPI server with conversation management
- **Core AI** (`core/`): Neural processing and reasoning
- **Agents** (`agents/`): Specialized AI agents for different tasks
- **Knowledge** (`knowledge/`): Information retrieval and storage
- **Tools** (`tools/`): Utility functions and integrations

### Frontend (`website/frontend/`)
- **Components**: Reusable UI components
- **Services**: API communication and state management
- **Pages**: Chat interface and other views

## API Endpoints

- `POST /chat` - Send chat message
- `GET /conversations` - List conversations
- `GET /conversations/{id}` - Get conversation details
- `POST /conversations` - Create new conversation
- `DELETE /conversations/{id}` - Delete conversation

## Database

The system uses SQLite for conversation persistence:

- **Database File**: `companion_baas/companion.db`
- **Tables**: 
  - `conversations`: Conversation metadata
  - `messages`: Individual messages with timestamps
  - `users`: User accounts (future feature)
- **Features**: Automatic schema creation, conversation history, message threading

## Development

### Testing
```bash
cd companion_baas/api
pytest test_api.py
```

### Code Quality
- Use type hints
- Follow PEP 8
- Add tests for new features
- Document APIs with docstrings

## Deployment

### Local
```bash
# API Server
cd companion_baas/api
uvicorn api_server:app --host 0.0.0.0 --port 8000

# Frontend
# Open website/frontend/pages/chat.html
```

### Docker
```bash
docker-compose up
```

### Cloud
- **Vercel**: Frontend deployment
- **Railway**: API deployment
- **Fly.io**: Full stack deployment

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

[Add your license here]

## Professional Standards Met

✅ Modular architecture with clear separation of concerns
✅ Comprehensive testing with pytest
✅ API documentation and validation
✅ Security best practices (auth, API keys)
✅ Error handling and logging
✅ Conversation persistence and management
✅ Agent transparency in responses
✅ Streaming support (framework ready)
✅ Deployment configurations for multiple platforms
✅ Environment-based configuration
✅ Requirements management
✅ Git ignore and security practices