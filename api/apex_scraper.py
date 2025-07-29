import os
import sys
from flask import Flask
from flask_cors import CORS

# Allows this file to find and import code from your 'src' folder
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.routes.apex_scraper import apex_scraper_bp
from src.models import init_app as init_db

app = Flask(__name__)
CORS(app)
init_db(app)

# Register the blueprint for the apex scraper (predator points)
app.register_blueprint(apex_scraper_bp, url_prefix='/api')
