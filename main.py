#!/usr/bin/env python3
"""
Companion proto-2.1 (Deepthink) - A modern GUI for Ollama AI models
A beautiful chat interface for interacting with local AI models
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

class DeepCompanion:
    def __init__(self, root):
        self.root = root
        self.root.title("Companion proto-2.1 (Deepthink) - AI Chat Interface")
        self.root.geometry("900x700")
        self.root.minsize(600, 500)
        
        # Configure style
        self.setup_styles()
        
        # Ollama configuration
        self.ollama_url = "http://localhost:11434"
        
        # Model configuration - Support for multiple models
        self.models = {
            "conversation": {
                "name": "deepseek-r1:1.5b",
                "display_name": "DeepSeek R1 (Conversation)",
                "description": "AI thinking and reasoning mode",
                "emoji": "🤔"
            },
            "code": {
                "name": "codegemma:2b", 
                "display_name": "CodeGemma 2B (Code)",
                "description": "Default coding assistant",
                "emoji": "💻"
            },
            "code_advanced": {
                "name": "codeqwen:7b", 
                "display_name": "CodeQwen 7B (Advanced)",
                "description": "Advanced coding with detailed explanations",
                "emoji": "🧠"
            }
        }
        
        # Current model selection - default to normal coding
        self.current_model_key = "code"
        self.model_name = self.models[self.current_model_key]["name"]
        
        # Chat history (separate for each model)
        self.chat_histories = {
            "conversation": [],
            "code": [],
            "code_advanced": []
        }
        self.chat_history = self.chat_histories[self.current_model_key]
        
        # Create GUI
        self.create_menu()
        self.create_widgets()
        
        # Check Ollama connection on startup
        self.check_ollama_connection()
    
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
        models_menu.add_command(label="🤔 Think Mode", command=lambda: self.switch_model("conversation"), accelerator="Ctrl+1")
        models_menu.add_command(label="💻 Code Mode", command=lambda: self.switch_model("code"), accelerator="Ctrl+2")
        models_menu.add_command(label="🧠 Advanced Code", command=lambda: self.switch_model("code_advanced"), accelerator="Ctrl+3")
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
        about_text = """🤖 Companion proto-2.1 (Deepthink) v2.1

A modern GUI for local AI model interaction

Features:
• Three specialized modes with dedicated icons
• Real-time streaming responses with visual indicators
• Separate chat histories per mode
• Code-specific tools and formatting
• Keyboard shortcuts for efficiency
• Interactive status icons and animations

Modes:
🤔 Think Mode - DeepSeek R1 1.5B for reasoning & analysis
💻 Code Mode - CodeGemma 2B for everyday coding (default)
🧠 Advanced Mode - CodeQwen 7B for complex programming

Visual Indicators:
• 🤔💭⚡✨ - AI thinking animation
• 💻⚡ - Default coding mode
• 🧠🔬 - Advanced coding mode

Optimized for Intel i7-7600U with 8GB RAM

