#!/usr/bin/env python3
"""
Companion proto-3.0 (Deepthink) - A modern GUI for local and cloud AI models
A beautiful chat interface for interacting with local Ollama and cloud OpenRouter models
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import requests
import json
import threading
from datetime import datetime
import sys
import os
import re

# Import OpenRouter integration
try:
    from openrouter_client import OpenRouterClient, OpenRouterModelWrapper
    from config import OPENROUTER_CONFIG, APP_CONFIG, list_available_models
    CLOUD_MODELS_AVAILABLE = True
except ImportError:
    CLOUD_MODELS_AVAILABLE = False
    APP_CONFIG = {
        "title": "Companion v3.0 - Local AI Chat",
        "version": "3.0.0", 
        "description": "Modern GUI for local Ollama models",
        "author": "Companion Team"
    }
    print("⚠️ Cloud models not available - OpenRouter integration not found")

class Companion:
    def __init__(self, root):
        self.root = root
        self.root.title("Companion proto-3.0 (Deepthink) - AI Chat Interface")
        self.root.geometry("1000x750")
        self.root.minsize(700, 600)
        
        # Configure style
        self.setup_styles()
        
        # API configurations
        self.ollama_url = "http://localhost:11434"
        
        # Local Ollama models configuration
        self.local_models = {
            "chat": {
                "name": "llama3.2:3b",
                "display_name": "Llama 3.2 (Local)",
                "description": "Natural conversation and general assistance",
                "emoji": "💬",
                "provider": "ollama"
            },
            "conversation": {
                "name": "deepseek-r1:1.5b",
                "display_name": "DeepSeek R1 (Local)",
                "description": "AI thinking and reasoning mode",
                "emoji": "🤔",
                "provider": "ollama"
            },
            "code": {
                "name": "codegemma:2b", 
                "display_name": "CodeGemma 2B (Local)",
                "description": "Default coding assistant",
                "emoji": "💻",
                "provider": "ollama"
            },
            "code_advanced": {
                "name": "codeqwen:7b", 
                "display_name": "CodeQwen 7B (Local)",
                "description": "Advanced coding with detailed explanations",
                "emoji": "🧠",
                "provider": "ollama"
            }
        }
        
        # Cloud OpenRouter models configuration
        self.cloud_models = {}
        if CLOUD_MODELS_AVAILABLE:
            try:
                cloud_model_configs = list_available_models()
                for model_id, config in cloud_model_configs.items():
                    key = f"cloud_{config['category']}_{len(self.cloud_models)}"
                    self.cloud_models[key] = {
                        "name": model_id,
                        "display_name": config["display_name"],
                        "description": config["description"],
                        "emoji": config["emoji"],
                        "provider": "openrouter",
                        "category": config["category"]
                    }
            except Exception as e:
                print(f"⚠️ Error loading cloud models: {e}")
                self.cloud_models = {}
        
        # Combine all models
        self.models = {}
        self.models.update(self.local_models)
        self.models.update(self.cloud_models)
        
        # Current model selection - default to local chat
        self.current_model_key = "chat"
        self.model_name = self.models[self.current_model_key]["name"]
        self.current_provider = self.models[self.current_model_key]["provider"]
        
        # Chat history (separate for each model)
        self.chat_histories = {key: [] for key in self.models.keys()}
        self.chat_history = self.chat_histories[self.current_model_key]
        
        # Initialize model wrappers
        self.model_wrapper = ModelWrapper(self)
        if CLOUD_MODELS_AVAILABLE:
            try:
                self.openrouter_wrapper = OpenRouterModelWrapper(self)
            except Exception as e:
                print(f"⚠️ Error initializing OpenRouter wrapper: {e}")
                self.openrouter_wrapper = None
        else:
            self.openrouter_wrapper = None
        
        # Create GUI
        self.create_menu()
        self.create_widgets()
        
        # Check connections on startup
        self.check_ollama_connection()
        if CLOUD_MODELS_AVAILABLE:
            threading.Thread(target=self.check_openrouter_connection_async, daemon=True).start()
    
    def create_menu(self):
        """Create menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Clear Chat", command=self.clear_chat, accelerator="Ctrl+L")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Models menu
        models_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Modes", menu=models_menu)
        models_menu.add_command(label="💬 Chat Mode", command=lambda: self.switch_model("chat"), accelerator="Ctrl+1")
        models_menu.add_command(label="🤔 Think Mode", command=lambda: self.switch_model("conversation"), accelerator="Ctrl+2")
        models_menu.add_command(label="💻 Code Mode", command=lambda: self.switch_model("code"), accelerator="Ctrl+3")
        models_menu.add_command(label="🧠 Advanced Code", command=lambda: self.switch_model("code_advanced"), accelerator="Ctrl+4")
        models_menu.add_separator()
        models_menu.add_command(label="Check Model Status", command=self.check_model_availability)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Copy Last Code", command=self.copy_last_code_block)
        tools_menu.add_command(label="Format Input", command=self.format_input_text)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Keyboard Shortcuts", command=self.show_help, accelerator="F1")
        help_menu.add_command(label="About", command=self.show_about)
    
    def show_about(self):
        """Show about dialog"""
        about_text = f"""🤖 {APP_CONFIG['title']} v{APP_CONFIG['version']}

{APP_CONFIG['description']}

🚀 Dual Provider Support:
• 🏠 Local Models (Ollama): Fast, private, offline capable
• ☁️ Cloud Models (OpenRouter): Advanced capabilities, latest models

📱 Local Models Available:
💬 Chat Mode - Llama 3.2 3B for natural conversation
🤔 Think Mode - DeepSeek R1 1.5B for reasoning & analysis  
💻 Code Mode - CodeGemma 2B for everyday coding
🧠 Advanced Mode - CodeQwen 7B for complex programming

☁️ Cloud Models Available ({len(self.cloud_models)} models):
🧠 DeepSeek R1 - Advanced reasoning and step-by-step analysis
⚡ Gemini 2.5 Flash - Google's fast multimodal AI
🤖 GPT-4o - OpenAI's most advanced multimodal model
💻 Mistral Devstral - Specialized for code generation
🚀 GPT-4.1 - Enhanced GPT-4 with improved capabilities
🔍 Perplexity Sonar - Deep research with real-time web search

✨ Enhanced Features:
• 🔄 Seamless switching between local and cloud models
• 📊 Real-time response performance monitoring
• 🎯 Context-aware message preparation
• 🚀 Intelligent streaming with smooth output
• 💾 Separate chat histories per model
• ⌨️ Comprehensive keyboard shortcuts
• � Advanced error handling and recovery

🎨 Visual Indicators:
• Model-specific thinking animations
• Performance metrics and speed indicators
• Connection status for both providers
• Real-time token streaming

⌨️ Keyboard Shortcuts:
• Enter - Send message
• Ctrl+Enter - New line
• Ctrl+L - Clear chat
• Ctrl+1-4 - Switch local models
• F1 - Show help

Built with Python & tkinter
Powered by Ollama (local) + OpenRouter (cloud)
{APP_CONFIG['author']}"""
        
        messagebox.showinfo(f"About {APP_CONFIG['title']}", about_text)
    
    def setup_styles(self):
        """Configure modern Grok-inspired styles for the application"""
        style = ttk.Style()
        
        # Configure the theme
        style.theme_use('clam')
        
        # Grok-inspired color palette - dark theme with vibrant accents
        bg_color = "#0A0A0A"          # Deep black background
        card_bg = "#1A1A1A"          # Card/panel background
        fg_color = "#FFFFFF"          # Primary text (white)
        secondary_fg = "#A0A0A0"      # Secondary text (light gray)
        accent_color = "#00D9FF"      # Bright cyan accent (Grok's signature color)
        accent_hover = "#00B8D4"      # Darker cyan for hover
        success_color = "#00E676"     # Success green
        warning_color = "#FFB74D"     # Warning orange
        error_color = "#FF5252"       # Error red
        border_color = "#333333"      # Subtle borders
        
        # Title styling - larger, more prominent
        style.configure('Title.TLabel', 
                       background=bg_color, 
                       foreground=fg_color, 
                       font=('SF Pro Display', 24, 'bold'))
        
        # Subtitle for mode descriptions
        style.configure('Subtitle.TLabel', 
                       background=bg_color, 
                       foreground=secondary_fg, 
                       font=('SF Pro Text', 11))
        
        # Status labels
        style.configure('Status.TLabel', 
                       background=bg_color, 
                       foreground=secondary_fg, 
                       font=('SF Pro Text', 10))
        
        # Primary action button (Send)
        style.configure('Send.TButton', 
                       background=accent_color, 
                       foreground='white', 
                       font=('SF Pro Text', 11, 'bold'),
                       borderwidth=0,
                       focuscolor='none',
                       relief='flat')
        
        style.map('Send.TButton',
                 background=[('active', accent_hover),
                           ('pressed', '#0097A7')])
        
        # Model selection buttons - inactive state
        style.configure('Model.TButton', 
                       background=card_bg, 
                       foreground=secondary_fg, 
                       font=('SF Pro Text', 10, 'normal'),
                       borderwidth=1,
                       relief='flat',
                       focuscolor='none')
        
        style.map('Model.TButton',
                 background=[('active', '#2A2A2A'),
                           ('pressed', '#333333')],
                 foreground=[('active', fg_color)])
        
        # Active model button
        style.configure('ActiveModel.TButton', 
                       background=accent_color, 
                       foreground='white', 
                       font=('SF Pro Text', 10, 'bold'),
                       borderwidth=0,
                       relief='flat',
                       focuscolor='none')
        
        style.map('ActiveModel.TButton',
                 background=[('active', accent_hover),
                           ('pressed', '#0097A7')])
        
        # Cloud model buttons
        style.configure('Cloud.TButton', 
                       background='#1E1E3A', 
                       foreground='#E0E0FF', 
                       font=('SF Pro Text', 10, 'normal'),
                       borderwidth=1,
                       relief='flat',
                       focuscolor='none')
        
        style.map('Cloud.TButton',
                 background=[('active', '#2A2A4A'),
                           ('pressed', '#333366')],
                 foreground=[('active', '#FFFFFF')])
        
        # Clear button
        style.configure('Clear.TButton', 
                       background='#333333', 
                       foreground=fg_color, 
                       font=('SF Pro Text', 10),
                       borderwidth=0,
                       relief='flat',
                       focuscolor='none')
        
        style.map('Clear.TButton',
                 background=[('active', '#444444'),
                           ('pressed', '#555555')])
        
        # Notebook (tabs) styling
        style.configure('TNotebook', 
                       background=bg_color,
                       borderwidth=0,
                       tabmargins=[0, 5, 0, 0])
        
        style.configure('TNotebook.Tab', 
                       background=card_bg,
                       foreground=secondary_fg,
                       padding=[20, 10],
                       font=('SF Pro Text', 11, 'normal'),
                       borderwidth=0)
        
        style.map('TNotebook.Tab',
                 background=[('selected', accent_color),
                           ('active', '#2A2A2A')],
                 foreground=[('selected', 'white'),
                           ('active', fg_color)])
        
        # Frame styling
        style.configure('TFrame', background=bg_color)
        
        # Configure root background
        self.root.configure(bg=bg_color)
    
    def create_widgets(self):
        """Create and layout the modern Grok-inspired GUI widgets"""
        # Main container with padding
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=24)
        
        # Header section with modern typography
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 32))
        
        # Main title with Grok-style branding
        title_label = ttk.Label(header_frame, 
                               text="🚀 Companion", 
                               style='Title.TLabel')
        title_label.pack(anchor=tk.W)
        
        # Subtitle
        subtitle_label = ttk.Label(header_frame, 
                                 text="AI Chat Interface • Local & Cloud Models • Powered by Ollama & OpenRouter", 
                                 style='Subtitle.TLabel')
        subtitle_label.pack(anchor=tk.W, pady=(8, 0))
        
        # Provider tabs with modern card design
        provider_card = ttk.Frame(main_frame)
        provider_card.pack(fill=tk.X, pady=(0, 24))
        
        # Create notebook for local/cloud switching with modern styling
        self.provider_notebook = ttk.Notebook(provider_card)
        self.provider_notebook.pack(fill=tk.X)
        
        # Local models tab
        local_tab = ttk.Frame(self.provider_notebook)
        self.provider_notebook.add(local_tab, text="🏠 Local Models")
        
        # Local models grid with improved spacing
        local_container = ttk.Frame(local_tab)
        local_container.pack(fill=tk.X, pady=16)
        
        # Create a grid layout for local model buttons
        local_buttons_frame = ttk.Frame(local_container)
        local_buttons_frame.pack(anchor=tk.CENTER)
        
        # Chat mode button - redesigned
        self.chat_button = ttk.Button(
            local_buttons_frame,
            text="💬 Chat Mode\nLlama 3.2",
            command=lambda: self.switch_model("chat"),
            style='ActiveModel.TButton',
            width=16
        )
        self.chat_button.grid(row=0, column=0, padx=8, pady=8, sticky="ew")
        
        # Think mode button
        self.think_button = ttk.Button(
            local_buttons_frame,
            text="🤔 Think Mode\nDeepSeek R1",
            command=lambda: self.switch_model("conversation"),
            style='Model.TButton',
            width=16
        )
        self.think_button.grid(row=0, column=1, padx=8, pady=8, sticky="ew")
        
        # Code mode button
        self.code_button = ttk.Button(
            local_buttons_frame,
            text="💻 Code Mode\nCodeGemma",
            command=lambda: self.switch_model("code"),
            style='Model.TButton',
            width=16
        )
        self.code_button.grid(row=1, column=0, padx=8, pady=8, sticky="ew")
        
        # Advanced coding button
        self.advanced_button = ttk.Button(
            local_buttons_frame,
            text="🧠 Advanced\nCodeQwen",
            command=lambda: self.switch_model("code_advanced"),
            style='Model.TButton',
            width=16
        )
        self.advanced_button.grid(row=1, column=1, padx=8, pady=8, sticky="ew")
        
        # Cloud models tab
        if CLOUD_MODELS_AVAILABLE and self.cloud_models:
            cloud_tab = ttk.Frame(self.provider_notebook)
            self.provider_notebook.add(cloud_tab, text="☁️ Cloud Models")
            
            # Cloud models container with modern card layout
            cloud_container = ttk.Frame(cloud_tab)
            cloud_container.pack(fill=tk.X, pady=16)
            
            # Cloud models grid
            cloud_grid = ttk.Frame(cloud_container)
            cloud_grid.pack(anchor=tk.CENTER)
            
            # Create cloud model buttons in a responsive grid
            self.cloud_buttons = {}
            row, col = 0, 0
            max_cols = 3
            
            for model_key, model_info in self.cloud_models.items():
                btn_text = f"{model_info['emoji']} {model_info['display_name'].split()[0]}\n{model_info['category'].title()}"
                btn = ttk.Button(
                    cloud_grid,
                    text=btn_text,
                    command=lambda k=model_key: self.switch_model(k),
                    style='Cloud.TButton',
                    width=18
                )
                btn.grid(row=row, column=col, padx=8, pady=8, sticky="ew")
                self.cloud_buttons[model_key] = btn
                
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1
        
        # Status and info section with modern card design
        status_card = ttk.Frame(main_frame)
        status_card.pack(fill=tk.X, pady=(0, 24))
        
        # Current mode info with modern typography
        current_model = self.models[self.current_model_key]
        self.mode_info_frame = ttk.Frame(status_card)
        self.mode_info_frame.pack(fill=tk.X, pady=(0, 16))
        
        self.current_mode_label = ttk.Label(
            self.mode_info_frame, 
            text=f"Active: {current_model['emoji']} {current_model['display_name']}", 
            style='Status.TLabel',
            font=('SF Pro Text', 12, 'bold')
        )
        self.current_mode_label.pack(anchor=tk.W)
        
        self.mode_desc_label = ttk.Label(
            self.mode_info_frame, 
            text=current_model['description'], 
            style='Subtitle.TLabel'
        )
        self.mode_desc_label.pack(anchor=tk.W, pady=(4, 0))
        
        # Connection status with modern indicators
        connection_frame = ttk.Frame(status_card)
        connection_frame.pack(fill=tk.X)
        
        self.status_label = ttk.Label(connection_frame, 
                                     text="� Initializing connections...", 
                                     style='Status.TLabel')
        self.status_label.pack(side=tk.LEFT)
        
        # Model status indicators (redesigned)
        self.model_status_frame = ttk.Frame(connection_frame)
        self.model_status_frame.pack(side=tk.RIGHT)
        
        self.status_indicators = {}
        status_models = [("chat", "💬"), ("conversation", "🤔"), ("code", "💻"), ("code_advanced", "🧠")]
        
        for i, (model_key, emoji) in enumerate(status_models):
            indicator = ttk.Label(self.model_status_frame, 
                                text=f"{emoji} ⏳", 
                                style='Status.TLabel',
                                font=('SF Pro Text', 10))
            indicator.pack(side=tk.LEFT, padx=(12, 0))
            self.status_indicators[model_key] = indicator
        
        # Chat display with modern styling
        chat_frame = ttk.Frame(main_frame)
        chat_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 24))
        
        self.chat_display = scrolledtext.ScrolledText(
            chat_frame,
            wrap=tk.WORD,
            width=90,
            height=28,
            font=('SF Mono', 11),
            bg="#0A0A0A",           # Deep black background
            fg="#FFFFFF",           # White text
            insertbackground="#00D9FF",  # Cyan cursor
            selectbackground="#00D9FF",  # Cyan selection
            selectforeground="#000000",  # Black selected text
            state=tk.DISABLED,
            borderwidth=0,
            relief='flat',
            padx=20,
            pady=20
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)
        
        # Input section with modern design
        input_section = ttk.Frame(main_frame)
        input_section.pack(fill=tk.X)
        
        # Input container
        input_container = ttk.Frame(input_section)
        input_container.pack(fill=tk.X, pady=(0, 16))
        
        # Message input with modern styling
        self.message_entry = tk.Text(
            input_container,
            height=4,
            font=('SF Pro Text', 12),
            bg="#1A1A1A",           # Dark gray background
            fg="#FFFFFF",           # White text
            insertbackground="#00D9FF",  # Cyan cursor
            wrap=tk.WORD,
            borderwidth=0,
            relief='flat',
            padx=16,
            pady=12
        )
        self.message_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 16))
        
        # Button container
        button_container = ttk.Frame(input_container)
        button_container.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Send button with modern styling
        self.send_button = ttk.Button(
            button_container,
            text="Send ↗",
            command=self.send_message,
            style='Send.TButton',
            width=12
        )
        self.send_button.pack(fill=tk.X, pady=(0, 8))
        
        # Clear button
        clear_button = ttk.Button(
            button_container,
            text="Clear",
            command=self.clear_chat,
            style='Clear.TButton',
            width=12
        )
        clear_button.pack(fill=tk.X)
        
        # Footer with stats and shortcuts
        footer_frame = ttk.Frame(input_section)
        footer_frame.pack(fill=tk.X)
        
        # Character counter and shortcuts
        self.stats_label = ttk.Label(footer_frame, 
                                   text="0 characters • Press Enter to send • Ctrl+L to clear", 
                                   style='Status.TLabel')
        self.stats_label.pack(side=tk.LEFT)
        
        # Performance indicator
        self.perf_label = ttk.Label(footer_frame, text="", style='Status.TLabel')
        self.perf_label.pack(side=tk.RIGHT)
        
        # Bind events
        self.message_entry.bind('<Return>', self.on_enter_pressed)
        self.message_entry.bind('<Control-Return>', self.insert_newline)
        self.message_entry.bind('<KeyRelease>', self.on_text_change)
        
        # Keyboard shortcuts
        self.root.bind('<Control-1>', lambda e: self.switch_model("chat"))
        self.root.bind('<Control-2>', lambda e: self.switch_model("conversation"))
        self.root.bind('<Control-3>', lambda e: self.switch_model("code"))
        self.root.bind('<Control-4>', lambda e: self.switch_model("code_advanced"))
        self.root.bind('<Control-l>', lambda e: self.clear_chat())
        self.root.bind('<F1>', self.show_help)
        
        # Focus on message entry
        self.message_entry.focus()
        
    def update_status_icons(self):
        """Update status icons based on current model and state"""
        # Update performance label based on current model
        current_model = self.models[self.current_model_key]
        provider = current_model.get("provider", "ollama")
        
        if provider == "ollama":
            if self.current_model_key == "chat":
                self.perf_label.config(text="💬 Local Chat", foreground="#00E676")
            elif self.current_model_key == "conversation":
                self.perf_label.config(text="🤔 Local Think", foreground="#00D9FF")
            elif self.current_model_key == "code":
                self.perf_label.config(text="💻 Local Code", foreground="#FFB74D")
            elif self.current_model_key == "code_advanced":
                self.perf_label.config(text="🧠 Local Advanced", foreground="#BB86FC")
        else:
            self.perf_label.config(text="☁️ Cloud Model", foreground="#00D9FF")
    
    def set_thinking_state(self, is_thinking=False):
        """Update performance indicator to show AI processing state"""
        if is_thinking:
            self.perf_label.config(text="🤔 Processing...", foreground="#00D9FF")
        else:
            self.perf_label.config(text="", foreground="gray")
    
    def update_code_buttons_visibility(self):
        """Legacy function - code buttons are now integrated into the main UI"""
        pass
    
    def copy_last_code_block(self):
        """Copy the last code block from the chat to clipboard"""
        # Get all text from chat display
        self.chat_display.config(state=tk.NORMAL)
        chat_content = self.chat_display.get("1.0", tk.END)
        self.chat_display.config(state=tk.DISABLED)
        
        # Find code blocks (text between ``` markers)
        code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', chat_content, re.DOTALL)
        
        if code_blocks:
            # Get the last code block
            last_code = code_blocks[-1].strip()
            
            # Copy to clipboard
            self.root.clipboard_clear()
            self.root.clipboard_append(last_code)
            
            # Update status
            self.update_status("📋 Code copied to clipboard", "blue")
        else:
            # Try to find any code-like content (indented blocks)
            lines = chat_content.split('\n')
            code_lines = []
            in_code_block = False
            
            for line in lines:
                if line.strip().startswith('```'):
                    in_code_block = not in_code_block
                    continue
                elif in_code_block or (line.startswith('    ') and line.strip()):
                    code_lines.append(line)
            
            if code_lines:
                code_content = '\n'.join(code_lines).strip()
                self.root.clipboard_clear()
                self.root.clipboard_append(code_content)
                self.update_status("📋 Code-like content copied to clipboard", "blue")
            else:
                self.update_status("❌ No code blocks found", "orange")
    
    def format_input_text(self):
        """Basic formatting for code input"""
        current_text = self.message_entry.get("1.0", tk.END).strip()
        
        if not current_text:
            return
        
        # Basic code formatting
        lines = current_text.split('\n')
        formatted_lines = []
        indent_level = 0
        
        for line in lines:
            stripped = line.strip()
            
            # Decrease indent for closing brackets
            if stripped.startswith(('}', ')', ']')):
                indent_level = max(0, indent_level - 1)
            
            # Add indentation
            formatted_line = '    ' * indent_level + stripped
            formatted_lines.append(formatted_line)
            
            # Increase indent for opening brackets
            if stripped.endswith(('{', '(', '[')):
                indent_level += 1
        
        # Update the text
        self.message_entry.delete("1.0", tk.END)
        self.message_entry.insert("1.0", '\n'.join(formatted_lines))
        
        self.update_status("✨ Text formatted", "blue")
    
    def copy_selection_or_code(self, event=None):
        """Copy selected text or last code block if Ctrl+C is pressed"""
        try:
            # Check if there's selected text in chat display
            if self.chat_display.tag_ranges("sel"):
                selected_text = self.chat_display.selection_get()
                self.root.clipboard_clear()
                self.root.clipboard_append(selected_text)
                self.update_status("📋 Selection copied", "blue")
            elif self.current_model_key in ["code", "code_advanced"]:
                # If in code mode and no selection, copy last code block
                self.copy_last_code_block()
        except tk.TclError:
            # No selection, try copying last code block if in code mode
            if self.current_model_key in ["code", "code_advanced"]:
                self.copy_last_code_block()
        
        return 'break'  # Prevent default behavior
    
    def show_help(self, event=None):
        """Show help dialog with keyboard shortcuts"""
        help_text = """🤖 Companion proto-2.1 (Deepthink) - Keyboard Shortcuts

General:
• Enter - Send message
• Ctrl+Enter - New line in input
• Ctrl+L - Clear current chat
• Ctrl+C - Copy selection or last code block

Mode Switching:
• Ctrl+1 - Chat mode (Llama 3.2 - natural conversation)
• Ctrl+2 - Think mode (DeepSeek R1 - reasoning & analysis)
• Ctrl+3 - Code mode (CodeGemma 2B - default coding)
• Ctrl+4 - Advanced mode (CodeQwen 7B - complex coding)

Features:
• Copy Code button - Copy last code block
• Format Input button - Basic code formatting

Usage Tips:
• Start with Chat mode 💬 for general conversations
• Use Think mode 🤔 for analysis and problem-solving
• Switch to Code mode 💻 for most programming tasks
• Use Advanced mode 🧠 for complex algorithms
• Each mode maintains separate chat history
"""
        
        messagebox.showinfo("Companion proto-2.1 (Deepthink) Help", help_text)
        return 'break'
        
    def switch_model(self, model_key):
        """Switch between different AI models"""
        if model_key == self.current_model_key:
            return  # Already using this model
            
        # Save current chat history
        self.chat_histories[self.current_model_key] = self.chat_history.copy()
        
        # Switch to new model
        old_model_key = self.current_model_key
        self.current_model_key = model_key
        self.model_name = self.models[model_key]["name"]
        self.chat_history = self.chat_histories[model_key]
        
        # Update UI
        self.update_mode_buttons()
        self.update_mode_labels()
        self.update_code_buttons_visibility()
        self.update_status_icons()  # Update the new status icons
        self.refresh_chat_display()
        
        # Show model switch message
        model_info = self.models[model_key]
        switch_msg = f"Switched to {model_info['display_name']} - {model_info['description']}"
        self.update_status(f"🔄 {switch_msg}", "blue")
        
        # Check if the new model is available
        self.check_model_availability()
        
        # Add a system message about the switch
        if len(self.chat_history) == 0:
            self.add_welcome_message()
        else:
            self.add_message_to_chat("System", f"🔄 Switched to {model_info['emoji']} {model_info['display_name'].split()[0]} mode", "assistant")
    
    def update_mode_buttons(self):
        """Update the styling of mode selection buttons"""
        # Reset all local buttons to normal style
        self.chat_button.configure(style='Model.TButton')
        self.think_button.configure(style='Model.TButton')
        self.code_button.configure(style='Model.TButton')
        self.advanced_button.configure(style='Model.TButton')
        
        # Highlight active button
        if self.current_model_key == "chat":
            self.chat_button.configure(style='ActiveModel.TButton')
        elif self.current_model_key == "conversation":
            self.think_button.configure(style='ActiveModel.TButton')
        elif self.current_model_key == "code":
            self.code_button.configure(style='ActiveModel.TButton')
        elif self.current_model_key == "code_advanced":
            self.advanced_button.configure(style='ActiveModel.TButton')
        
        # Update cloud buttons if available
        if hasattr(self, 'cloud_buttons'):
            for btn_key, btn in self.cloud_buttons.items():
                if btn_key == self.current_model_key:
                    btn.configure(style='ActiveModel.TButton')
                else:
                    btn.configure(style='Cloud.TButton')
    
    def update_mode_labels(self):
        """Update mode-related labels"""
        current_model = self.models[self.current_model_key]
        self.current_mode_label.config(text=f"Active: {current_model['emoji']} {current_model['display_name']}")
        self.mode_desc_label.config(text=current_model['description'])
    
    def refresh_chat_display(self):
        """Refresh the chat display with current model's history"""
        # Clear display
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete("1.0", tk.END)
        self.chat_display.config(state=tk.DISABLED)
        
        # Reload chat history for current model
        if len(self.chat_history) == 0:
            self.add_welcome_message()
        else:
            # Replay chat history
            for i, msg in enumerate(self.chat_history):
                if msg["role"] == "user":
                    self.add_message_to_chat("You", msg["content"], "user")
                else:
                    sender = self.models[self.current_model_key]["display_name"]
                    self.add_message_to_chat(sender, msg["content"], "assistant")
    
    def on_enter_pressed(self, event):
        """Handle Enter key press"""
        self.send_message()
        return 'break'  # Prevent default behavior
    
    def insert_newline(self, event):
        """Insert newline with Ctrl+Enter"""
        self.message_entry.insert(tk.INSERT, '\n')
        return 'break'
    
    def on_text_change(self, event):
        """Update character counter with modern styling and enhanced time estimation"""
        text = self.message_entry.get("1.0", tk.END).strip()
        char_count = len(text)
        word_count = len(text.split()) if text else 0
        
        # Enhanced response time estimation
        if char_count > 0:
            # Determine current provider
            current_model = self.models[self.current_model_key]
            provider = current_model.get("provider", "ollama")
            
            if provider == "ollama":
                # Local model estimation
                if self.current_model_key == "chat":
                    base_time = 2.5
                    complexity_factor = word_count * 0.1
                    estimated_time = max(2, min(15, base_time + complexity_factor))
                    speed_indicator = "⚡ Local"
                elif self.current_model_key == "code":
                    base_time = 2
                    complexity_factor = word_count * 0.1
                    estimated_time = max(2, min(12, base_time + complexity_factor))
                    speed_indicator = "� Fast"
                elif self.current_model_key == "code_advanced":
                    base_time = 5
                    complexity_factor = word_count * 0.15
                    estimated_time = max(5, min(30, base_time + complexity_factor))
                    speed_indicator = "🔬 Deep"
                else:
                    base_time = 3
                    complexity_factor = word_count * 0.12
                    estimated_time = max(3, min(20, base_time + complexity_factor))
                    speed_indicator = "� Think"
            else:
                # Cloud model estimation
                base_time = 3
                complexity_factor = word_count * 0.08
                estimated_time = max(2, min(25, base_time + complexity_factor))
                speed_indicator = "☁️ Cloud"
            
            # Update stats with modern formatting
            stats_text = f"{char_count} chars, {word_count} words • ~{estimated_time:.0f}s {speed_indicator}"
            if word_count > 50:
                stats_text += " • Complex query"
            elif word_count > 20:
                stats_text += " • Detailed"
            
            self.stats_label.config(text=stats_text + " • Enter to send • Ctrl+L to clear")
        else:
            self.stats_label.config(text="0 characters • Press Enter to send • Ctrl+L to clear")
    
    def check_ollama_connection(self):
        """Check if Ollama is running and accessible"""
        def check_connection():
            try:
                response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
                if response.status_code == 200:
                    self.root.after(0, lambda: self.update_status("✅ Connected to Ollama", "green"))
                    # Check if our model is available
                    self.check_model_availability()
                else:
                    self.root.after(0, lambda: self.update_status("❌ Ollama connection failed", "red"))
            except Exception as e:
                self.root.after(0, lambda: self.update_status(f"❌ Ollama not accessible: {str(e)}", "red"))
        
        # Run connection check in background
        threading.Thread(target=check_connection, daemon=True).start()
    
    def check_openrouter_connection_async(self):
        """Check OpenRouter connection in background"""
        if not CLOUD_MODELS_AVAILABLE or not self.openrouter_wrapper:
            return
            
        try:
            # Test connection with first available model
            if self.cloud_models:
                from openrouter_client import OpenRouterClient
                first_model = list(self.cloud_models.values())[0]["name"]
                client = OpenRouterClient()
                
                if client.test_connection(first_model):
                    self.root.after(0, lambda: self.update_status("✅ Cloud models ready", "green"))
                else:
                    self.root.after(0, lambda: self.update_status("⚠️ Cloud models unavailable", "orange"))
            else:
                self.root.after(0, lambda: self.update_status("⚠️ No cloud models configured", "orange"))
        except Exception as e:
            self.root.after(0, lambda: self.update_status(f"❌ Cloud error: {str(e)}", "red"))
    
    def check_model_availability(self):
        """Check if the specified models are available"""
        def check_models():
            try:
                response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
                if response.status_code == 200:
                    models = response.json().get('models', [])
                    model_names = [model['name'] for model in models]
                    
                    # Check each configured model and update status indicators
                    available_models = []
                    missing_models = []
                    
                    for model_key, model_info in self.models.items():
                        if model_info['name'] in model_names:
                            available_models.append(model_info['display_name'])
                            # Update individual model status
                            if model_key in self.status_indicators:
                                emoji = self.status_indicators[model_key].cget("text").split()[0]
                                self.root.after(0, lambda k=model_key, e=emoji: 
                                               self.status_indicators[k].config(text=f"{e} ✅", foreground="#00E676"))
                        else:
                            missing_models.append(model_info['display_name'])
                            # Update individual model status
                            if model_key in self.status_indicators:
                                emoji = self.status_indicators[model_key].cget("text").split()[0]
                                self.root.after(0, lambda k=model_key, e=emoji: 
                                               self.status_indicators[k].config(text=f"{e} ❌", foreground="#FF5252"))
                    
                    if missing_models:
                        missing_str = ", ".join(missing_models)
                        available_str = ", ".join(available_models) if available_models else "None"
                        self.root.after(0, lambda: self.update_status(f"⚠️ Missing models: {missing_str}. Available: {available_str}", "orange"))
                    else:
                        self.root.after(0, lambda: self.update_status("✅ All models ready", "green"))
                        self.root.after(0, self.add_welcome_message)
            except Exception as e:
                self.root.after(0, lambda: self.update_status(f"❌ Error checking models: {str(e)}", "red"))
                # Set all model indicators to error
                for model_key in self.status_indicators:
                    emoji = self.status_indicators[model_key].cget("text").split()[0]
                    self.root.after(0, lambda k=model_key, e=emoji: 
                                   self.status_indicators[k].config(text=f"{e} ❌", foreground="#FF5252"))
        
        threading.Thread(target=check_models, daemon=True).start()
    
    def update_status(self, message, color="black"):
        """Update the status label"""
        self.status_label.config(text=message, foreground=color)
    
    def add_welcome_message(self):
        """Add model-specific welcome message to chat"""
        current_model = self.models[self.current_model_key]
        
        if self.current_model_key == "chat":
            welcome_msg = f"""💬 Welcome to Chat Mode!

{current_model['emoji']} **Llama 3.2** is ready for natural conversation!

What would you like to chat about today?"""
        
        elif self.current_model_key == "conversation":
            welcome_msg = f"""🤔 Welcome to Think Mode!

{current_model['emoji']} **DeepSeek R1** is ready to help you think through problems!

What would you like to think through today?"""
        
        elif self.current_model_key == "code":
            welcome_msg = f"""💻 Welcome to Code Mode!

{current_model['emoji']} **CodeGemma 2B** is ready to code with you!

Let's start coding! What can I help you build?"""
        
        elif self.current_model_key == "code_advanced":
            welcome_msg = f"""🧠 Welcome to Advanced Code Mode!

{current_model['emoji']} **CodeQwen 7B** is ready for complex coding challenges!

Ready to tackle complex coding challenges?"""
        
        else:
            welcome_msg = f"""🤖 Welcome to Companion proto-2.1 (Deepthink)!

{current_model['emoji']} **{current_model['display_name']}** is ready!

{current_model['description']}

How can I assist you today?"""
        
        sender_name = current_model['display_name']
        self.add_message_to_chat(sender_name, welcome_msg, "assistant")
    
    def add_message_to_chat(self, sender, message, role="user"):
        """Add a message to the chat display with modern Grok-inspired styling"""
        self.chat_display.config(state=tk.NORMAL)
        
        # Add timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Format message based on role with modern styling
        if role == "user":
            prefix = f"[{timestamp}] 👤 You\n"
            self.chat_display.insert(tk.END, prefix, "user_header")
        else:
            prefix = f"[{timestamp}] 🤖 {sender}\n"
            self.chat_display.insert(tk.END, prefix, "assistant_header")
        
        # Add message content
        self.chat_display.insert(tk.END, f"{message}\n\n", f"{role}_message")
        
        # Configure modern text tags
        self.chat_display.tag_config("user_header", 
                                   foreground="#00D9FF", 
                                   font=('SF Pro Text', 11, 'bold'))
        self.chat_display.tag_config("assistant_header", 
                                   foreground="#00E676", 
                                   font=('SF Pro Text', 11, 'bold'))
        self.chat_display.tag_config("user_message", 
                                   foreground="#FFFFFF", 
                                   font=('SF Pro Text', 11))
        self.chat_display.tag_config("assistant_message", 
                                   foreground="#E0E0E0", 
                                   font=('SF Pro Text', 11))
        self.chat_display.tag_config("code_block", 
                                   foreground="#FFB74D", 
                                   background="#1A1A1A", 
                                   font=('SF Mono', 10),
                                   borderwidth=1,
                                   relief="solid")
        
        # Apply code highlighting if needed
        if role == "assistant":
            self.highlight_code_blocks()
        
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)
    
    def highlight_code_blocks(self):
        """Highlight code blocks in the chat display"""
        self.chat_display.config(state=tk.NORMAL)
        content = self.chat_display.get("1.0", tk.END)
        
        # Find and highlight code blocks
        code_pattern = r'```[\w]*\n(.*?)```'
        matches = re.finditer(code_pattern, content, re.DOTALL)
        
        for match in matches:
            start_pos = f"1.0 + {match.start()}c"
            end_pos = f"1.0 + {match.end()}c"
            self.chat_display.tag_add("code_block", start_pos, end_pos)
        
        self.chat_display.config(state=tk.DISABLED)
    
    def add_streaming_message_start(self):
        """Start a streaming message in the chat with modern styling"""
        self.chat_display.config(state=tk.NORMAL)
        
        # Add timestamp and assistant header
        timestamp = datetime.now().strftime("%H:%M:%S")
        sender_name = self.models[self.current_model_key]["display_name"]
        emoji = self.models[self.current_model_key]["emoji"]
        prefix = f"[{timestamp}] {emoji} {sender_name}\n"
        self.chat_display.insert(tk.END, prefix, "assistant_header")
        
        # Mark the start position for streaming content
        self.streaming_start_pos = self.chat_display.index(tk.END + "-1c")
        
        # Configure streaming text style
        self.chat_display.tag_config("assistant_header", 
                                   foreground="#00E676", 
                                   font=('SF Pro Text', 11, 'bold'))
        self.chat_display.tag_config("streaming", 
                                   foreground="#E0E0E0", 
                                   font=('SF Pro Text', 11))
        
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)
    
    def update_streaming_message(self, content):
        """Update the streaming message with new content"""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, content, "streaming")
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)
    
    def finalize_streaming_message(self):
        """Finalize the streaming message"""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, "\n\n")
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)
    
    def send_message(self):
        """Send message to appropriate AI service (local or cloud) and display response"""
        message = self.message_entry.get("1.0", tk.END).strip()
        
        if not message:
            return
        
        # Clear input
        self.message_entry.delete("1.0", tk.END)
        
        # Add user message to chat
        self.add_message_to_chat("You", message, "user")
        
        # Add to history
        self.chat_history.append({"role": "user", "content": message})
        
        # Disable send button and show loading with modern text
        self.send_button.config(state="disabled", text="⏳ Sending...")
        self.update_status("� AI is processing your request...", "#00D9FF")
        
        # Show thinking icon and start animation
        self.set_thinking_state(True)
        self.start_thinking_animation()
        
        # Route to appropriate service based on provider
        current_model = self.models[self.current_model_key]
        provider = current_model.get("provider", "ollama")
        
        if provider == "ollama":
            # Send to local Ollama
            threading.Thread(target=self.model_wrapper.get_ollama_response_wrapped, args=(message,), daemon=True).start()
        elif provider == "openrouter" and CLOUD_MODELS_AVAILABLE and self.openrouter_wrapper:
            # Send to OpenRouter cloud
            model_name = current_model["name"]
            threading.Thread(target=self.openrouter_wrapper.get_openrouter_response_wrapped, args=(message, model_name), daemon=True).start()
        else:
            # Fallback error
            error_msg = "❌ Provider not available"
            if provider == "openrouter" and not CLOUD_MODELS_AVAILABLE:
                error_msg = "❌ Cloud models not available - OpenRouter integration missing"
            elif provider == "openrouter" and not self.openrouter_wrapper:
                error_msg = "❌ OpenRouter wrapper failed to initialize"
            
            self.root.after(0, lambda: self.add_message_to_chat("System", error_msg, "assistant"))
            self.root.after(0, self.stop_thinking_animation)
            self.root.after(0, lambda: self.send_button.config(state="normal", text="Send ↗"))
    
    def start_thinking_animation(self):
        """Start enhanced thinking animation using wrapper"""
        self.thinking_dots = 0
        self.model_wrapper.animate_thinking_enhanced(self.current_model_key)
    
    def stop_thinking_animation(self):
        """Stop the thinking animation"""
        if hasattr(self, 'thinking_dots'):
            delattr(self, 'thinking_dots')
        # Stop wrapper streaming
        self.model_wrapper.is_streaming = False
        # Clear thinking state
        self.set_thinking_state(False)
    
    def get_ollama_response(self, message):
        """Get response from Ollama API with streaming support and model-specific settings"""
        try:
            # Use the chat API with proper context for better performance
            messages = []
            # Include recent chat history for context (last 10 messages)
            recent_history = self.chat_history[-10:] if len(self.chat_history) > 10 else self.chat_history
            for msg in recent_history:
                messages.append(msg)
            
            # Add current message
            messages.append({"role": "user", "content": message})
            
            # Model-specific configurations
            options = {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 2048
            }
            
            # Adjust parameters based on model type
            if self.current_model_key == "code":
                # CodeGemma 2B optimizations for faster performance
                options.update({
                    "temperature": 0.2,  # Lower temperature for focused responses
                    "top_p": 0.7,        # More focused token selection
                    "num_predict": 2048,  # Moderate length for faster generation
                    "repeat_penalty": 1.1,
                    "top_k": 20,         # Limit vocabulary for speed
                    "stop": ["\n\n\n"]   # Stop on excessive newlines
                })
            elif self.current_model_key == "code_advanced":
                # CodeQwen 7B settings for more detailed responses
                options.update({
                    "temperature": 0.3,  # Low temperature for code precision
                    "top_p": 0.8,
                    "num_predict": 4096,  # Allow longer, more detailed code
                    "repeat_penalty": 1.1,
                    "top_k": 40
                })
            elif self.current_model_key == "conversation":
                # Conversation can be more creative
                options.update({
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "num_predict": 2048
                })
            
            payload = {
                "model": self.model_name,
                "messages": messages,
                "stream": True,
                "options": options
            }
            
            # Use streaming for real-time response
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json=payload,
                timeout=120,
                stream=True
            )
            
            if response.status_code == 200:
                # Initialize response tracking
                ai_response = ""
                response_start_time = datetime.now()
                
                # Add initial message placeholder
                self.root.after(0, lambda: self.add_streaming_message_start())
                
                # Process streaming response
                for line in response.iter_lines():
                    if line:
                        try:
                            chunk = json.loads(line.decode('utf-8'))
                            if 'message' in chunk and 'content' in chunk['message']:
                                new_content = chunk['message']['content']
                                ai_response += new_content
                                # Update UI with streaming content
                                self.root.after(0, lambda content=new_content: self.update_streaming_message(content))
                            
                            # Check if response is complete
                            if chunk.get('done', False):
                                break
                                
                        except json.JSONDecodeError:
                            continue
                
                # Finalize response
                if ai_response.strip():
                    # Add to history
                    self.chat_history.append({"role": "assistant", "content": ai_response})
                    self.chat_histories[self.current_model_key] = self.chat_history.copy()
                    
                    # Update status with timing and model info
                    response_time = (datetime.now() - response_start_time).total_seconds()
                    model_display = self.models[self.current_model_key]["display_name"]
                    self.root.after(0, lambda: self.update_status(f"✅ {model_display} responded ({response_time:.1f}s)", "green"))
                    self.root.after(0, self.finalize_streaming_message)
                else:
                    self.root.after(0, lambda: self.add_message_to_chat("System", "❌ No response received", "assistant"))
                    self.root.after(0, lambda: self.update_status("❌ Empty response", "red"))
            else:
                error_msg = f"Error: HTTP {response.status_code}"
                self.root.after(0, lambda: self.add_message_to_chat("System", f"❌ {error_msg}", "assistant"))
                self.root.after(0, lambda: self.update_status(f"❌ {error_msg}", "red"))
                
        except requests.exceptions.Timeout:
            error_msg = "Request timed out. Please try again."
            self.root.after(0, lambda: self.add_message_to_chat("System", f"⏰ {error_msg}", "assistant"))
            self.root.after(0, lambda: self.update_status("⏰ Request timed out", "orange"))
            
        except Exception as e:
            error_msg = f"Error communicating with Ollama: {str(e)}"
            self.root.after(0, lambda: self.add_message_to_chat("System", f"❌ {error_msg}", "assistant"))
            self.root.after(0, lambda: self.update_status(f"❌ Connection error", "red"))
        
        finally:
            # Stop thinking animation and re-enable send button
            self.root.after(0, self.stop_thinking_animation)
            self.root.after(0, lambda: self.send_button.config(state="normal", text="Send ↗"))
    
    def clear_chat(self):
        """Clear the chat history and display for current model"""
        # Clear current model's history
        self.chat_histories[self.current_model_key] = []
        self.chat_history = []
        
        # Clear display
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete("1.0", tk.END)
        self.chat_display.config(state=tk.DISABLED)
        
        # Add welcome message for current model
        self.add_welcome_message()
        
        # Update status
        model_name = self.models[self.current_model_key]["display_name"]
        self.update_status(f"🗑️ Cleared chat for {model_name}", "blue")

