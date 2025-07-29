import os
import sys
from flask import Flask
from flask_cors import CORS

# Allows this file to find and import code from your 'src' folder
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.routes.twitch_override import twitch_override_bp
from src.models import init_app as init_db

app = Flask(__name__)
CORS(app)
init_db(app)

# Register the blueprint for Twitch overrides
app.register_blueprint(twitch_override_bp, url_prefix='/api')
