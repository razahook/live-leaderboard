import sys
import os

# Add the parent directory to Python path so we can import test_server
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from test_server import app as application

# Export for Vercel
app = application
