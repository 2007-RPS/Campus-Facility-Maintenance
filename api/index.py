import sys
import os

# Add parent directory to sys.path so app and db modules can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Expose app for Vercel WSGI runner
app = app
