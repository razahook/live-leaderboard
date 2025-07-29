from flask import Flask
from flask_cors import CORS
from src.routes.leaderboard_scraper import leaderboard_bp
from src.models import init_app as init_db

app = Flask(__name__)
CORS(app)
init_db(app)
app.register_blueprint(leaderboard_bp)
