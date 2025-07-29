import os
import sys
from flask import Flask
from flask_cors import CORS

# CORRECTED: This robustly adds the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.routes.twitch_override import twitch_override_bp
from src.models import init_app as init_db

app = Flask(__name__)
CORS(app)
init_db(app)

# CORRECTED: Removed the redundant url_prefix
app.register_blueprint(twitch_override_bp)
