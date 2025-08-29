#!/usr/bin/env python3

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up mock environment for testing
os.environ['DEBUG'] = 'true'
os.environ['SECRET_KEY'] = 'test-secret-key'
os.environ['TESTING'] = 'true'
os.environ['FIREBASE_PROJECT_ID'] = 'test-project'
os.environ['FIREBASE_PRIVATE_KEY_ID'] = 'test-key-id'
os.environ['FIREBASE_PRIVATE_KEY'] = '-----BEGIN PRIVATE KEY-----\\ntest-key\\n-----END PRIVATE KEY-----\\n'
os.environ['FIREBASE_CLIENT_EMAIL'] = 'test@test-project.iam.gserviceaccount.com'
os.environ['FIREBASE_CLIENT_ID'] = '123456789'

class TestServerStartup(unittest.TestCase):
    def setUp(self):
        pass
        
    @patch('firebase_admin._apps', {})
    @patch('firebase_admin.initialize_app')
    @patch('firebase_admin.credentials.Certificate')
    @patch('firebase_admin.firestore.client')
    def test_server_imports(self, mock_firestore, mock_cert, mock_init):
        """Test that the server can be imported without errors."""
        try:
            # Mock Firebase initialization
            mock_cert.return_value = MagicMock()
            mock_init.return_value = MagicMock()
            mock_firestore.return_value = MagicMock()
            
            # Import the server module
            import server
            
            # Check that the Flask app was created
            self.assertIsNotNone(server.app)
            self.assertEqual(server.app.name, 'server')
            
            # Test health endpoint
            with server.app.test_client() as client:
                response = client.get('/api/health')
                self.assertEqual(response.status_code, 200)
                data = response.get_json()
                self.assertEqual(data['status'], 'healthy')
                self.assertEqual(data['service'], 'REDO AI Chat')
            
            print("✓ Server startup test passed")
            
        except Exception as e:
            self.fail(f"Server import failed: {e}")
    
    @patch('firebase_admin.firestore.client')
    def test_database_module(self, mock_firestore):
        """Test that the database module can be imported."""
        try:
            mock_firestore.return_value = MagicMock()
            import database
            db_service = database.DatabaseService()
            self.assertIsNotNone(db_service)
            print("✓ Database module test passed")
        except Exception as e:
            self.fail(f"Database module import failed: {e}")
    
    @patch('firebase_admin._apps', {})
    @patch('firebase_admin.initialize_app')
    @patch('firebase_admin.credentials.Certificate')
    def test_auth_middleware_module(self, mock_cert, mock_init):
        """Test that the auth middleware can be imported."""
        try:
            mock_cert.return_value = MagicMock()
            mock_init.return_value = MagicMock()
            import auth_middleware
            # The global instance should be None in test mode
            self.assertIsNone(auth_middleware.auth_middleware)
            # But we can create one manually
            auth = auth_middleware.AuthMiddleware()
            self.assertIsNotNone(auth)
            print("✓ Auth middleware test passed")
        except Exception as e:
            self.fail(f"Auth middleware import failed: {e}")
    
    @patch('firebase_admin.firestore.client')
    def test_chat_service_module(self, mock_firestore):
        """Test that the chat service can be imported."""
        try:
            mock_firestore.return_value = MagicMock()
            import chat_service
            chat = chat_service.ChatService()
            self.assertIsNotNone(chat)
            print("✓ Chat service test passed")
        except Exception as e:
            self.fail(f"Chat service import failed: {e}")
    
    def test_rate_limiter_module(self):
        """Test that the rate limiter can be imported."""
        try:
            import rate_limiter
            limiter = rate_limiter.RateLimiter()
            self.assertIsNotNone(limiter)
            
            # Test basic rate limiting functionality
            user_id = "test-user"
            ip = "127.0.0.1"
            
            # Should allow first request
            allowed, error = limiter.check_rate_limit(user_id, ip)
            self.assertTrue(allowed)
            self.assertEqual(error, "")
            
            print("✓ Rate limiter test passed")
        except Exception as e:
            self.fail(f"Rate limiter import failed: {e}")

if __name__ == '__main__':
    print("Running REDO AI Chat tests...")
    unittest.main(verbosity=2)