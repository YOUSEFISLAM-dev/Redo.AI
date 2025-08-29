import requests
import os
import logging
import time
import uuid
from typing import Dict, Optional
from database import DatabaseService
from rate_limiter import rate_limiter

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self):
        self.db = DatabaseService()
        self.redo_api_key = os.getenv('REDO_AI_API_KEY')
        self.redo_api_url = os.getenv('REDO_AI_API_URL', 'https://api.redo.ai/v1/chat')
        self.max_message_length = int(os.getenv('MAX_MESSAGE_LENGTH', 4096))
        self.credit_policy = os.getenv('CREDIT_POLICY', 'refund_on_provider_failure')
        
        if not self.redo_api_key:
            logger.warning("REDO_AI_API_KEY not set - chat functionality will be limited")
    
    def sanitize_message(self, message: str) -> str:
        """Sanitize and validate user message."""
        if not message:
            raise ValueError("Message cannot be empty")
        
        # Trim whitespace
        message = message.strip()
        
        # Check length
        if len(message) > self.max_message_length:
            raise ValueError(f"Message too long (max {self.max_message_length} characters)")
        
        # Remove control characters except newlines and tabs
        sanitized = ''.join(char for char in message if ord(char) >= 32 or char in '\n\t')
        
        return sanitized
    
    def call_redo_api(self, message: str, conversation_id: str = None) -> Dict:
        """Call REDO AI API and return response."""
        if not self.redo_api_key:
            raise Exception("REDO AI API key not configured")
        
        start_time = time.time()
        
        try:
            headers = {
                'Authorization': f'Bearer {self.redo_api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'message': message,
                'conversation_id': conversation_id
            }
            
            response = requests.post(
                self.redo_api_url,
                json=payload,
                headers=headers,
                timeout=30  # 30 second timeout
            )
            
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)
            
            if response.status_code == 200:
                api_response = response.json()
                return {
                    'success': True,
                    'response': api_response.get('response', 'No response from AI'),
                    'metadata': {
                        'providerStatus': 'success',
                        'latencyMs': latency_ms,
                        'statusCode': response.status_code
                    }
                }
            else:
                logger.error(f"REDO API error {response.status_code}: {response.text}")
                return {
                    'success': False,
                    'error': f"Provider error (status {response.status_code})",
                    'metadata': {
                        'providerStatus': 'error',
                        'latencyMs': latency_ms,
                        'statusCode': response.status_code
                    }
                }
        
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Provider timeout - please try again',
                'metadata': {
                    'providerStatus': 'timeout',
                    'latencyMs': int((time.time() - start_time) * 1000)
                }
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"REDO API request failed: {e}")
            return {
                'success': False,
                'error': 'Provider temporarily unavailable',
                'metadata': {
                    'providerStatus': 'connection_error',
                    'latencyMs': int((time.time() - start_time) * 1000)
                }
            }
        except Exception as e:
            logger.error(f"Unexpected error calling REDO API: {e}")
            return {
                'success': False,
                'error': 'Unexpected error occurred',
                'metadata': {
                    'providerStatus': 'unexpected_error',
                    'latencyMs': int((time.time() - start_time) * 1000)
                }
            }
    
    def process_chat_message(self, user_id: str, message_text: str, ip_address: str, 
                           conversation_id: str = None) -> Dict:
        """
        Process a chat message from start to finish.
        Returns response dict with success/error status.
        """
        try:
            # Generate conversation ID if not provided
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
            
            # Sanitize message
            sanitized_message = self.sanitize_message(message_text)
            
            # Check rate limits
            rate_allowed, rate_error = rate_limiter.check_rate_limit(user_id, ip_address)
            if not rate_allowed:
                self.db.log_usage(
                    uid=user_id,
                    endpoint='chat',
                    input_preview=sanitized_message,
                    result_status='rate_limited',
                    credits_consumed=0
                )
                return {
                    'success': False,
                    'error': rate_error,
                    'error_code': 'RATE_LIMITED'
                }
            
            # Check and deduct credits atomically
            credit_deducted, remaining_credits = self.db.deduct_credit(user_id)
            if not credit_deducted:
                self.db.log_usage(
                    uid=user_id,
                    endpoint='chat',
                    input_preview=sanitized_message,
                    result_status='insufficient_credits',
                    credits_consumed=0
                )
                return {
                    'success': False,
                    'error': 'Insufficient credits',
                    'error_code': 'INSUFFICIENT_CREDITS',
                    'creditsRemaining': remaining_credits
                }
            
            # Record the user's message
            self.db.save_chat_message(
                uid=user_id,
                message_text=sanitized_message,
                role='user',
                conversation_id=conversation_id,
                credit_used=True
            )
            
            # Call AI provider
            ai_response = self.call_redo_api(sanitized_message, conversation_id)
            
            if ai_response['success']:
                # Success - save AI response
                self.db.save_chat_message(
                    uid=user_id,
                    message_text=ai_response['response'],
                    role='assistant',
                    conversation_id=conversation_id,
                    credit_used=False,
                    ai_metadata=ai_response['metadata']
                )
                
                # Record successful request for rate limiting
                rate_limiter.record_request(user_id, ip_address)
                
                # Log successful usage
                self.db.log_usage(
                    uid=user_id,
                    endpoint='chat',
                    input_preview=sanitized_message,
                    result_status='success',
                    credits_consumed=1
                )
                
                return {
                    'success': True,
                    'response': ai_response['response'],
                    'conversationId': conversation_id,
                    'creditsRemaining': remaining_credits,
                    'metadata': ai_response['metadata']
                }
            
            else:
                # Provider failed - handle according to credit policy
                if self.credit_policy == 'refund_on_provider_failure':
                    # Refund the credit
                    self.db.refund_credit(user_id)
                    remaining_credits += 1
                    
                    # Log the refund
                    self.db.log_usage(
                        uid=user_id,
                        endpoint='chat',
                        input_preview=sanitized_message,
                        result_status='provider_failed_refunded',
                        credits_consumed=0
                    )
                    
                    logger.info(f"Refunded credit to user {user_id} due to provider failure")
                
                else:
                    # Consume credit even on failure
                    self.db.log_usage(
                        uid=user_id,
                        endpoint='chat',
                        input_preview=sanitized_message,
                        result_status='provider_failed_consumed',
                        credits_consumed=1
                    )
                
                return {
                    'success': False,
                    'error': ai_response['error'],
                    'error_code': 'PROVIDER_ERROR',
                    'creditsRemaining': remaining_credits,
                    'conversationId': conversation_id
                }
        
        except ValueError as e:
            # Input validation error
            self.db.log_usage(
                uid=user_id,
                endpoint='chat',
                input_preview=message_text[:100] if message_text else '',
                result_status='validation_error',
                credits_consumed=0
            )
            return {
                'success': False,
                'error': str(e),
                'error_code': 'VALIDATION_ERROR'
            }
        
        except Exception as e:
            logger.error(f"Unexpected error in process_chat_message: {e}")
            
            # Try to refund credit if it was deducted
            if 'credit_deducted' in locals() and credit_deducted:
                self.db.refund_credit(user_id)
                logger.info(f"Refunded credit to user {user_id} due to unexpected error")
            
            self.db.log_usage(
                uid=user_id,
                endpoint='chat',
                input_preview=message_text[:100] if message_text else '',
                result_status='system_error',
                credits_consumed=0
            )
            
            return {
                'success': False,
                'error': 'System error - please try again',
                'error_code': 'SYSTEM_ERROR'
            }