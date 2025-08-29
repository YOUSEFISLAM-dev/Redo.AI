import firebase_admin
from firebase_admin import credentials, auth
from functools import wraps
from flask import request, jsonify, g
import logging
import os

logger = logging.getLogger(__name__)

class AuthMiddleware:
    def __init__(self):
        # Initialize Firebase Admin if not already done
        if not firebase_admin._apps:
            try:
                # Try to use service account file first
                if os.path.exists('firebase-config.json'):
                    cred = credentials.Certificate('firebase-config.json')
                else:
                    # Use environment variables
                    private_key = os.getenv('FIREBASE_PRIVATE_KEY')
                    if not private_key:
                        raise ValueError("FIREBASE_PRIVATE_KEY environment variable is required")
                    
                    cred = credentials.Certificate({
                        "type": "service_account",
                        "project_id": os.getenv('FIREBASE_PROJECT_ID'),
                        "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID'),
                        "private_key": private_key.replace('\\n', '\n'),
                        "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
                        "client_id": os.getenv('FIREBASE_CLIENT_ID'),
                        "auth_uri": os.getenv('FIREBASE_AUTH_URI', 'https://accounts.google.com/o/oauth2/auth'),
                        "token_uri": os.getenv('FIREBASE_TOKEN_URI', 'https://oauth2.googleapis.com/token'),
                    })
                
                firebase_admin.initialize_app(cred)
                logger.info("Firebase Admin initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Firebase Admin: {e}")
                raise
    
    def verify_token(self, id_token: str) -> dict:
        """Verify Firebase ID token and return decoded token."""
        try:
            decoded_token = auth.verify_id_token(id_token)
            return decoded_token
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            return None
    
    def require_auth(self, f):
        """Decorator to require valid Firebase authentication."""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # Get token from request
                data = request.get_json()
                if not data or 'idToken' not in data:
                    return jsonify({'error': 'ID token required'}), 401
                
                id_token = data['idToken']
                decoded_token = self.verify_token(id_token)
                
                if not decoded_token:
                    return jsonify({'error': 'Invalid or expired token'}), 401
                
                # Check if email is verified
                if not decoded_token.get('email_verified', False):
                    return jsonify({'error': 'Email not verified'}), 403
                
                # Store user info in Flask's g object
                g.user_id = decoded_token['uid']
                g.user_email = decoded_token.get('email')
                g.user_claims = decoded_token
                
                return f(*args, **kwargs)
            except Exception as e:
                logger.error(f"Auth middleware error: {e}")
                return jsonify({'error': 'Authentication failed'}), 401
        
        return decorated_function
    
    def require_admin(self, f):
        """Decorator to require admin privileges."""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # First check authentication
            auth_result = self.require_auth(lambda: None)()
            if auth_result:  # If auth failed, return the error
                return auth_result
            
            # Check admin status from database
            from database import DatabaseService
            db = DatabaseService()
            user = db.get_user(g.user_id)
            
            if not user or not user.get('isAdmin', False):
                return jsonify({'error': 'Admin privileges required'}), 403
            
            return f(*args, **kwargs)
        
        return decorated_function

# Global instance - only create if not in test mode
auth_middleware = None
if not os.getenv('TESTING', False):
    try:
        auth_middleware = AuthMiddleware()
    except Exception as e:
        logger.warning(f"Failed to initialize AuthMiddleware: {e}")
        auth_middleware = None