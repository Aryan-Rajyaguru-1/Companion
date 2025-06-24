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
            "chat": {
                "name": "llama3.2:3b",
                "display_name": "Llama 3.2 (Chat)",
                "description": "Natural conversation and general assistance",
                "emoji": "💬"
            },
            "conversation": {
                "name": "deepseek-r1:1.5b",
                "display_name": "DeepSeek R1 (Think)",
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
        
        # Current model selection - default to chat for normal conversation
        self.current_model_key = "chat"
        self.model_name = self.models[self.current_model_key]["name"]
        
        # Chat history (separate for each model)
        self.chat_histories = {
            "chat": [],
            "conversation": [],
            "code": [],
            "code_advanced": []
        }
        self.chat_history = self.chat_histories[self.current_model_key]
        
        # Initialize model wrapper for enhanced flow
        self.model_wrapper = ModelWrapper(self)
        
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
        about_text = """🤖 Companion proto-2.1 (Deepthink) v2.1

A modern GUI for local AI model interaction with enhanced model wrapper

Features:
• Three specialized modes with dedicated icons
• Enhanced streaming with smooth output flow
• Intelligent response buffering and performance metrics
• Model-specific optimizations and error handling
• Separate chat histories per mode
• Code-specific tools and formatting
• Keyboard shortcuts for efficiency
• Interactive status icons and animations

Modes:
💬 Chat Mode - Llama 3.2 3B for natural conversation & assistance
🤔 Think Mode - DeepSeek R1 1.5B for reasoning & analysis
💻 Code Mode - CodeGemma 2B for everyday coding
🧠 Advanced Mode - CodeQwen 7B for complex programming

Enhanced Features:
• 🚀 Intelligent response streaming with performance metrics
• ⚡ Model-specific thinking animations and status updates
• 🔧 Advanced error handling with helpful suggestions
• 📊 Real-time response performance monitoring
• 🎯 Context-aware message preparation and optimization

Visual Indicators:
• 💬💭⚡✨🧐💡 - Natural chat indicators
• 🤔💭⚡✨🧐💡 - Enhanced thinking animations per mode
• 💻⚡🔧⚙️🚀 - Code mode indicators
• 🧠🔬⚡💡🎯🔍 - Advanced mode indicators

Optimized for Intel i7-7600U with 8GB RAM

Built with Python & tkinter
Powered by Ollama with enhanced model wrapper"""
        
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
        
        # Mode selection with icons instead of tabs - now 4 models
        modes_container = ttk.Frame(mode_frame)
        modes_container.pack(anchor=tk.CENTER)
        
        # Chat mode button (Llama 3.2 - default)
        self.chat_button = ttk.Button(
            modes_container,
            text="💬 Chat",
            command=lambda: self.switch_model("chat"),
            style='ActiveModel.TButton',
            width=10
        )
        self.chat_button.pack(side=tk.LEFT, padx=(0, 8))
        
        # Think mode button (DeepSeek R1)
        self.think_button = ttk.Button(
            modes_container,
            text="🤔 Think",
            command=lambda: self.switch_model("conversation"),
            style='Model.TButton',
            width=10
        )
        self.think_button.pack(side=tk.LEFT, padx=(0, 8))
        
        # Code mode button (CodeGemma)
        self.code_button = ttk.Button(
            modes_container,
            text="💻 Code",
            command=lambda: self.switch_model("code"),
            style='Model.TButton',
            width=10
        )
        self.code_button.pack(side=tk.LEFT, padx=(0, 8))
        
        # Advanced coding button (CodeQwen)
        self.advanced_button = ttk.Button(
            modes_container,
            text="🧠 Advanced",
            command=lambda: self.switch_model("code_advanced"),
            style='Model.TButton',
            width=10
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
        
        self.chat_status = ttk.Label(self.model_status_frame, 
                                   text="💬 ⏳", 
                                   style='Status.TLabel',
                                   font=('Arial', 8))
        self.chat_status.pack(side=tk.LEFT, padx=(0, 5))
        
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
        self.root.bind('<Control-1>', lambda e: self.switch_model("chat"))
        self.root.bind('<Control-2>', lambda e: self.switch_model("conversation"))
        self.root.bind('<Control-3>', lambda e: self.switch_model("code"))
        self.root.bind('<Control-4>', lambda e: self.switch_model("code_advanced"))
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
        if self.current_model_key == "chat":
            self.coding_icon.config(text="💬", foreground="#27ae60")  # Chat icon
            self.speed_icon.config(text="💭", foreground="green")      # Conversation speed
        elif self.current_model_key == "conversation":
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
        # Reset all buttons to normal style
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
        """Update character counter with enhanced time estimation"""
        text = self.message_entry.get("1.0", tk.END).strip()
        char_count = len(text)
        word_count = len(text.split()) if text else 0
        
        # Enhanced response time estimation using wrapper
        if char_count > 0:
            config = self.model_wrapper.get_model_config(self.current_model_key)
            
            # More sophisticated time estimation based on content type and model
            if self.current_model_key == "chat":
                # Chat mode - natural conversation, moderate speed
                base_time = 2.5
                complexity_factor = word_count * 0.1
                estimated_time = max(2, min(15, base_time + complexity_factor))
                speed_indicator = "💬⚡"
            elif self.current_model_key == "code":
                # Code mode - faster responses, but varies by complexity
                base_time = 2
                complexity_factor = word_count * 0.1  # Code complexity
                estimated_time = max(2, min(12, base_time + complexity_factor))
                speed_indicator = "💻⚡"
            elif self.current_model_key == "code_advanced":
                # Advanced mode - more detailed responses
                base_time = 5
                complexity_factor = word_count * 0.15
                estimated_time = max(5, min(30, base_time + complexity_factor))
                speed_indicator = "🧠🔬"
            else:
                # Think mode - analytical responses
                base_time = 3
                complexity_factor = word_count * 0.12
                estimated_time = max(3, min(20, base_time + complexity_factor))
                speed_indicator = "🤔💭"
            
            # Add context about message complexity
            complexity_hint = ""
            if word_count > 50:
                complexity_hint = " (complex)"
            elif word_count > 20:
                complexity_hint = " (detailed)"
            
            self.char_label.config(text=f"{char_count} chars, {word_count} words (~{estimated_time:.0f}s {speed_indicator}){complexity_hint}")
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
                            if model_key == "chat":
                                self.root.after(0, lambda: self.chat_status.config(text="💬 ✅", foreground="green"))
                            elif model_key == "conversation":
                                self.root.after(0, lambda: self.think_status.config(text="🤔 ✅", foreground="green"))
                            elif model_key == "code":
                                self.root.after(0, lambda: self.code_status.config(text="💻 ✅", foreground="green"))
                            elif model_key == "code_advanced":
                                self.root.after(0, lambda: self.advanced_status.config(text="🧠 ✅", foreground="green"))
                        else:
                            missing_models.append(model_info['display_name'])
                            # Update individual model status
                            if model_key == "chat":
                                self.root.after(0, lambda: self.chat_status.config(text="💬 ❌", foreground="red"))
                            elif model_key == "conversation":
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
                self.root.after(0, lambda: self.chat_status.config(text="💬 ❌", foreground="red"))
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
        
        # Send to Ollama in background thread using wrapper
        threading.Thread(target=self.model_wrapper.get_ollama_response_wrapped, args=(message,), daemon=True).start()
    
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
    app = DeepCompanion(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nGoodbye!")
        sys.exit(0)

if __name__ == "__main__":
    main()
