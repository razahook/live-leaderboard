import os
import sys
from flask import Flask
from flask_cors import CORS

# This line is essential. It tells Vercel where to find your 'src' folder
# so that the imports below will work correctly.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- Your Project's Specific Imports ---
# 1. Import the specific set of routes (blueprint) this file will handle.
from src.routes.leaderboard_scraper import leaderboard_bp

# 2. Import the database initializer from your models file.
from src.models import init_app as init_db

# --- Boilerplate for Vercel ---
# This is the standard setup for a Vercel serverless function.
# Vercel will automatically find and run this 'app' object.
app = Flask(__name__)

# Enable CORS to allow your frontend to call this API
CORS(app)

# Initialize the database connection for this function
# This ensures it can talk to your Vercel Postgres DB
init_db(app)

# Register the blueprint. This tells Flask which code to run
# for routes like /api/leaderboard/PC
app.register_blueprint(leaderboard_bp, url_prefix='/api')

# Note: There is no app.run() here. Vercel handles that automatically.
