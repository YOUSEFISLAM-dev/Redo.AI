class AdminManager {
    constructor() {
        this.isVisible = false;
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        // Admin panel button
        document.getElementById('admin-panel-btn').addEventListener('click', () => {
            this.showAdminPanel();
        });
        
        // Close admin panel
        document.getElementById('close-admin-btn').addEventListener('click', () => {
            this.hideAdminPanel();
        });
        
        // Search users
        document.getElementById('search-users-btn').addEventListener('click', () => {
            this.searchUsers();
        });
        
        // Search on enter
        document.getElementById('user-search-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                this.searchUsers();
            }
        });
        
        // Load logs
        document.getElementById('load-logs-btn').addEventListener('click', () => {
            this.loadLogs();
        });
        
        // Export logs
        document.getElementById('export-logs-btn').addEventListener('click', () => {
            this.exportLogs();
        });
    }
    
    async showAdminPanel() {
        document.getElementById('admin-panel').classList.remove('hidden');
        this.isVisible = true;
        
        // Load initial data
        await this.loadSystemHealth();
        await this.searchUsers(); // Load all users initially
    }
    
    hideAdminPanel() {
        document.getElementById('admin-panel').classList.add('hidden');
        this.isVisible = false;
    }
    
    async searchUsers() {
        const query = document.getElementById('user-search-input').value.trim();
        
        try {
            const token = await authManager.getCurrentUserToken();
            if (!token) return;
            
            const response = await fetch('/api/admin/users', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    idToken: token,
                    query: query 
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.renderUsersList(data.users);
            } else {
                this.showNotification(data.error || 'Failed to search users', 'error');
            }
        } catch (error) {
            console.error('Error searching users:', error);
            this.showNotification('Connection error while searching users', 'error');
        }
    }
    
    renderUsersList(users) {
        const usersList = document.getElementById('users-list');
        usersList.innerHTML = '';
        
        if (users.length === 0) {
            usersList.innerHTML = '<div class="no-results">No users found</div>';
            return;
        }
        
        users.forEach(user => {
            const userItem = document.createElement('div');
            userItem.className = 'user-item';
            
            userItem.innerHTML = `
                <div class="user-info-admin">
                    <div class="user-email">${this.escapeHtml(user.email || 'No email')}</div>
                    <div class="user-details">
                        Credits: ${user.credits || 0} | 
                        Admin: ${user.isAdmin ? 'Yes' : 'No'} | 
                        Verified: ${user.emailVerified ? 'Yes' : 'No'} |
                        UID: ${user.uid}
                    </div>
                </div>
                <div class="user-actions">
                    <button class="btn btn-primary btn-sm" onclick="adminManager.showAddCreditsDialog('${user.uid}', '${this.escapeHtml(user.email)}')">
                        Add Credits
                    </button>
                    <button class="btn btn-secondary btn-sm" onclick="adminManager.viewUserLogs('${user.uid}')">
                        View Logs
                    </button>
                </div>
            `;
            
            usersList.appendChild(userItem);
        });
    }
    
    async showAddCreditsDialog(userId, userEmail) {
        const amount = prompt(`How many credits to add for ${userEmail}?`);
        if (amount === null) return;
        
        const numAmount = parseInt(amount);
        if (isNaN(numAmount) || numAmount === 0) {
            this.showNotification('Please enter a valid number', 'error');
            return;
        }
        
        const reason = prompt('Reason for credit adjustment:') || 'Admin adjustment';
        
        await this.addCredits(userId, numAmount, reason);
    }
    
    async addCredits(userId, amount, reason) {
        try {
            const token = await authManager.getCurrentUserToken();
            if (!token) return;
            
            const response = await fetch(`/api/admin/users/${userId}/credits`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    idToken: token,
                    amount: amount,
                    reason: reason
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showNotification(`Successfully added ${amount} credits. New balance: ${data.newBalance}`, 'success');
                // Refresh users list
                await this.searchUsers();
            } else {
                this.showNotification(data.error || 'Failed to add credits', 'error');
            }
        } catch (error) {
            console.error('Error adding credits:', error);
            this.showNotification('Connection error while adding credits', 'error');
        }
    }
    
    async loadLogs() {
        const userFilter = document.getElementById('logs-user-filter').value.trim();
        
        try {
            const token = await authManager.getCurrentUserToken();
            if (!token) return;
            
            const response = await fetch('/api/admin/logs', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    idToken: token,
                    userId: userFilter || null,
                    limit: 100
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.renderLogsList(data.logs);
            } else {
                this.showNotification(data.error || 'Failed to load logs', 'error');
            }
        } catch (error) {
            console.error('Error loading logs:', error);
            this.showNotification('Connection error while loading logs', 'error');
        }
    }
    
    renderLogsList(logs) {
        const logsList = document.getElementById('logs-list');
        logsList.innerHTML = '';
        
        if (logs.length === 0) {
            logsList.innerHTML = '<div class="no-results">No logs found</div>';
            return;
        }
        
        logs.forEach(log => {
            const logItem = document.createElement('div');
            logItem.className = 'log-item';
            
            const timestamp = new Date(log.timestamp).toLocaleString();
            const statusColor = this.getStatusColor(log.resultStatus);
            
            logItem.innerHTML = `
                <div class="log-info">
                    <div class="log-primary">
                        <strong>${this.escapeHtml(log.endpoint)}</strong> - 
                        <span style="color: ${statusColor}">${this.escapeHtml(log.resultStatus)}</span>
                    </div>
                    <div class="log-details">
                        User: ${this.escapeHtml(log.uid)} | 
                        Credits: ${log.creditsConsumed || 0} | 
                        Time: ${timestamp}
                        ${log.adminAction ? ' | <strong>Admin Action</strong>' : ''}
                    </div>
                    ${log.inputPreview ? `<div class="log-preview">${this.escapeHtml(log.inputPreview)}</div>` : ''}
                </div>
            `;
            
            logsList.appendChild(logItem);
        });
    }
    
    getStatusColor(status) {
        if (status.includes('success')) return '#10b981';
        if (status.includes('error') || status.includes('failed')) return '#ef4444';
        if (status.includes('rate_limited')) return '#f59e0b';
        return '#6b7280';
    }
    
    async viewUserLogs(userId) {
        document.getElementById('logs-user-filter').value = userId;
        await this.loadLogs();
        
        // Scroll to logs section
        document.querySelector('.admin-section:nth-child(3)').scrollIntoView({
            behavior: 'smooth'
        });
    }
    
    async exportLogs() {
        const userFilter = document.getElementById('logs-user-filter').value.trim();
        
        try {
            const token = await authManager.getCurrentUserToken();
            if (!token) return;
            
            const response = await fetch('/api/admin/logs/export', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    idToken: token,
                    userId: userFilter || null,
                    limit: 1000
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Create and download CSV file
                const blob = new Blob([data.csv], { type: 'text/csv' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = data.filename;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                this.showNotification('Logs exported successfully', 'success');
            } else {
                this.showNotification(data.error || 'Failed to export logs', 'error');
            }
        } catch (error) {
            console.error('Error exporting logs:', error);
            this.showNotification('Connection error while exporting logs', 'error');
        }
    }
    
    async loadSystemHealth() {
        try {
            const token = await authManager.getCurrentUserToken();
            if (!token) return;
            
            const response = await fetch('/api/admin/health', {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.renderSystemHealth(data.metrics);
            } else {
                document.getElementById('system-health').innerHTML = '<p>Failed to load system health</p>';
            }
        } catch (error) {
            console.error('Error loading system health:', error);
            document.getElementById('system-health').innerHTML = '<p>Error loading system health</p>';
        }
    }
    
    renderSystemHealth(metrics) {
        const systemHealth = document.getElementById('system-health');
        
        systemHealth.innerHTML = `
            <div class="health-metric">
                <span>Total Requests (24h):</span>
                <strong>${metrics.totalRequests24h}</strong>
            </div>
            <div class="health-metric">
                <span>Failed Requests (24h):</span>
                <strong style="color: ${metrics.failedRequests24h > 0 ? '#ef4444' : '#10b981'}">${metrics.failedRequests24h}</strong>
            </div>
            <div class="health-metric">
                <span>Provider Failures (24h):</span>
                <strong style="color: ${metrics.providerFailures24h > 0 ? '#ef4444' : '#10b981'}">${metrics.providerFailures24h}</strong>
            </div>
            <div class="health-metric">
                <span>Rate Limited (24h):</span>
                <strong style="color: ${metrics.rateLimitedRequests24h > 0 ? '#f59e0b' : '#10b981'}">${metrics.rateLimitedRequests24h}</strong>
            </div>
            <div class="health-metric">
                <span>Credits Consumed (24h):</span>
                <strong>${metrics.creditsConsumed24h}</strong>
            </div>
            <div class="health-metric">
                <span>Success Rate:</span>
                <strong style="color: ${metrics.successRate > 95 ? '#10b981' : metrics.successRate > 85 ? '#f59e0b' : '#ef4444'}">${metrics.successRate.toFixed(1)}%</strong>
            </div>
            <div class="health-metric">
                <span>Last Updated:</span>
                <strong>${new Date(metrics.lastUpdated).toLocaleString()}</strong>
            </div>
        `;
    }
    
    showNotification(message, type = 'info') {
        // Use the chat manager's notification system
        if (window.chatManager) {
            chatManager.showNotification(message, type);
        } else {
            alert(message);
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Create global admin manager instance
const adminManager = new AdminManager();