Built with Python & tkinter
Powered by Ollama"""
        
        messagebox.showinfo("About Companion proto-2.1 (Deepthink)", about_text)
    
    def setup_styles(self):
        """Configure custom styles for the application"""
        style = ttk.Style()
        
        # Configure the theme
        style.theme_use('clam')
        
        # Custom colors
        bg_color = "#2c3e50"
        fg_color = "#ecf0f1"
        accent_color = "#3498db"
        secondary_color = "#34495e"
        
        # Configure styles
        style.configure('Title.TLabel', 
                       background=bg_color, 
                       foreground=accent_color, 
                       font=('Arial', 16, 'bold'))
        
        style.configure('Status.TLabel', 
                       background=bg_color, 
                       foreground=fg_color, 
                       font=('Arial', 9))
        
        style.configure('Send.TButton', 
                       background=accent_color, 
                       foreground='white', 
                       font=('Arial', 10, 'bold'))
        
        style.map('Send.TButton',
                 background=[('active', '#2980b9')])
                 
        style.configure('Model.TButton', 
                       background=secondary_color, 
                       foreground=fg_color, 
                       font=('Arial', 9))
        
        style.map('Model.TButton',
                 background=[('active', '#4a5f7a')])
        
        style.configure('ActiveModel.TButton', 
                       background=accent_color, 
                       foreground='white', 
                       font=('Arial', 9, 'bold'))
        
        style.map('ActiveModel.TButton',
                 background=[('active', '#2980b9')])
        
        # Configure root background
        self.root.configure(bg=bg_color)
    
    def create_widgets(self):
        """Create and layout the GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_frame, 
                               text="🤖 Companion proto-2.1 (Deepthink)", 
                               style='Title.TLabel')
        title_label.pack(pady=(0, 10))
        
        # Mode selector frame with icons (replace model tabs)
        mode_frame = ttk.Frame(main_frame)
        mode_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Mode selection with icons instead of tabs
        modes_container = ttk.Frame(mode_frame)
        modes_container.pack(anchor=tk.CENTER)
        
        # Think mode button (DeepSeek R1)
        self.think_button = ttk.Button(
            modes_container,
            text="🤔 Think",
            command=lambda: self.switch_model("conversation"),
            style='Model.TButton',
            width=12
        )
        self.think_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Code mode button (CodeGemma - default)
        self.code_button = ttk.Button(
            modes_container,
            text="💻 Code",
            command=lambda: self.switch_model("code"),
            style='ActiveModel.TButton',
            width=12
        )
        self.code_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Advanced coding button (CodeQwen)
        self.advanced_button = ttk.Button(
            modes_container,
            text="🧠 Advanced",
            command=lambda: self.switch_model("code_advanced"),
            style='Model.TButton',
            width=12
        )
        self.advanced_button.pack(side=tk.LEFT)
        
        # Current mode description
        current_model = self.models[self.current_model_key]
        self.mode_desc_label = ttk.Label(
            mode_frame, 
            text=current_model['description'], 
            style='Status.TLabel',
            font=('Arial', 9, 'italic')
        )
        self.mode_desc_label.pack(anchor=tk.CENTER, pady=(5, 0))
        
        # Status frame
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(10, 10))
        
        self.status_label = ttk.Label(status_frame, 
                                     text="Connecting to Ollama...", 
                                     style='Status.TLabel')
        self.status_label.pack(side=tk.LEFT)
        
        # Model availability indicators with icons
        self.model_status_frame = ttk.Frame(status_frame)
        self.model_status_frame.pack(side=tk.LEFT, padx=(20, 0))
        
        self.think_status = ttk.Label(self.model_status_frame, 
                                     text="🤔 ⏳", 
                                     style='Status.TLabel',
                                     font=('Arial', 8))
        self.think_status.pack(side=tk.LEFT, padx=(0, 5))
        
        self.code_status = ttk.Label(self.model_status_frame, 
                                    text="💻 ⏳", 
                                    style='Status.TLabel',
                                    font=('Arial', 8))
        self.code_status.pack(side=tk.LEFT, padx=(0, 5))
        
        self.advanced_status = ttk.Label(self.model_status_frame, 
                                        text="🧠 ⏳", 
                                        style='Status.TLabel',
                                        font=('Arial', 8))
        self.advanced_status.pack(side=tk.LEFT)
        
        self.active_mode_label = ttk.Label(status_frame, 
                                          text=f"Mode: {current_model['emoji']} {current_model['display_name'].split()[0]}", 
                                          style='Status.TLabel')
        self.active_mode_label.pack(side=tk.RIGHT)
        
        # Chat display area
        self.chat_display = scrolledtext.ScrolledText(
            main_frame,
            wrap=tk.WORD,
            width=80,
            height=25,
            font=('Consolas', 10),
            bg="#34495e",
            fg="#ecf0f1",
            insertbackground="#ecf0f1",
            selectbackground="#3498db",
            selectforeground="white",
            state=tk.DISABLED
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Input frame
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X)
        
        # Message input
        self.message_entry = tk.Text(
            input_frame,
            height=3,
            font=('Arial', 10),
            bg="#ecf0f1",
            fg="#2c3e50",
            insertbackground="#2c3e50",
            wrap=tk.WORD
        )
        self.message_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Bind Enter key (Ctrl+Enter for new line)
        self.message_entry.bind('<Return>', self.on_enter_pressed)
        self.message_entry.bind('<Control-Return>', self.insert_newline)
        self.message_entry.bind('<KeyRelease>', self.on_text_change)
        
        # Additional keyboard shortcuts
        self.root.bind('<Control-1>', lambda e: self.switch_model("conversation"))
        self.root.bind('<Control-2>', lambda e: self.switch_model("code"))
        self.root.bind('<Control-3>', lambda e: self.switch_model("code_advanced"))
        self.root.bind('<Control-l>', lambda e: self.clear_chat())
        self.root.bind('<Control-c>', self.copy_selection_or_code)
        self.root.bind('<F1>', self.show_help)
        
        # Icon status frame below input
        icon_frame = ttk.Frame(input_frame)
        icon_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(2, 0))
        
        # Character counter
        self.char_label = ttk.Label(icon_frame, text="0 chars", style='Status.TLabel', font=('Arial', 8))
        self.char_label.pack(side=tk.LEFT)
        
        # Thinking indicator
        self.thinking_icon = ttk.Label(icon_frame, text="", style='Status.TLabel', font=('Arial', 12))
        self.thinking_icon.pack(side=tk.LEFT, padx=(10, 5))
        
        # Advanced coding mode indicator
        self.coding_icon = ttk.Label(icon_frame, text="", style='Status.TLabel', font=('Arial', 12))
        self.coding_icon.pack(side=tk.LEFT, padx=(5, 0))
        
        # Speed indicator
        self.speed_icon = ttk.Label(icon_frame, text="", style='Status.TLabel', font=('Arial', 10))
        self.speed_icon.pack(side=tk.RIGHT)
        
        # Update icons based on current model
        self.update_status_icons()
        
        # Send button
        self.send_button = ttk.Button(
            input_frame,
            text="Send\n(Enter)",
            command=self.send_message,
            style='Send.TButton'
        )
        self.send_button.pack(side=tk.RIGHT)
        
        # Clear button
        clear_button = ttk.Button(
            input_frame,
            text="Clear\nChat",
            command=self.clear_chat
        )
        clear_button.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Code-specific buttons (only visible in code mode)
        self.code_buttons_frame = ttk.Frame(input_frame)
        
        # Copy last code button
        self.copy_code_button = ttk.Button(
            self.code_buttons_frame,
            text="Copy\nCode",
            command=self.copy_last_code_block,
            style='Model.TButton'
        )
        self.copy_code_button.pack(side=tk.RIGHT, padx=(0, 5))
        
        # Format code button
        self.format_code_button = ttk.Button(
            self.code_buttons_frame,
            text="Format\nInput",
            command=self.format_input_text,
            style='Model.TButton'
        )
        self.format_code_button.pack(side=tk.RIGHT, padx=(0, 5))
        
        # Update button visibility based on current model
        self.update_code_buttons_visibility()
        
        # Focus on message entry
        self.message_entry.focus()
        
    def update_status_icons(self):
        """Update status icons based on current model and state"""
        # Clear all icons first
        self.thinking_icon.config(text="", foreground="gray")
        self.coding_icon.config(text="", foreground="gray")
        self.speed_icon.config(text="", foreground="gray")
        
        # Update model-specific icons
        if self.current_model_key == "conversation":
            self.coding_icon.config(text="🤔", foreground="#3498db")  # Think icon
            self.speed_icon.config(text="💭", foreground="blue")      # Thinking speed
        elif self.current_model_key == "code":
            self.coding_icon.config(text="💻", foreground="#f39c12") # Normal coding icon
            self.speed_icon.config(text="⚡", foreground="green")      # Fast speed
        elif self.current_model_key == "code_advanced":
            self.coding_icon.config(text="🧠", foreground="#e74c3c") # Advanced coding icon
            self.speed_icon.config(text="🔬", foreground="orange")     # Research/detailed mode
    
    def set_thinking_state(self, is_thinking=False):
        """Update thinking icon to show AI processing state"""
        if is_thinking:
            self.thinking_icon.config(text="🤔", foreground="#3498db")
        else:
            self.thinking_icon.config(text="", foreground="gray")
    
    def update_code_buttons_visibility(self):
        """Show/hide code-specific buttons based on current model"""
        if self.current_model_key in ["code", "code_advanced"]:
            self.code_buttons_frame.pack(side=tk.RIGHT, padx=(5, 0))
        else:
            self.code_buttons_frame.pack_forget()
    
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
• Ctrl+1 - Think mode (DeepSeek R1 - reasoning & analysis)
• Ctrl+2 - Code mode (CodeGemma 2B - default coding)
• Ctrl+3 - Advanced mode (CodeQwen 7B - complex coding)

