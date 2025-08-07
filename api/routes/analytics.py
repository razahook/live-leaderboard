from flask import Blueprint, request, jsonify, session
from models.user import db
from models.analytics import AnalyticsEvent, AnalyticsSummary, StreamerPopularity
from datetime import datetime, date, timedelta
from sqlalchemy import func, desc, text
import uuid
import logging
from functools import wraps
import time

analytics_bp = Blueprint('analytics', __name__)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ...rest of the code from the original file...
# ...existing code from c:\Users\john\Desktop\apex leaderbaord project\test\routes\analytics.py...
