class ChatManager {
    constructor() {
        this.currentConversationId = null;
        this.conversations = [];
        this.userInfo = null;
        this.isLoading = false;
        
        this.setupEventListeners();
        this.setupMarkdownRenderer();
    }
    
    setupEventListeners() {
        // Send button
        document.getElementById('send-btn').addEventListener('click', () => {
            this.sendMessage();
        });
        
        // Chat input
        const chatInput = document.getElementById('chat-input');
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        chatInput.addEventListener('input', () => {
            this.updateCharacterCount();
            this.autoResizeTextarea();
            this.updateSendButton();
        });
        
        // New chat button
        document.getElementById('new-chat-btn').addEventListener('click', () => {
            this.startNewChat();
        });
        
        // Share chat button
        document.getElementById('share-chat-btn').addEventListener('click', () => {
            this.shareCurrentChat();
        });
    }
    
    setupMarkdownRenderer() {
        // Configure marked.js for safe rendering
        marked.setOptions({
            breaks: true,
            gfm: true,
            sanitize: false, // We'll use DOMPurify instead
            highlight: function(code, lang) {
                // Simple syntax highlighting placeholder
                return `<pre><code class="language-${lang}">${code}</code></pre>`;
            }
        });
    }
    
    async initialize(userInfo) {
        this.userInfo = userInfo;
        await this.loadConversations();
        this.updateUI();
    }
    
