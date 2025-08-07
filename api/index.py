import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Import the Flask app directly
from app import app as application

# Export for Vercel
app = application