class ModelWrapper:
    """Unified wrapper for all AI models with enhanced flow and output handling"""
    
    def __init__(self, parent):
        self.parent = parent
        self.response_buffer = ""
        self.chunk_buffer = ""
        self.is_streaming = False
        self.response_metrics = {
            'start_time': None,
            'first_token_time': None,
            'total_tokens': 0,
            'chunks_received': 0
        }
        
        # Model-specific configurations for optimal performance
        self.model_configs = {
            "chat": {
                "temperature": 0.8,
                "top_p": 0.9,
                "num_predict": 2048,
                "repeat_penalty": 1.1,
                "top_k": 40,
                "chunk_size": 6,  # Characters per UI update
                "update_interval": 40,  # ms between updates
                "thinking_style": ["💬", "💭", "⚡", "✨", "🗣️", "💡"]
            },
            "conversation": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 2048,
                "repeat_penalty": 1.1,
                "top_k": 40,
                "chunk_size": 8,  # Characters per UI update
                "update_interval": 50,  # ms between updates
                "thinking_style": ["🤔", "💭", "⚡", "✨", "🧐", "💡"]
            },
            "code": {
                "temperature": 0.2,
                "top_p": 0.7,
                "num_predict": 2048,
                "repeat_penalty": 1.1,
                "top_k": 20,
                "stop": ["\n\n\n", "```\n\n"],
                "chunk_size": 4,  # Faster updates for code
                "update_interval": 30,
                "thinking_style": ["💻", "⚡", "🔧", "⚙️", "🚀"]
            },
            "code_advanced": {
                "temperature": 0.3,
                "top_p": 0.8,
                "num_predict": 4096,
                "repeat_penalty": 1.1,
                "top_k": 40,
                "chunk_size": 6,
                "update_interval": 40,
                "thinking_style": ["🧠", "🔬", "⚡", "💡", "🎯", "🔍"]
            }
        }
    
    def get_model_config(self, model_key):
        """Get optimized configuration for specific model"""
        return self.model_configs.get(model_key, self.model_configs["conversation"])
    
    def prepare_context(self, message, chat_history, max_context=10):
        """Prepare conversation context with intelligent truncation"""
        messages = []
        
        # Add system message for better responses based on model
        model_key = self.parent.current_model_key
        if model_key == "chat":
            system_msg = {
                "role": "system", 
                "content": "You are a helpful, friendly AI assistant for natural conversation. Be engaging, informative, and conversational. Respond naturally and help with a wide range of topics."
            }
            messages.append(system_msg)
        elif model_key == "code":
            system_msg = {
                "role": "system", 
                "content": "You are a helpful coding assistant. Provide clear, concise code examples with brief explanations. Format code using markdown code blocks."
            }
            messages.append(system_msg)
        elif model_key == "code_advanced":
            system_msg = {
                "role": "system", 
                "content": "You are an expert programming assistant. Provide detailed explanations, best practices, and well-documented code. Include error handling and optimization suggestions when relevant."
            }
            messages.append(system_msg)
        elif model_key == "conversation":
            system_msg = {
                "role": "system", 
                "content": "You are a thoughtful AI assistant focused on reasoning and analysis. Think step by step and provide clear explanations for your conclusions."
            }
            messages.append(system_msg)
        
        # Add recent chat history with smart truncation
        if chat_history:
            # Keep recent messages but ensure we don't exceed context window
            recent_messages = chat_history[-max_context:] if len(chat_history) > max_context else chat_history
            for msg in recent_messages:
                messages.append(msg)
        
        # Add current message
        messages.append({"role": "user", "content": message})
        
        return messages
    
    def smooth_streaming_update(self, new_content):
        """Handle smooth streaming updates with buffering"""
        if not new_content:
            return
        
        self.chunk_buffer += new_content
        config = self.get_model_config(self.parent.current_model_key)
        
        # Update metrics
        self.response_metrics['chunks_received'] += 1
        self.response_metrics['total_tokens'] += len(new_content.split())
        
        # Record first token time
        if self.response_metrics['first_token_time'] is None:
            self.response_metrics['first_token_time'] = datetime.now()
        
        # Update UI in chunks for smoother experience
        if len(self.chunk_buffer) >= config['chunk_size']:
            content_to_display = self.chunk_buffer
            self.chunk_buffer = ""
            
            # Schedule UI update
            self.parent.root.after(0, lambda content=content_to_display: 
                                 self.parent.update_streaming_message(content))
    
    def animate_thinking_enhanced(self, model_key):
        """Enhanced thinking animation based on model type"""
        config = self.get_model_config(model_key)
        thinking_icons = config['thinking_style']
        
        def animate():
            if hasattr(self.parent, 'thinking_dots') and self.is_streaming:
                # Cycle through model-specific thinking icons
                icon_index = self.parent.thinking_dots % len(thinking_icons)
                current_icon = thinking_icons[icon_index]
                
                # Update thinking icon with smooth transition
                self.parent.thinking_icon.config(text=current_icon, foreground="#3498db")
                
                # Update status with contextual message
                if model_key == "chat":
                    status_msg = f"💬 Chatting{('.' * (self.parent.thinking_dots % 4))}"
                elif model_key == "code":
                    status_msg = f"💻 Coding{('.' * (self.parent.thinking_dots % 4))}"
                elif model_key == "code_advanced":
                    status_msg = f"🧠 Analyzing{('.' * (self.parent.thinking_dots % 4))}"
                else:
                    status_msg = f"🤔 Thinking{('.' * (self.parent.thinking_dots % 4))}"
                
                self.parent.update_status(status_msg, "blue")
                self.parent.thinking_dots += 1
                
                # Schedule next animation
                self.parent.root.after(config['update_interval'], animate)
        
        animate()
    
    def calculate_response_metrics(self):
        """Calculate and return response performance metrics"""
        if not self.response_metrics['start_time']:
            return None
        
        total_time = (datetime.now() - self.response_metrics['start_time']).total_seconds()
        first_token_time = None
        
        if self.response_metrics['first_token_time']:
            first_token_time = (self.response_metrics['first_token_time'] - 
                              self.response_metrics['start_time']).total_seconds()
        
        tokens_per_second = (self.response_metrics['total_tokens'] / total_time) if total_time > 0 else 0
        
        return {
            'total_time': total_time,
            'first_token_time': first_token_time,
            'total_tokens': self.response_metrics['total_tokens'],
            'tokens_per_second': tokens_per_second,
            'chunks_received': self.response_metrics['chunks_received']
        }
    
    def reset_metrics(self):
        """Reset response metrics for new request"""
        self.response_metrics = {
            'start_time': datetime.now(),
            'first_token_time': None,
            'total_tokens': 0,
            'chunks_received': 0
        }
        self.response_buffer = ""
        self.chunk_buffer = ""
    
    def format_response_status(self, metrics, model_display):
        """Format final response status with performance info"""
        if not metrics:
            return f"✅ {model_display} responded"
        
        status_parts = [f"✅ {model_display}"]
        
        # Add timing info
        if metrics['total_time']:
            status_parts.append(f"({metrics['total_time']:.1f}s")
            
            if metrics['tokens_per_second'] > 0:
                status_parts.append(f"@ {metrics['tokens_per_second']:.1f} tok/s)")
            else:
                status_parts.append(")")
        
        # Add performance indicator
        if metrics['tokens_per_second'] > 15:
            status_parts.append("⚡")
        elif metrics['tokens_per_second'] > 8:
            status_parts.append("🚀")
        else:
            status_parts.append("💫")
        
        return " ".join(status_parts)

    def handle_response_error(self, error, error_type="general"):
        """Enhanced error handling with user-friendly messages"""
        error_messages = {
            "timeout": {
                "title": "⏰ Request Timeout",
                "message": "The model took too long to respond. This can happen with complex requests.",
                "suggestions": ["Try a shorter message", "Switch to a faster model", "Check your connection"]
            },
            "connection": {
                "title": "❌ Connection Error", 
                "message": "Unable to connect to Ollama. Make sure it's running.",
                "suggestions": ["Start Ollama service", "Check if models are loaded", "Verify port 11434 is accessible"]
            },
            "model_not_found": {
                "title": "🔍 Model Not Available",
                "message": "The selected model is not available in Ollama.",
                "suggestions": ["Pull the model using 'ollama pull'", "Switch to an available model", "Check model status"]
            },
            "general": {
                "title": "❌ Unexpected Error",
                "message": str(error),
                "suggestions": ["Try again", "Check Ollama status", "Restart the application if needed"]
            }
        }
        
        error_info = error_messages.get(error_type, error_messages["general"])
        
        # Display user-friendly error
        error_display = f"{error_info['title']}\n\n{error_info['message']}"
        if error_info.get('suggestions'):
            error_display += f"\n\n💡 Suggestions:\n" + "\n".join([f"• {s}" for s in error_info['suggestions']])
        
        self.parent.root.after(0, lambda: self.parent.add_message_to_chat(
            "System", error_display, "assistant"))
        self.parent.root.after(0, lambda: self.parent.update_status(error_info['title'], "red"))

    def get_ollama_response_wrapped(self, message):
        """Enhanced wrapper for Ollama API calls with smooth streaming"""
        try:
            self.reset_metrics()
            self.is_streaming = True
            
            # Prepare optimized context
            messages = self.prepare_context(message, self.parent.chat_history)
            
            # Get model-specific configuration
            config = self.get_model_config(self.parent.current_model_key)
            
            # Prepare optimized payload
            payload = {
                "model": self.parent.model_name,
                "messages": messages,
                "stream": True,
                "options": {k: v for k, v in config.items() 
                           if k not in ['chunk_size', 'update_interval', 'thinking_style']}
            }
            
            # Start enhanced thinking animation
            self.animate_thinking_enhanced(self.parent.current_model_key)
            
            # Make streaming request
            response = requests.post(
                f"{self.parent.ollama_url}/api/chat",
                json=payload,
                timeout=120,
                stream=True
            )
            
            if response.status_code == 200:
                ai_response = ""
                
                # Initialize streaming display
                self.parent.root.after(0, lambda: self.parent.add_streaming_message_start())
                
                # Process streaming response with enhanced handling
                for line in response.iter_lines():
                    if line and self.is_streaming:
                        try:
                            chunk = json.loads(line.decode('utf-8'))
                            if 'message' in chunk and 'content' in chunk['message']:
                                new_content = chunk['message']['content']
                                ai_response += new_content
                                
                                # Use smooth streaming update
                                self.smooth_streaming_update(new_content)
                            
                            if chunk.get('done', False):
                                break
                                
                        except json.JSONDecodeError:
                            continue
                
                # Flush any remaining buffer
                if self.chunk_buffer:
                    self.parent.root.after(0, lambda content=self.chunk_buffer: 
                                         self.parent.update_streaming_message(content))
                
                # Finalize response
                if ai_response.strip():
                    # Add to history
                    self.parent.chat_history.append({"role": "assistant", "content": ai_response})
                    self.parent.chat_histories[self.parent.current_model_key] = self.parent.chat_history.copy()
                    
                    # Calculate and display metrics
                    metrics = self.calculate_response_metrics()
                    model_display = self.parent.models[self.parent.current_model_key]["display_name"]
                    status_message = self.format_response_status(metrics, model_display)
                    
                    self.parent.root.after(0, lambda: self.parent.update_status(status_message, "green"))
                    self.parent.root.after(0, self.parent.finalize_streaming_message)
                else:
                    self.handle_response_error("Empty response received", "general")
                    
            elif response.status_code == 404:
                self.handle_response_error(f"Model {self.parent.model_name} not found", "model_not_found")
            else:
                self.handle_response_error(f"HTTP {response.status_code}", "connection")
                
        except requests.exceptions.Timeout:
            self.handle_response_error("Request timeout", "timeout")
        except requests.exceptions.ConnectionError:
            self.handle_response_error("Connection failed", "connection")
        except Exception as e:
            self.handle_response_error(e, "general")
        finally:
            self.is_streaming = False
            # Re-enable UI
            self.parent.root.after(0, self.parent.stop_thinking_animation)
            self.parent.root.after(0, lambda: self.parent.send_button.config(
                state="normal", text="Send\n(Enter)"))

def main():
    """Main function to run the application"""
    root = tk.Tk()
    app = Companion(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)

if __name__ == "__main__":
    main()
