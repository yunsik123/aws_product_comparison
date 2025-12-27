"""AWS Lambda handler using Mangum adapter for FastAPI."""
from mangum import Mangum
from app.main import app

# Create Lambda handler
handler = Mangum(app, lifespan="off")
