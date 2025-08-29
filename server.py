from flask import Flask, request, jsonify, g, send_from_directory
from flask_cors import CORS
import os
import logging
from dotenv import load_dotenv

# Import our services
from auth_middleware import auth_middleware
from chat_service import ChatService
from admin_service import create_admin_routes
from database import DatabaseService

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Enable CORS for development
CORS(app, origins=['http://localhost:3000', 'http://127.0.0.1:3000'])

# Initialize services
chat_service = ChatService() if not os.getenv('TESTING') else None
db_service = DatabaseService() if not os.getenv('TESTING') else None

# Helper function to check if auth middleware is available
def require_auth_decorator(f):
    if auth_middleware:
        return auth_middleware.require_auth(f)
    else:
        # In testing mode, just return the function as-is
        return f

def require_admin_decorator(f):
    if auth_middleware:
        return auth_middleware.require_admin(f)
    else:
        # In testing mode, just return the function as-is
        return f

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'REDO AI Chat'
    })

# Serve main application
@app.route('/')
def index():
    """Serve the main application."""
    return send_from_directory('.', 'index.html')

# User info endpoint
@app.route('/api/user/info', methods=['POST'])
@require_auth_decorator
def get_user_info():
    """Get user information and credits."""
    try:
        user = db_service.get_user(g.user_id)
        
        if not user:
            # Create user if doesn't exist
            success = db_service.create_user(
                uid=g.user_id,
                email=g.user_email,
                display_name=g.user_claims.get('name')
            )
            
            if success:
                # Update email verification status
                db_service.update_email_verified(g.user_id, g.user_claims.get('email_verified', False))
                user = db_service.get_user(g.user_id)
            else:
                return jsonify({'error': 'Failed to create user'}), 500
        else:
            # Update email verification status if needed
            if user.get('emailVerified') != g.user_claims.get('email_verified', False):
                db_service.update_email_verified(g.user_id, g.user_claims.get('email_verified', False))
                user['emailVerified'] = g.user_claims.get('email_verified', False)
        
        return jsonify({
            'uid': g.user_id,
            'email': user.get('email'),
            'displayName': user.get('displayName'),
            'credits': user.get('credits', 0),
            'isAdmin': user.get('isAdmin', False),
            'emailVerified': user.get('emailVerified', False)
        })
    
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        return jsonify({'error': 'Failed to get user information'}), 500

# Chat endpoint
@app.route('/api/chat', methods=['POST'])
@require_auth_decorator
def chat():
    """Send a message to the AI."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request data required'}), 400
        
        message_text = data.get('messageText', '').strip()
        conversation_id = data.get('conversationId')
        
        if not message_text:
            return jsonify({'error': 'Message text required'}), 400
        
        # Get client IP
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        # Process the chat message
        result = chat_service.process_chat_message(
            user_id=g.user_id,
            message_text=message_text,
            ip_address=client_ip,
            conversation_id=conversation_id
        )
        
        if result['success']:
            return jsonify(result)
        else:
            # Return appropriate HTTP status codes
            error_code = result.get('error_code')
            if error_code == 'INSUFFICIENT_CREDITS':
                status_code = 402  # Payment Required
            elif error_code == 'RATE_LIMITED':
                status_code = 429  # Too Many Requests
            elif error_code == 'VALIDATION_ERROR':
                status_code = 400  # Bad Request
            else:
                status_code = 500  # Internal Server Error
            
            return jsonify(result), status_code
    
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'System error occurred',
            'error_code': 'SYSTEM_ERROR'
        }), 500

# Get user conversations
@app.route('/api/conversations', methods=['POST'])
@require_auth_decorator
def get_conversations():
    """Get user's conversations."""
    try:
        conversations = db_service.get_user_conversations(g.user_id)
        
        # Format timestamps for frontend
        for conv in conversations:
            if 'lastUpdate' in conv and conv['lastUpdate']:
                conv['lastUpdate'] = conv['lastUpdate'].isoformat() if hasattr(conv['lastUpdate'], 'isoformat') else str(conv['lastUpdate'])
            
            for message in conv.get('messages', []):
                if 'timestamp' in message and message['timestamp']:
                    message['timestamp'] = message['timestamp'].isoformat() if hasattr(message['timestamp'], 'isoformat') else str(message['timestamp'])
        
        return jsonify({
            'success': True,
            'conversations': conversations
        })
    
    except Exception as e:
        logger.error(f"Error getting conversations: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get conversations'
        }), 500

# Rate limit info
@app.route('/api/user/rate-limit', methods=['POST'])
@require_auth_decorator
def get_rate_limit_info():
    """Get current rate limit status for user."""
    try:
        from rate_limiter import rate_limiter
        stats = rate_limiter.get_user_stats(g.user_id)
        return jsonify({
            'success': True,
            'rateLimits': stats
        })
    except Exception as e:
        logger.error(f"Error getting rate limit info: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get rate limit information'
        }), 500

# Create admin routes
if not os.getenv('TESTING'):
    create_admin_routes(app)

# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

# Development server
if __name__ == '__main__':
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug)