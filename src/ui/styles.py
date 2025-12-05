import tkinter as tk
from tkinter import ttk
from src.constants import THEME

def setup_styles():
    """Setup ttk styles matching gunsmoke.app theme"""
    style = ttk.Style()
    style.theme_use('clam')
    
    # Configure Treeview
    style.configure('Custom.Treeview',
                   background=THEME['bg_light'],
                   foreground=THEME['text_primary'],
                   fieldbackground=THEME['bg_light'],
                   borderwidth=0,
                   font=('Segoe UI', 10))
    style.configure('Custom.Treeview.Heading',
                   background=THEME['bg_medium'],
                   foreground=THEME['accent_cyan'],
                   borderwidth=1,
                   relief='flat',
                   font=('Segoe UI', 10, 'bold'))
    style.map('Custom.Treeview',
              background=[('selected', THEME['accent_cyan'])],
              foreground=[('selected', THEME['bg_dark'])])
    
    # Configure Notebook (tabs)
    style.configure('Custom.TNotebook',
                   background=THEME['bg_dark'],
                   borderwidth=0)
    style.configure('Custom.TNotebook.Tab',
                   background=THEME['bg_medium'],
                   foreground=THEME['text_secondary'],
                   padding=[12, 6],
                   borderwidth=0,
                   relief='flat',
                   font=('Segoe UI', 11, 'bold'))
    style.map('Custom.TNotebook.Tab',
              background=[('selected', THEME['bg_light'])],
              foreground=[('selected', THEME['accent_cyan'])],
              padding=[('selected', [12, 6])])

def create_button(parent, text, command, bg_color):
    """Create themed button"""
    btn = tk.Button(parent, text=text, command=command,
                   bg=bg_color, fg=THEME['text_primary'],
                   font=("Segoe UI", 10, "bold"),
                   padx=20, pady=10,
                   relief=tk.FLAT,
                   cursor="hand2",
                   activebackground=THEME['accent_hover'],
                   activeforeground=THEME['text_primary'])
    return btn
