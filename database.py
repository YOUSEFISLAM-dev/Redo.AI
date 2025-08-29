import firebase_admin
from firebase_admin import credentials, firestore, auth
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self):
        self.db = firestore.client()
    
    def get_user(self, uid: str) -> Optional[Dict[str, Any]]:
        """Get user document from Firestore."""
        try:
            user_ref = self.db.collection('users').document(uid)
            user_doc = user_ref.get()
            
            if user_doc.exists:
                return user_doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Error getting user {uid}: {e}")
            return None
    
    def create_user(self, uid: str, email: str, display_name: str = None) -> bool:
        """Create a new user document."""
        try:
            user_data = {
                'email': email,
                'displayName': display_name or email.split('@')[0],
                'credits': 0,
                'isAdmin': False,
                'emailVerified': False,
                'createdAt': datetime.utcnow()
            }
            
            self.db.collection('users').document(uid).set(user_data)
            logger.info(f"Created user document for {uid}")
            return True
        except Exception as e:
            logger.error(f"Error creating user {uid}: {e}")
            return False
    
    def update_email_verified(self, uid: str, verified: bool = True) -> bool:
        """Update user email verification status."""
        try:
            user_ref = self.db.collection('users').document(uid)
            user_ref.update({'emailVerified': verified})
            return True
        except Exception as e:
            logger.error(f"Error updating email verification for {uid}: {e}")
            return False
    
    @firestore.transactional
    def deduct_credit_transaction(self, transaction, uid: str) -> bool:
        """Atomically deduct one credit from user. Returns True if successful."""
        try:
            user_ref = self.db.collection('users').document(uid)
            user_doc = user_ref.get(transaction=transaction)
            
            if not user_doc.exists:
                return False
                
            user_data = user_doc.to_dict()
            current_credits = user_data.get('credits', 0)
            
            if current_credits < 1:
                return False
            
            transaction.update(user_ref, {'credits': current_credits - 1})
            return True
        except Exception as e:
            logger.error(f"Error deducting credit for {uid}: {e}")
            return False
    
    def deduct_credit(self, uid: str) -> tuple[bool, int]:
        """Deduct one credit from user. Returns (success, remaining_credits)."""
        try:
            transaction = self.db.transaction()
            success = self.deduct_credit_transaction(transaction, uid)
            
            if success:
                # Get updated credit count
                user = self.get_user(uid)
                remaining = user.get('credits', 0) if user else 0
                return True, remaining
            else:
                user = self.get_user(uid)
                current = user.get('credits', 0) if user else 0
                return False, current
        except Exception as e:
            logger.error(f"Error in deduct_credit for {uid}: {e}")
            return False, 0
    
    def refund_credit(self, uid: str) -> bool:
        """Add one credit back to user (for provider failures)."""
        try:
            user_ref = self.db.collection('users').document(uid)
            user_ref.update({'credits': firestore.Increment(1)})
            logger.info(f"Refunded 1 credit to user {uid}")
            return True
        except Exception as e:
            logger.error(f"Error refunding credit for {uid}: {e}")
            return False
    
    def save_chat_message(self, uid: str, message_text: str, role: str, 
                         conversation_id: str, credit_used: bool = False, 
                         ai_metadata: Dict = None) -> bool:
        """Save a chat message to user's chat subcollection."""
        try:
            chat_data = {
                'messageText': message_text,
                'role': role,
                'timestamp': datetime.utcnow(),
                'creditUsed': credit_used,
                'conversationId': conversation_id
            }
            
            if ai_metadata:
                chat_data['aiResponseMetadata'] = ai_metadata
            
            self.db.collection('users').document(uid).collection('chats').add(chat_data)
            return True
        except Exception as e:
            logger.error(f"Error saving chat message for {uid}: {e}")
            return False
    
    def get_user_conversations(self, uid: str) -> List[Dict]:
        """Get list of conversations for a user."""
        try:
            chats_ref = self.db.collection('users').document(uid).collection('chats')
            chats = chats_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
            
            conversations = {}
            for chat in chats:
                chat_data = chat.to_dict()
                conv_id = chat_data.get('conversationId')
                if conv_id not in conversations:
                    conversations[conv_id] = {
                        'conversationId': conv_id,
                        'messages': [],
                        'lastUpdate': chat_data.get('timestamp')
                    }
                conversations[conv_id]['messages'].append(chat_data)
            
            return list(conversations.values())
        except Exception as e:
            logger.error(f"Error getting conversations for {uid}: {e}")
            return []
    
    def log_usage(self, uid: str, endpoint: str, input_preview: str, 
                  result_status: str, credits_consumed: int = 0, 
                  admin_action: bool = False) -> bool:
        """Log usage to usage_logs collection."""
        try:
            log_data = {
                'uid': uid,
                'endpoint': endpoint,
                'inputPreview': input_preview[:100] if input_preview else '',
                'resultStatus': result_status,
                'timestamp': datetime.utcnow(),
                'creditsConsumed': credits_consumed,
                'adminAction': admin_action
            }
            
            self.db.collection('usage_logs').add(log_data)
            return True
        except Exception as e:
            logger.error(f"Error logging usage: {e}")
            return False
    
    def get_usage_logs(self, uid: str = None, limit: int = 100) -> List[Dict]:
        """Get usage logs, optionally filtered by user."""
        try:
            logs_ref = self.db.collection('usage_logs')
            
            if uid:
                logs_ref = logs_ref.where('uid', '==', uid)
            
            logs = logs_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(limit).stream()
            return [log.to_dict() for log in logs]
        except Exception as e:
            logger.error(f"Error getting usage logs: {e}")
            return []
    
    def add_credits(self, uid: str, amount: int, admin_uid: str, reason: str) -> bool:
        """Add credits to a user (admin function)."""
        try:
            user_ref = self.db.collection('users').document(uid)
            user_ref.update({'credits': firestore.Increment(amount)})
            
            # Log the admin action
            self.log_usage(
                uid=admin_uid,
                endpoint='admin_add_credits',
                input_preview=f"Added {amount} credits to {uid}: {reason}",
                result_status='success',
                credits_consumed=0,
                admin_action=True
            )
            
            logger.info(f"Admin {admin_uid} added {amount} credits to {uid}")
            return True
        except Exception as e:
            logger.error(f"Error adding credits: {e}")
            return False
    
    def search_users(self, query: str) -> List[Dict]:
        """Search users by email (admin function)."""
        try:
            users_ref = self.db.collection('users')
            users = users_ref.where('email', '>=', query).where('email', '<', query + '\uf8ff').stream()
            return [{'uid': user.id, **user.to_dict()} for user in users]
        except Exception as e:
            logger.error(f"Error searching users: {e}")
            return []