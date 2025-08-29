// Main application controller
class App {
    constructor() {
        this.currentScreen = 'loading';
        this.userInfo = null;
        this.init();
    }
    
    async init() {
        // Set up auth state listener
        authManager.onAuthStateChanged = (user) => {
            this.handleAuthStateChange(user);
        };
        
        // Set up UI event listeners
        this.setupUIEventListeners();
        
        // Initial screen setup
        await this.checkAuthState();
    }
    
    setupUIEventListeners() {
        // User menu dropdown
        document.getElementById('user-menu-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleUserDropdown();
        });
        
        // Close dropdown when clicking outside
        document.addEventListener('click', () => {
            this.closeUserDropdown();
        });
        
        // Prevent dropdown from closing when clicking inside
        document.getElementById('user-dropdown').addEventListener('click', (e) => {
            e.stopPropagation();
        });
        
        // Handle keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Escape key to close admin panel
            if (e.key === 'Escape' && adminManager.isVisible) {
                adminManager.hideAdminPanel();
            }
        });
    }
    
    async checkAuthState() {
        // Wait a bit for Firebase to initialize
        setTimeout(() => {
            const user = firebase.auth().currentUser;
            this.handleAuthStateChange(user);
        }, 1000);
    }
    
    async handleAuthStateChange(user) {
        if (user && user.emailVerified) {
            // User is signed in and verified
            await this.initializeApp(user);
        } else if (user && !user.emailVerified) {
            // User is signed in but not verified
            this.showAuthScreen();
            document.getElementById('email-verification-message').classList.remove('hidden');
        } else {
            // User is not signed in
            this.showAuthScreen();
        }
    }
    
    async initializeApp(user) {
        try {
            // Get user info from backend
            const token = await authManager.getCurrentUserToken();
            if (!token) {
                this.showAuthScreen();
                return;
            }
            
            const response = await fetch('/api/user/info', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ idToken: token })
            });
            
            if (!response.ok) {
                throw new Error('Failed to get user info');
            }
            
            const userInfo = await response.json();
            this.userInfo = userInfo;
            
            // Initialize chat manager
            await chatManager.initialize(userInfo);
            
            // Show main app
            this.showChatApp();
            
            // Load rate limit info
            await this.loadRateLimitInfo();
            
        } catch (error) {
            console.error('Error initializing app:', error);
            this.showAuthScreen();
            this.showNotification('Failed to load user data. Please try signing in again.', 'error');
        }
    }
    
    async loadRateLimitInfo() {
        try {
            const token = await authManager.getCurrentUserToken();
            if (!token) return;
            
            const response = await fetch('/api/user/rate-limit', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ idToken: token })
            });
            
            const data = await response.json();
            if (data.success) {
                this.updateRateLimitDisplay(data.rateLimits);
            }
        } catch (error) {
            console.error('Error loading rate limit info:', error);
        }
    }
    
    updateRateLimitDisplay(rateLimits) {
        const rateLimitInfo = document.getElementById('rate-limit-info');
        
        if (!rateLimits.can_send) {
            if (rateLimits.messages_last_30s >= rateLimits.max_messages_30s) {
                rateLimitInfo.textContent = `Rate limited: ${rateLimits.messages_last_30s}/${rateLimits.max_messages_30s} messages in 30s`;
                rateLimitInfo.style.color = '#ef4444';
            } else if (rateLimits.messages_today >= rateLimits.max_messages_daily) {
                rateLimitInfo.textContent = `Daily limit reached: ${rateLimits.messages_today}/${rateLimits.max_messages_daily} messages`;
                rateLimitInfo.style.color = '#ef4444';
            }
        } else {
            rateLimitInfo.textContent = `${rateLimits.messages_today}/${rateLimits.max_messages_daily} daily messages`;
            rateLimitInfo.style.color = '#6b7280';
        }
    }
    
    showLoadingScreen() {
        this.currentScreen = 'loading';
        document.getElementById('loading-screen').classList.remove('hidden');
        document.getElementById('auth-screen').classList.add('hidden');
        document.getElementById('chat-app').classList.add('hidden');
    }
    
    showAuthScreen() {
        this.currentScreen = 'auth';
        document.getElementById('loading-screen').classList.add('hidden');
        document.getElementById('auth-screen').classList.remove('hidden');
        document.getElementById('chat-app').classList.add('hidden');
        
        // Clear verification message unless user is unverified
        const user = firebase.auth().currentUser;
        if (!user || user.emailVerified) {
            document.getElementById('email-verification-message').classList.add('hidden');
        }
        
        // Focus on email input
        setTimeout(() => {
            document.getElementById('email').focus();
        }, 100);
    }
    
    showChatApp() {
        this.currentScreen = 'chat';
        document.getElementById('loading-screen').classList.add('hidden');
        document.getElementById('auth-screen').classList.add('hidden');
        document.getElementById('chat-app').classList.remove('hidden');
        
        // Focus on chat input
        setTimeout(() => {
            document.getElementById('chat-input').focus();
        }, 100);
    }
    
    toggleUserDropdown() {
        const dropdown = document.getElementById('user-dropdown');
        dropdown.classList.toggle('hidden');
    }
    
    closeUserDropdown() {
        document.getElementById('user-dropdown').classList.add('hidden');
    }
    
    showNotification(message, type = 'info') {
        if (chatManager) {
            chatManager.showNotification(message, type);
        } else {
            // Fallback if chat manager not initialized
            console.log(`${type.toUpperCase()}: ${message}`);
        }
    }
    
    // Handle offline/online status
    handleOnlineStatus() {
        window.addEventListener('online', () => {
            this.showNotification('Connection restored', 'success');
        });
        
        window.addEventListener('offline', () => {
            this.showNotification('Connection lost - some features may not work', 'warning');
        });
    }
    
    // Handle visibility changes (tab switching)
    handleVisibilityChange() {
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && this.currentScreen === 'chat') {
                // Refresh rate limit info when user returns to tab
                this.loadRateLimitInfo();
            }
        });
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
    
    // Set up additional event listeners
    app.handleOnlineStatus();
    app.handleVisibilityChange();
    
    // Handle beforeunload for unsaved changes
    window.addEventListener('beforeunload', (e) => {
        // You could warn about unsaved messages here if needed
        // For now, just let the user leave
    });
    
    // Service worker registration for PWA capabilities (optional)
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js').catch(err => {
            console.log('Service worker registration failed:', err);
        });
    }
});