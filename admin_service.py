from flask import request, jsonify, g
from database import DatabaseService
from auth_middleware import auth_middleware
import logging
import csv
import io
from datetime import datetime

logger = logging.getLogger(__name__)

class AdminService:
    def __init__(self):
        self.db = DatabaseService()
    
    def search_users(self, query: str = None):
        """Search users by email."""
        try:
            if query:
                users = self.db.search_users(query)
            else:
                # Get all users (limit to 100 for performance)
                users_ref = self.db.db.collection('users').limit(100)
                users_docs = users_ref.stream()
                users = [{'uid': doc.id, **doc.to_dict()} for doc in users_docs]
            
            # Remove sensitive data from response
            for user in users:
                user.pop('email', None)  # Keep email for admin
                # Format timestamps for display
                if 'createdAt' in user:
                    user['createdAt'] = user['createdAt'].isoformat() if hasattr(user['createdAt'], 'isoformat') else str(user['createdAt'])
            
            return {
                'success': True,
                'users': users
            }
        
        except Exception as e:
            logger.error(f"Error searching users: {e}")
            return {
                'success': False,
                'error': 'Failed to search users'
            }
    
    def add_credits(self, target_uid: str, amount: int, reason: str):
        """Add credits to a user."""
        try:
            if not target_uid or amount is None:
                return {
                    'success': False,
                    'error': 'User ID and amount are required'
                }
            
            if not isinstance(amount, int) or amount == 0:
                return {
                    'success': False,
                    'error': 'Amount must be a non-zero integer'
                }
            
            if not reason:
                reason = f"Admin adjustment: {amount} credits"
            
            # Check if target user exists
            target_user = self.db.get_user(target_uid)
            if not target_user:
                return {
                    'success': False,
                    'error': 'User not found'
                }
            
            # Add credits
            success = self.db.add_credits(target_uid, amount, g.user_id, reason)
            
            if success:
                # Get updated user info
                updated_user = self.db.get_user(target_uid)
                return {
                    'success': True,
                    'message': f'Added {amount} credits to user',
                    'newBalance': updated_user.get('credits', 0) if updated_user else 0
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to add credits'
                }
        
        except Exception as e:
            logger.error(f"Error adding credits: {e}")
            return {
                'success': False,
                'error': 'System error occurred'
            }
    
    def get_usage_logs(self, user_id: str = None, limit: int = 100):
        """Get usage logs."""
        try:
            logs = self.db.get_usage_logs(user_id, limit)
            
            # Format timestamps for display
            for log in logs:
                if 'timestamp' in log:
                    log['timestamp'] = log['timestamp'].isoformat() if hasattr(log['timestamp'], 'isoformat') else str(log['timestamp'])
            
            return {
                'success': True,
                'logs': logs
            }
        
        except Exception as e:
            logger.error(f"Error getting usage logs: {e}")
            return {
                'success': False,
                'error': 'Failed to retrieve logs'
            }
    
    def export_logs_csv(self, user_id: str = None, limit: int = 1000):
        """Export usage logs as CSV."""
        try:
            logs = self.db.get_usage_logs(user_id, limit)
            
            if not logs:
                return {
                    'success': False,
                    'error': 'No logs found'
                }
            
            # Create CSV
            output = io.StringIO()
            fieldnames = ['timestamp', 'uid', 'endpoint', 'inputPreview', 'resultStatus', 
                         'creditsConsumed', 'adminAction']
            
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            
            for log in logs:
                # Format timestamp
                if 'timestamp' in log:
                    log['timestamp'] = log['timestamp'].isoformat() if hasattr(log['timestamp'], 'isoformat') else str(log['timestamp'])
                
                # Write row
                writer.writerow({
                    field: log.get(field, '') for field in fieldnames
                })
            
            csv_content = output.getvalue()
            output.close()
            
            return {
                'success': True,
                'csv': csv_content,
                'filename': f'usage_logs_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'
            }
        
        except Exception as e:
            logger.error(f"Error exporting logs: {e}")
            return {
                'success': False,
                'error': 'Failed to export logs'
            }
    
    def get_system_health(self):
        """Get system health metrics."""
        try:
            # Get logs from last 24 hours
            from datetime import timedelta
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            
            logs_ref = self.db.db.collection('usage_logs')
            recent_logs = logs_ref.where('timestamp', '>=', cutoff_time).stream()
            
            total_requests = 0
            failed_requests = 0
            provider_failures = 0
            rate_limited = 0
            credits_consumed = 0
            
            for log in recent_logs:
                log_data = log.to_dict()
                total_requests += 1
                
                status = log_data.get('resultStatus', '')
                if 'error' in status or 'failed' in status:
                    failed_requests += 1
                if 'provider_failed' in status:
                    provider_failures += 1
                if 'rate_limited' in status:
                    rate_limited += 1
                
                credits_consumed += log_data.get('creditsConsumed', 0)
            
            return {
                'success': True,
                'metrics': {
                    'totalRequests24h': total_requests,
                    'failedRequests24h': failed_requests,
                    'providerFailures24h': provider_failures,
                    'rateLimitedRequests24h': rate_limited,
                    'creditsConsumed24h': credits_consumed,
                    'successRate': (total_requests - failed_requests) / max(total_requests, 1) * 100,
                    'lastUpdated': datetime.utcnow().isoformat()
                }
            }
        
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {
                'success': False,
                'error': 'Failed to get system health'
            }

# Admin endpoints
def create_admin_routes(app):
    admin_service = AdminService()
    
    # Helper to get the right decorator
    def get_admin_decorator():
        from auth_middleware import auth_middleware
        if auth_middleware:
            return auth_middleware.require_admin
        else:
            return lambda f: f  # No-op decorator for testing
    
    @app.route('/api/admin/users', methods=['POST'])
    @get_admin_decorator()
    def admin_search_users():
        """Search users."""
        data = request.get_json()
        query = data.get('query', '') if data else ''
        
        result = admin_service.search_users(query)
        return jsonify(result)
    
    @app.route('/api/admin/users/<target_uid>/credits', methods=['POST'])
    @get_admin_decorator()
    def admin_add_credits(target_uid):
        """Add credits to a user."""
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Request data required'}), 400
        
        amount = data.get('amount')
        reason = data.get('reason', '')
        
        result = admin_service.add_credits(target_uid, amount, reason)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    
    @app.route('/api/admin/logs', methods=['POST'])
    @get_admin_decorator()
    def admin_get_logs():
        """Get usage logs."""
        data = request.get_json()
        user_id = data.get('userId') if data else None
        limit = data.get('limit', 100) if data else 100
        
        result = admin_service.get_usage_logs(user_id, limit)
        return jsonify(result)
    
    @app.route('/api/admin/logs/export', methods=['POST'])
    @get_admin_decorator()
    def admin_export_logs():
        """Export logs as CSV."""
        data = request.get_json()
        user_id = data.get('userId') if data else None
        limit = data.get('limit', 1000) if data else 1000
        
        result = admin_service.export_logs_csv(user_id, limit)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    
    @app.route('/api/admin/health', methods=['GET'])
    @get_admin_decorator()
    def admin_system_health():
        """Get system health metrics."""
        result = admin_service.get_system_health()
        return jsonify(result)