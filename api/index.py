import sys
import os

# Add parent directory to sys.path so app and db modules can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

class VercelPathMiddleware:
    """
    Middleware to restore the true requested URL path for Flask on Vercel.
    Vercel rewrites forward requests to /api/index, so we restore PATH_INFO
    from HTTP_X_FORWARDED_URI or HTTP_X_MATCHED_PATH.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        original_uri = environ.get("HTTP_X_FORWARDED_URI") or environ.get("HTTP_X_MATCHED_PATH")
        if original_uri:
            path_only = original_uri.split("?")[0]
            if path_only:
                environ["PATH_INFO"] = path_only
        elif environ.get("PATH_INFO", "").startswith("/api/index"):
            environ["PATH_INFO"] = "/"
        return self.wsgi_app(environ, start_response)

# Apply middleware to Flask WSGI app
app.wsgi_app = VercelPathMiddleware(app.wsgi_app)
