from flask import Blueprint, jsonify, request
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import time
import os
import json
from functools import wraps
from collections import defaultdict
import sys
import logging
from typing import Any, Callable, Dict, List, Optional

# ...rest of the code from the original file...
# ...existing code from c:\Users\john\Desktop\apex leaderbaord project\test\routes\leaderboard_scraper.py...
