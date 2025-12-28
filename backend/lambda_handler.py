"""AWS Lambda handler using Mangum adapter for FastAPI."""
import sys
import os

# Ensure app module is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mangum import Mangum
from app.main import app

# Create Lambda handler
handler = Mangum(app, lifespan="off")
