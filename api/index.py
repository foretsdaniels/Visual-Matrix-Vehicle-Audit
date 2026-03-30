"""Vercel serverless entry point for the FastAPI application."""
import os
import sys

# Add the project root to the path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Set environment variables for serverless environment
os.environ["DATA_DIR"] = "/tmp/data"
os.environ["VERCEL"] = "1"

# Create necessary directories before importing app
os.makedirs("/tmp/data", exist_ok=True)
os.makedirs("/tmp/data/artifacts", exist_ok=True)
os.makedirs("/tmp/data/uploads", exist_ok=True)
os.makedirs("/tmp/data/logs", exist_ok=True)

from app.main import app

# Vercel expects the app to be named 'app' or 'handler'
# FastAPI apps work directly with @vercel/python