Features:
• Copy Code button - Copy last code block
• Format Input button - Basic code formatting

Usage Tips:
• Start with Code mode 💻 for most programming tasks
• Use Think mode 🤔 for analysis and problem-solving
• Switch to Advanced mode 🧠 for complex algorithms
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
        # Reset all buttons to normal style
        self.think_button.configure(style='Model.TButton')
        self.code_button.configure(style='Model.TButton')
        self.advanced_button.configure(style='Model.TButton')
        
        # Highlight active button
        if self.current_model_key == "conversation":
            self.think_button.configure(style='ActiveModel.TButton')
        elif self.current_model_key == "code":
            self.code_button.configure(style='ActiveModel.TButton')
        elif self.current_model_key == "code_advanced":
            self.advanced_button.configure(style='ActiveModel.TButton')
    
    def update_mode_labels(self):
        """Update mode-related labels"""
        current_model = self.models[self.current_model_key]
        mode_name = current_model['display_name'].split()[0]  # Get first word (DeepSeek, CodeGemma, CodeQwen)
        self.active_mode_label.config(text=f"Mode: {current_model['emoji']} {mode_name}")
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
        """Update character counter"""
        text = self.message_entry.get("1.0", tk.END).strip()
        char_count = len(text)
        
        # Estimate response time based on message length and current model
        if char_count > 0:
            if self.current_model_key == "code":
                # CodeGemma 2B - Default coding, fast responses
                estimated_time = max(2, min(8, char_count // 30))
                speed_indicator = "💻"
            elif self.current_model_key == "code_advanced":
                # CodeQwen 7B - Advanced coding, slower but detailed
                estimated_time = max(8, min(25, char_count // 15))
                speed_indicator = "🧠"
            else:
                # Think mode - DeepSeek R1, analytical responses
                estimated_time = max(3, min(15, char_count // 20))
                speed_indicator = "🤔"
            
            self.char_label.config(text=f"{char_count} chars (~{estimated_time}s {speed_indicator})")
        else:
            self.char_label.config(text="0 chars")
    
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
                            if model_key == "conversation":
                                self.root.after(0, lambda: self.think_status.config(text="🤔 ✅", foreground="green"))
                            elif model_key == "code":
                                self.root.after(0, lambda: self.code_status.config(text="💻 ✅", foreground="green"))
                            elif model_key == "code_advanced":
                                self.root.after(0, lambda: self.advanced_status.config(text="🧠 ✅", foreground="green"))
                        else:
                            missing_models.append(model_info['display_name'])
                            # Update individual model status
                            if model_key == "conversation":
                                self.root.after(0, lambda: self.think_status.config(text="🤔 ❌", foreground="red"))
                            elif model_key == "code":
                                self.root.after(0, lambda: self.code_status.config(text="💻 ❌", foreground="red"))
                            elif model_key == "code_advanced":
                                self.root.after(0, lambda: self.advanced_status.config(text="🧠 ❌", foreground="red"))
                    
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
                self.root.after(0, lambda: self.think_status.config(text="🤔 ❌", foreground="red"))
                self.root.after(0, lambda: self.code_status.config(text="💻 ❌", foreground="red"))
                self.root.after(0, lambda: self.advanced_status.config(text="🧠 ❌", foreground="red"))
        
        threading.Thread(target=check_models, daemon=True).start()
    
    def update_status(self, message, color="black"):
        """Update the status label"""
        self.status_label.config(text=message, foreground=color)
    
    def add_welcome_message(self):
        """Add model-specific welcome message to chat"""
        current_model = self.models[self.current_model_key]
        
        if self.current_model_key == "conversation":
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
        """Add a message to the chat display"""
        self.chat_display.config(state=tk.NORMAL)
        
        # Add timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Format message based on role
        if role == "user":
            prefix = f"[{timestamp}] 👤 You:\n"
            self.chat_display.insert(tk.END, prefix, "user_name")
        else:
            prefix = f"[{timestamp}] 🤖 {sender}:\n"
            self.chat_display.insert(tk.END, prefix, "assistant_name")
        
        # Add message content
        self.chat_display.insert(tk.END, f"{message}\n\n", "message")
        
        # Configure text tags for styling
        self.chat_display.tag_config("user_name", foreground="#3498db", font=('Arial', 10, 'bold'))
        self.chat_display.tag_config("assistant_name", foreground="#e74c3c", font=('Arial', 10, 'bold'))
        self.chat_display.tag_config("message", foreground="#ecf0f1")
        self.chat_display.tag_config("code_block", foreground="#f39c12", background="#2c3e50", font=('Consolas', 9))
        
        # Apply code highlighting if in code mode
        if role == "assistant" and self.current_model_key in ["code", "code_advanced"]:
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
        """Start a streaming message in the chat"""
        self.chat_display.config(state=tk.NORMAL)
        
        # Add timestamp and assistant header
        timestamp = datetime.now().strftime("%H:%M:%S")
        sender_name = self.models[self.current_model_key]["display_name"]
        emoji = self.models[self.current_model_key]["emoji"]
        prefix = f"[{timestamp}] {emoji} {sender_name}:\n"
        self.chat_display.insert(tk.END, prefix, "assistant_name")
        
        # Mark the start position for streaming content
        self.streaming_start_pos = self.chat_display.index(tk.END + "-1c")
        
        # Configure text tags for styling
        self.chat_display.tag_config("assistant_name", foreground="#e74c3c", font=('Arial', 10, 'bold'))
        self.chat_display.tag_config("streaming", foreground="#ecf0f1")
        
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
        """Send message to Ollama and display response"""
        message = self.message_entry.get("1.0", tk.END).strip()
        
        if not message:
            return
        
        # Clear input
        self.message_entry.delete("1.0", tk.END)
        
        # Add user message to chat
        self.add_message_to_chat("You", message, "user")
        
        # Add to history
        self.chat_history.append({"role": "user", "content": message})
        
        # Disable send button and show loading with animated dots
        self.send_button.config(state="disabled", text="Thinking...")
        self.update_status("🤔 AI is thinking...", "blue")
        
        # Show thinking icon and start animation
        self.set_thinking_state(True)
        self.start_thinking_animation()
        
        # Send to Ollama in background thread
        threading.Thread(target=self.get_ollama_response, args=(message,), daemon=True).start()
    
    def start_thinking_animation(self):
        """Start animated thinking indicator"""
        self.thinking_dots = 0
        self.animate_thinking()
    
    def animate_thinking(self):
        """Animate the thinking indicator"""
        if hasattr(self, 'thinking_dots'):
            dots = "." * (self.thinking_dots % 4)
            self.update_status(f"🤔 AI is thinking{dots}", "blue")
            
            # Animate thinking icon
            thinking_emojis = ["🤔", "💭", "⚡", "✨"]
            emoji = thinking_emojis[self.thinking_dots % len(thinking_emojis)]
            self.thinking_icon.config(text=emoji, foreground="#3498db")
            
            self.thinking_dots += 1
            # Schedule next animation frame
            self.root.after(500, self.animate_thinking)
    
    def stop_thinking_animation(self):
        """Stop the thinking animation"""
        if hasattr(self, 'thinking_dots'):
            delattr(self, 'thinking_dots')
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
            self.root.after(0, lambda: self.send_button.config(state="normal", text="Send\n(Enter)"))
    
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

def main():
    """Main function to run the application"""
    root = tk.Tk()
    app = DeepCompanion(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)

if __name__ == "__main__":
    main()
