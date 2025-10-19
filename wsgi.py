# This file loads the Flask app instance for the Gunicorn server

from app import app as application

if __name__ == "__main__":
    application.run()