// Firebase configuration - replace with your actual config
const firebaseConfig = {
    apiKey: "your-api-key",
    authDomain: "your-project.firebaseapp.com",
    projectId: "your-project-id",
    storageBucket: "your-project.appspot.com",
    messagingSenderId: "123456789",
    appId: "your-app-id"
};

// Initialize Firebase
firebase.initializeApp(firebaseConfig);
const auth = firebase.auth();

class AuthManager {
    constructor() {
        this.currentUser = null;
        this.onAuthStateChanged = null;
        this.setupAuthStateListener();
        this.setupEventListeners();
    }
    
    setupAuthStateListener() {
        auth.onAuthStateChanged((user) => {
            this.currentUser = user;
            if (this.onAuthStateChanged) {
                this.onAuthStateChanged(user);
            }
        });
    }
    
    setupEventListeners() {
        // Auth form submission
        document.getElementById('auth-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleAuthSubmit();
        });
        
        // Auth tab switching
        document.getElementById('signin-tab').addEventListener('click', () => {
            this.switchToSignIn();
        });
        
        document.getElementById('signup-tab').addEventListener('click', () => {
            this.switchToSignUp();
        });
        
        // Sign out button
        document.getElementById('sign-out-btn').addEventListener('click', () => {
            this.signOut();
        });
    }
    
    switchToSignIn() {
        document.getElementById('signin-tab').classList.add('active');
        document.getElementById('signup-tab').classList.remove('active');
        document.getElementById('confirm-password-group').style.display = 'none';
        document.getElementById('auth-submit').textContent = 'Sign In';
        document.getElementById('confirm-password').required = false;
        this.hideError();
    }
    
    switchToSignUp() {
        document.getElementById('signup-tab').classList.add('active');
        document.getElementById('signin-tab').classList.remove('active');
        document.getElementById('confirm-password-group').style.display = 'block';
        document.getElementById('auth-submit').textContent = 'Sign Up';
        document.getElementById('confirm-password').required = true;
        this.hideError();
    }
    
    async handleAuthSubmit() {
        const email = document.getElementById('email').value.trim();
        const password = document.getElementById('password').value;
        const confirmPassword = document.getElementById('confirm-password').value;
        const isSignUp = document.getElementById('signup-tab').classList.contains('active');
        
        // Validation
        if (!email || !password) {
            this.showError('Please fill in all fields');
            return;
        }
        
        if (password.length < 6) {
            this.showError('Password must be at least 6 characters');
            return;
        }
        
        if (isSignUp && password !== confirmPassword) {
            this.showError('Passwords do not match');
            return;
        }
        
        try {
            document.getElementById('auth-submit').disabled = true;
            document.getElementById('auth-submit').textContent = isSignUp ? 'Creating Account...' : 'Signing In...';
            
            if (isSignUp) {
                await this.signUp(email, password);
            } else {
                await this.signIn(email, password);
            }
        } catch (error) {
            this.showError(this.getFirebaseErrorMessage(error));
            document.getElementById('auth-submit').disabled = false;
            document.getElementById('auth-submit').textContent = isSignUp ? 'Sign Up' : 'Sign In';
        }
    }
    
    async signIn(email, password) {
        const result = await auth.signInWithEmailAndPassword(email, password);
        
        if (!result.user.emailVerified) {
            this.showEmailVerificationMessage();
            await auth.signOut();
            return;
        }
        
        // Success will be handled by onAuthStateChanged
    }
    
    async signUp(email, password) {
        const result = await auth.createUserWithEmailAndPassword(email, password);
        
        // Send verification email
        await result.user.sendEmailVerification();
        
        this.showEmailVerificationMessage();
        await auth.signOut();
    }
    
    async signOut() {
        try {
            await auth.signOut();
            // Clear any cached data
            localStorage.removeItem('userToken');
            // Reload page to reset state
            window.location.reload();
        } catch (error) {
            console.error('Sign out error:', error);
        }
    }
    
    async getCurrentUserToken() {
        if (!this.currentUser) {
            return null;
        }
        
        try {
            // Force refresh to ensure we have a valid token
            const token = await this.currentUser.getIdToken(true);
            return token;
        } catch (error) {
            console.error('Error getting user token:', error);
            return null;
        }
    }
    
    showError(message) {
        const errorDiv = document.getElementById('auth-error');
        errorDiv.textContent = message;
        errorDiv.classList.remove('hidden');
    }
    
    hideError() {
        document.getElementById('auth-error').classList.add('hidden');
    }
    
    showEmailVerificationMessage() {
        document.getElementById('email-verification-message').classList.remove('hidden');
        this.hideError();
    }
    
    getFirebaseErrorMessage(error) {
        switch (error.code) {
            case 'auth/user-not-found':
                return 'No account found with this email address';
            case 'auth/wrong-password':
                return 'Incorrect password';
            case 'auth/email-already-in-use':
                return 'An account with this email already exists';
            case 'auth/weak-password':
                return 'Password is too weak';
            case 'auth/invalid-email':
                return 'Invalid email address';
            case 'auth/too-many-requests':
                return 'Too many failed attempts. Please try again later';
            case 'auth/network-request-failed':
                return 'Network error. Please check your connection';
            default:
                return error.message || 'An error occurred. Please try again';
        }
    }
    
    // Check if user is authenticated and email is verified
    isAuthenticated() {
        return this.currentUser && this.currentUser.emailVerified;
    }
    
    // Get user info
    getUserInfo() {
        if (!this.currentUser) {
            return null;
        }
        
        return {
            uid: this.currentUser.uid,
            email: this.currentUser.email,
            displayName: this.currentUser.displayName || this.currentUser.email.split('@')[0],
            emailVerified: this.currentUser.emailVerified
        };
    }
}

// Create global auth manager instance
const authManager = new AuthManager();