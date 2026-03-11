import sys
import os

# Set the path to the application
sys.path.insert(0, os.path.dirname(__file__))

# Import the FastAPI app
from app.main import app

# Create a wrapper for WSGI (FastAPI uses ASGI, so we need a converter)
try:
    from a2wsgi import ASGIMiddleware
    application = ASGIMiddleware(app)
except ImportError:
    # If a2wsgi is not installed, we'll suggest installing it in the walkthrough
    application = app
