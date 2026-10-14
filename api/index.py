import sys
import os
from urllib.parse import parse_qs, urlencode

# Add parent directory to sys.path so app and db modules can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

class VercelPathMiddleware:
    """Restores the true requested path when Vercel rewrites forward with __url query parameter."""
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        qs = environ.get("QUERY_STRING", "")
        if "__url" in qs:
            params = parse_qs(qs, keep_blank_values=True)
            if "__url" in params:
                req_path = params.pop("__url")[0]
                if not req_path.startswith("/"):
                    req_path = "/" + req_path
                environ["PATH_INFO"] = req_path
                environ["QUERY_STRING"] = urlencode(params, doseq=True)
        elif environ.get("PATH_INFO") in ("/api/index", "/api/index.py"):
            environ["PATH_INFO"] = "/"
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathMiddleware(app.wsgi_app)
