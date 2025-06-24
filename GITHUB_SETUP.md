# GitHub Setup Guide for DeepCompanion

## 🎯 Quick Setup Steps

### Step 1: Create GitHub Repository
1. Go to [GitHub.com](https://github.com/new)
2. Repository name: `DeepCompanion`
3. Description: `Modern GUI chat application for local AI model interaction with Ollama`
4. Make it **Public** (recommended)
5. **DO NOT** check any initialization options (README, .gitignore, license)
6. Click **"Create repository"**

### Step 2: Connect Your Local Repository
Replace `YOUR_GITHUB_USERNAME` with your actual GitHub username:

```bash
./github-setup.sh YOUR_GITHUB_USERNAME
```

**Example:**
```bash
./github-setup.sh aryan
```

### Step 3: Verify Upload
After successful setup, your project will be available at:
`https://github.com/YOUR_GITHUB_USERNAME/DeepCompanion`

## 🔄 Daily Development Workflow

### Quick Sync (with timestamp)
```bash
./workflow.sh sync
```

### Commit with Custom Message
```bash
./workflow.sh commit "Added new feature"
```

### Pull Latest Changes
```bash
./workflow.sh pull
```

### Check Repository Status
```bash
./workflow.sh status
```

## ✨ What's Included in Your Repository

- ✅ Complete DeepCompanion application (`main.py`)
- ✅ Project documentation (`README.md`)
- ✅ Python dependencies (`requirements.txt`)
- ✅ Run script (`run.sh`)
- ✅ VS Code configuration (`.vscode/tasks.json`)
- ✅ GitHub Copilot instructions (`.github/copilot-instructions.md`)
- ✅ Git configuration (`.gitignore`)
- ✅ Development workflow tools

## 🚀 Features Ready for GitHub

**Three Specialized AI Modes:**
- 🤔 **Think Mode** - DeepSeek R1 1.5B for reasoning & analysis
- 💻 **Code Mode** - CodeGemma 2B for everyday coding (default)
- 🧠 **Advanced Mode** - CodeQwen 7B for complex programming

**Modern Interface:**
- Real-time streaming responses
- Visual status indicators and thinking animations
- Separate chat histories per mode
- Keyboard shortcuts (Ctrl+1/2/3)
- Code highlighting and tools

**Optimizations:**
- Designed for Intel i7-7600U with 8GB RAM
- Model-specific performance tuning
- Fast response times with CodeGemma 2B default

## 🔧 Troubleshooting

**"Repository not found" error:**
- Make sure you created the repository on GitHub first
- Double-check your GitHub username
- Ensure the repository name is exactly `DeepCompanion`

**Permission denied:**
- Check you're logged into the correct GitHub account
- Verify you have write access to the repository

**Push fails:**
- Try: `git push -u origin main`
- Check your internet connection
- Verify GitHub is accessible
