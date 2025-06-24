<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

# DeepCompanion Project Instructions

This is a Python GUI application called "DeepCompanion" that provides a modern chat interface for interacting with the Ollama DeepSeek R1 model.

## Project Context

- **Purpose**: GUI chat application for local AI model interaction
- **Main Technology**: Python with tkinter for GUI, requests for API communication
- **Target Model**: Ollama DeepSeek R1 1.5B model running locally
- **API Endpoint**: http://localhost:11434 (standard Ollama API)

## Code Style Guidelines

- Use clear, descriptive function and variable names
- Include comprehensive docstrings for all functions
- Handle errors gracefully with user-friendly messages
- Use threading for API calls to prevent GUI freezing
- Follow Python PEP 8 style guidelines
- Prefer composition over inheritance for GUI components

## Architecture Notes

- Main application class: `DeepCompanion`
- Asynchronous API communication using threading
- Custom styling with ttk themes for modern appearance
- Real-time chat interface with scrollable history
- Status indicators for connection and model availability

## Key Features to Maintain

- Real-time chat interface
- Connection status monitoring
- Model availability checking
- Keyboard shortcuts (Enter to send, Ctrl+Enter for newlines)
- Clear chat functionality
- Error handling and user feedback
- Modern, responsive UI design

When suggesting improvements or fixes, prioritize user experience, code maintainability, and robust error handling.