    async loadConversations() {
        try {
            const token = await authManager.getCurrentUserToken();
            if (!token) return;
            
            const response = await fetch('/api/conversations', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ idToken: token })
            });
            
            const data = await response.json();
            if (data.success) {
                this.conversations = data.conversations.sort((a, b) => 
                    new Date(b.lastUpdate) - new Date(a.lastUpdate)
                );
                this.renderConversationsList();
            }
        } catch (error) {
            console.error('Error loading conversations:', error);
        }
    }
    
    renderConversationsList() {
        const conversationsList = document.getElementById('conversations-list');
        conversationsList.innerHTML = '';
        
        if (this.conversations.length === 0) {
            conversationsList.innerHTML = '<div class="no-conversations">No conversations yet. Start a new chat!</div>';
            return;
        }
        
        this.conversations.forEach(conversation => {
            const item = document.createElement('div');
            item.className = 'conversation-item';
            item.dataset.conversationId = conversation.conversationId;
            
            // Get first user message as title
            const firstUserMessage = conversation.messages.find(m => m.role === 'user');
            const title = firstUserMessage ? 
                firstUserMessage.messageText.substring(0, 50) + (firstUserMessage.messageText.length > 50 ? '...' : '') :
                'New Conversation';
            
            // Get last message as preview
            const lastMessage = conversation.messages[conversation.messages.length - 1];
            const preview = lastMessage ? 
                lastMessage.messageText.substring(0, 80) + (lastMessage.messageText.length > 80 ? '...' : '') :
                '';
            
            item.innerHTML = `
                <div class="conversation-title">${this.escapeHtml(title)}</div>
                <div class="conversation-preview">${this.escapeHtml(preview)}</div>
            `;
            
            item.addEventListener('click', () => {
                this.loadConversation(conversation.conversationId);
            });
            
            conversationsList.appendChild(item);
        });
    }
    
    loadConversation(conversationId) {
        const conversation = this.conversations.find(c => c.conversationId === conversationId);
        if (!conversation) return;
        
        this.currentConversationId = conversationId;
        this.renderMessages(conversation.messages);
        this.updateActiveConversation();
        
        // Show share button if conversation has messages
        const shareBtn = document.getElementById('share-chat-btn');
        if (conversation.messages.length > 0) {
            shareBtn.classList.remove('hidden');
        } else {
            shareBtn.classList.add('hidden');
        }
        
        // Update chat title
        const firstUserMessage = conversation.messages.find(m => m.role === 'user');
        const title = firstUserMessage ? 
            firstUserMessage.messageText.substring(0, 30) + (firstUserMessage.messageText.length > 30 ? '...' : '') :
            'Chat';
        document.getElementById('chat-title').textContent = title;
    }
    
    updateActiveConversation() {
        document.querySelectorAll('.conversation-item').forEach(item => {
            if (item.dataset.conversationId === this.currentConversationId) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    }
    
    renderMessages(messages) {
        const chatMessages = document.getElementById('chat-messages');
        chatMessages.innerHTML = '';
        
        if (messages.length === 0) {
            chatMessages.innerHTML = `
                <div class="welcome-message">
                    <h3>Start a conversation!</h3>
                    <p>Type your message below to begin chatting with the AI.</p>
                </div>
            `;
            return;
        }
        
        messages.forEach(message => {
            this.addMessageToUI(message);
        });
        
        this.scrollToBottom();
    }
    
    addMessageToUI(message) {
        const chatMessages = document.getElementById('chat-messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${message.role}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        if (message.role === 'assistant') {
            // Render markdown for AI messages
            const htmlContent = marked.parse(message.messageText);
            const sanitizedContent = DOMPurify.sanitize(htmlContent, {
                ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'code', 'pre', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote'],
                ALLOWED_ATTR: ['class']
            });
            contentDiv.innerHTML = sanitizedContent;
        } else {
            // Plain text for user messages
            contentDiv.textContent = message.messageText;
        }
        
        messageDiv.appendChild(contentDiv);
        
        // Add timestamp if available
        if (message.timestamp) {
            const timestampDiv = document.createElement('div');
            timestampDiv.className = 'message-timestamp';
            const date = new Date(message.timestamp);
            timestampDiv.textContent = date.toLocaleTimeString();
            messageDiv.appendChild(timestampDiv);
        }
        
        chatMessages.appendChild(messageDiv);
    }
    
    startNewChat() {
        this.currentConversationId = null;
        this.renderMessages([]);
        document.getElementById('chat-title').textContent = 'New Chat';
        document.getElementById('share-chat-btn').classList.add('hidden');
        
        // Clear active conversation
        document.querySelectorAll('.conversation-item').forEach(item => {
            item.classList.remove('active');
        });
        
        // Focus on input
        document.getElementById('chat-input').focus();
    }
    
    async sendMessage() {
        if (this.isLoading) return;
        
        const chatInput = document.getElementById('chat-input');
        const messageText = chatInput.value.trim();
        
        if (!messageText) return;
        
        // Check if user has credits
        if (this.userInfo.credits < 1) {
            this.showNotification('Insufficient credits. Please contact an administrator to add credits.', 'error');
            return;
        }
        
        // Disable input
        this.setLoading(true);
        chatInput.value = '';
        this.updateCharacterCount();
        this.updateSendButton();
        
        // Add user message to UI immediately
        const userMessage = {
            messageText: messageText,
            role: 'user',
            timestamp: new Date().toISOString()
        };
        this.addMessageToUI(userMessage);
        this.scrollToBottom();
        
        // Show typing indicator
        this.showTypingIndicator();
        
        try {
            const token = await authManager.getCurrentUserToken();
            if (!token) {
                throw new Error('Authentication required');
            }
            
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    idToken: token,
                    messageText: messageText,
                    conversationId: this.currentConversationId
                })
            });
            
            const data = await response.json();
            
            // Remove typing indicator
            this.hideTypingIndicator();
            
            if (data.success) {
                // Update conversation ID if this was a new chat
                if (!this.currentConversationId) {
                    this.currentConversationId = data.conversationId;
                }
                
                // Add AI response to UI
                const aiMessage = {
                    messageText: data.response,
                    role: 'assistant',
                    timestamp: new Date().toISOString()
                };
                this.addMessageToUI(aiMessage);
                
                // Update credits
                this.userInfo.credits = data.creditsRemaining;
                this.updateCreditsDisplay();
                
                // Reload conversations to get updated list
                await this.loadConversations();
                
                // Update chat title for new conversations
                if (document.getElementById('chat-title').textContent === 'New Chat') {
                    const title = messageText.substring(0, 30) + (messageText.length > 30 ? '...' : '');
                    document.getElementById('chat-title').textContent = title;
                }
                
                // Show share button
                document.getElementById('share-chat-btn').classList.remove('hidden');
                
            } else {
                // Handle error
                let errorMessage = data.error || 'An error occurred';
                
                if (data.error_code === 'INSUFFICIENT_CREDITS') {
                    errorMessage = 'Insufficient credits. Please contact an administrator to add credits.';
                    this.userInfo.credits = data.creditsRemaining || 0;
                    this.updateCreditsDisplay();
                } else if (data.error_code === 'RATE_LIMITED') {
                    errorMessage = 'Rate limit exceeded. Please wait before sending another message.';
                } else if (data.error_code === 'PROVIDER_ERROR') {
                    errorMessage = 'AI service temporarily unavailable. Please try again.';
                    // Update credits if they were refunded
                    if (data.creditsRemaining !== undefined) {
                        this.userInfo.credits = data.creditsRemaining;
                        this.updateCreditsDisplay();
                    }
                }
                
                this.showNotification(errorMessage, 'error');
                
                // Remove the user message if it was a validation error
                if (data.error_code === 'VALIDATION_ERROR') {
                    const messages = document.querySelectorAll('.message');
                    const lastMessage = messages[messages.length - 1];
                    if (lastMessage && lastMessage.classList.contains('user')) {
                        lastMessage.remove();
                    }
                }
            }
            
        } catch (error) {
            console.error('Error sending message:', error);
            this.hideTypingIndicator();
            this.showNotification('Connection error. Please try again.', 'error');
            
            // Remove the user message on connection error
            const messages = document.querySelectorAll('.message');
            const lastMessage = messages[messages.length - 1];
            if (lastMessage && lastMessage.classList.contains('user')) {
                lastMessage.remove();
            }
        } finally {
            this.setLoading(false);
            this.scrollToBottom();
        }
    }
    
    showTypingIndicator() {
        const chatMessages = document.getElementById('chat-messages');
        const typingDiv = document.createElement('div');
        typingDiv.className = 'typing-indicator';
        typingDiv.id = 'typing-indicator';
        typingDiv.innerHTML = `
            AI is typing
            <div class="typing-dots">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
        chatMessages.appendChild(typingDiv);
        this.scrollToBottom();
    }
    
    hideTypingIndicator() {
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }
    
    setLoading(loading) {
        this.isLoading = loading;
        const sendBtn = document.getElementById('send-btn');
        const chatInput = document.getElementById('chat-input');
        
        sendBtn.disabled = loading;
        chatInput.disabled = loading;
        
        if (loading) {
            sendBtn.innerHTML = '<div class="loading-spinner" style="width: 16px; height: 16px;"></div>';
        } else {
            sendBtn.innerHTML = '<span class="send-icon">→</span>';
        }
        
        this.updateSendButton();
    }
    
    updateCharacterCount() {
        const chatInput = document.getElementById('chat-input');
        const characterCount = document.querySelector('.character-count');
        const length = chatInput.value.length;
        characterCount.textContent = `${length}/4096`;
        
        if (length > 3900) {
            characterCount.style.color = '#ef4444';
        } else if (length > 3500) {
            characterCount.style.color = '#f59e0b';
        } else {
            characterCount.style.color = '#6b7280';
        }
    }
    
    autoResizeTextarea() {
        const chatInput = document.getElementById('chat-input');
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
    }
    
    updateSendButton() {
        const chatInput = document.getElementById('chat-input');
        const sendBtn = document.getElementById('send-btn');
        const hasText = chatInput.value.trim().length > 0;
        const hasCredits = this.userInfo && this.userInfo.credits > 0;
        
        sendBtn.disabled = !hasText || !hasCredits || this.isLoading;
    }
    
    updateCreditsDisplay() {
        document.getElementById('credits-count').textContent = this.userInfo.credits;
    }
    
    scrollToBottom() {
        const chatMessages = document.getElementById('chat-messages');
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    async shareCurrentChat() {
        if (!this.currentConversationId) return;
        
        try {
            // For now, just copy the conversation ID to clipboard
            await navigator.clipboard.writeText(`Conversation ID: ${this.currentConversationId}`);
            this.showNotification('Conversation ID copied to clipboard!', 'success');
        } catch (error) {
            console.error('Error sharing chat:', error);
            this.showNotification('Failed to copy conversation ID', 'error');
        }
    }
    
    showNotification(message, type = 'info') {
        const notifications = document.getElementById('notifications');
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        notifications.appendChild(notification);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 5000);
    }
    
    updateUI() {
        // Update user display name
        document.getElementById('user-display-name').textContent = this.userInfo.displayName;
        
        // Update credits display
        this.updateCreditsDisplay();
        
        // Show admin panel button if user is admin
        if (this.userInfo.isAdmin) {
            document.getElementById('admin-panel-btn').classList.remove('hidden');
        }
        
        // Update send button state
        this.updateSendButton();
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Create global chat manager instance
const chatManager = new ChatManager();