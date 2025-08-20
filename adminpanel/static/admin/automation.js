// adminpanel/static/admin/automation.js
// Instagram Automation System JavaScript

class AutomationManager {
    constructor() {
        this.init();
        this.setupEventListeners();
        this.startAutoRefresh();
    }

    init() {
        console.log('Automation Manager initialized');
        this.toastContainer = this.createToastContainer();
    }

    setupEventListeners() {
        // Automation toggle
        const automationToggle = document.getElementById('automationToggle');
        if (automationToggle) {
            automationToggle.addEventListener('change', this.toggleAutomation.bind(this));
        }

        // Manual activity buttons
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-action="run-activity"]')) {
                const sessionUser = e.target.dataset.sessionUser;
                this.runManualActivity(sessionUser);
            }
            
            if (e.target.matches('[data-action="refresh-sessions"]')) {
                this.refreshSessions();
            }
            
            if (e.target.matches('[data-action="view-session"]')) {
                const sessionId = e.target.dataset.sessionId;
                this.viewSessionDetails(sessionId);
            }
        });

        // Filter controls
        const filters = document.querySelectorAll('[data-filter]');
        filters.forEach(filter => {
            filter.addEventListener('change', this.applyFilters.bind(this));
        });
    }

    async toggleAutomation() {
        const toggle = document.getElementById('automationToggle');
        const status = document.getElementById('automationStatus');
        
        if (!toggle || !status) return;

        const enabled = toggle.checked;
        
        try {
            this.showToast('Otomasyon durumu güncelleniyor...', 'info');
            
            const response = await fetch('/admin/automation/api/toggle', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ enabled })
            });

            const result = await response.json();

            if (result.success) {
                status.textContent = result.enabled ? 'Aktif' : 'Pasif';
                status.className = result.enabled ? 'text-success' : 'text-danger';
                this.showToast(result.message, 'success');
                
                // Update UI state
                this.updateAutomationStatus(result.enabled);
            } else {
                throw new Error(result.error || 'Bilinmeyen hata');
            }
        } catch (error) {
            // Revert toggle state
            toggle.checked = !enabled;
            this.showToast('Hata: ' + error.message, 'error');
        }
    }

    async runManualActivity(sessionUser = null) {
        try {
            const message = sessionUser 
                ? `${sessionUser} için aktivite başlatılıyor...`
                : 'Rastgele session için aktivite başlatılıyor...';
            
            this.showToast(message, 'info');
            
            const response = await fetch('/admin/automation/api/run-activity', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(sessionUser ? { session_user: sessionUser } : {})
            });

            const result = await response.json();

            if (result.success) {
                this.showToast('Aktivite başarıyla tamamlandı!', 'success');
                this.showActivityResult(result);
                
                // Refresh data after delay
                setTimeout(() => {
                    this.refreshDashboardData();
                }, 2000);
            } else {
                this.showToast('Aktivite başarısız: ' + (result.error || 'Bilinmeyen hata'), 'error');
            }
        } catch (error) {
            this.showToast('Hata: ' + error.message, 'error');
        }
    }

    async refreshSessions() {
        try {
            this.showToast('Session\'lar yenileniyor...', 'info');
            
            const response = await fetch('/admin/automation/api/refresh-sessions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            const result = await response.json();

            if (result.success) {
                this.showToast('Session\'lar başarıyla yenilendi!', 'success');
                this.updateSessionStats(result.stats);
                
                // Reload page to show updated data
                setTimeout(() => location.reload(), 1000);
            } else {
                this.showToast('Yenileme başarısız: ' + (result.error || 'Bilinmeyen hata'), 'error');
            }
        } catch (error) {
            this.showToast('Hata: ' + error.message, 'error');
        }
    }

    async refreshDashboardData() {
        try {
            const response = await fetch('/admin/automation/api/status');
            const status = await response.json();
            
            this.updateStatusDisplay(status);
        } catch (error) {
            console.error('Failed to refresh dashboard data:', error);
        }
    }

    updateStatusDisplay(status) {
        // Update last activity
        const lastActivity = document.getElementById('lastActivity');
        if (lastActivity && status.last_activity) {
            lastActivity.textContent = status.last_activity.substring(0, 16).replace('T', ' ');
        }

        // Update next scheduled
        const nextScheduled = document.getElementById('nextScheduled');
        if (nextScheduled && status.next_scheduled) {
            nextScheduled.textContent = status.next_scheduled.substring(0, 16).replace('T', ' ');
        }

        // Update session counts
        if (status.session_stats) {
            this.updateSessionStats(status.session_stats);
        }
    }

    updateSessionStats(stats) {
        const elements = {
            total: document.querySelector('[data-stat="total"]'),
            active: document.querySelector('[data-stat="active"]'),
            blocked: document.querySelector('[data-stat="blocked"]'),
            invalid: document.querySelector('[data-stat="invalid"]')
        };

        Object.entries(elements).forEach(([key, element]) => {
            if (element && stats[key] !== undefined) {
                element.textContent = stats[key];
            }
        });
    }

    updateAutomationStatus(enabled) {
        // Update status indicators throughout the page
        const indicators = document.querySelectorAll('[data-automation-status]');
        indicators.forEach(indicator => {
            indicator.textContent = enabled ? 'Aktif' : 'Pasif';
            indicator.className = enabled ? 'status-indicator active' : 'status-indicator inactive';
        });
    }

    showActivityResult(result) {
        if (!result.activities) return;

        const activities = result.activities;
        let message = 'Tamamlanan aktiviteler: ';
        const parts = [];

        if (activities.likes) {
            parts.push(`${activities.likes} beğeni`);
        }
        if (activities.stories_viewed) {
            parts.push(`${activities.stories_viewed} story`);
        }
        if (activities.explore_browsed) {
            parts.push('keşfet gezintisi');
        }

        if (parts.length > 0) {
            message += parts.join(', ');
            this.showToast(message, 'success', 7000);
        }
    }

    applyFilters() {
        const filters = document.querySelectorAll('[data-filter]');
        const filterValues = {};
        
        filters.forEach(filter => {
            const filterType = filter.dataset.filter;
            filterValues[filterType] = filter.value.toLowerCase();
        });

        const rows = document.querySelectorAll('[data-filterable]');
        let visibleCount = 0;

        rows.forEach(row => {
            let visible = true;

            Object.entries(filterValues).forEach(([filterType, value]) => {
                if (!value) return;

                const rowValue = (row.dataset[filterType] || '').toLowerCase();
                if (!rowValue.includes(value)) {
                    visible = false;
                }
            });

            row.style.display = visible ? '' : 'none';
            if (visible) visibleCount++;
        });

        // Update visible count display
        const countDisplay = document.querySelector('[data-count-display]');
        if (countDisplay) {
            countDisplay.textContent = `${visibleCount} kayıt gösteriliyor`;
        }
    }

    clearFilters() {
        const filters = document.querySelectorAll('[data-filter]');
        filters.forEach(filter => {
            filter.value = '';
        });
        this.applyFilters();
    }

    async viewSessionDetails(sessionId) {
        try {
            const response = await fetch(`/admin/automation/api/session-activity/${sessionId}`);
            const data = await response.json();

            if (response.ok) {
                this.showSessionModal(sessionId, data);
            } else {
                this.showToast('Session detayları alınamadı: ' + (data.error || 'Bilinmeyen hata'), 'error');
            }
        } catch (error) {
            this.showToast('Hata: ' + error.message, 'error');
        }
    }

    showSessionModal(sessionId, data) {
        // Create or update modal content
        const modalId = 'sessionDetailsModal';
        let modal = document.getElementById(modalId);
        
        if (!modal) {
            modal = this.createModal(modalId, 'Session Detayları');
        }

        const modalBody = modal.querySelector('.modal-body');
        modalBody.innerHTML = this.generateSessionDetailsHTML(sessionId, data);

        // Show modal
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
    }

    generateSessionDetailsHTML(sessionId, data) {
        const activity = data.activity || {};
        const canPerform = data.can_perform || {};

        return `
            <div class="row">
                <div class="col-md-6">
                    <h6>Günlük Aktivite</h6>
                    <div class="activity-stats">
                        ${this.generateActivityStat('❤️', 'Beğeni', activity.likes || 0)}
                        ${this.generateActivityStat('📖', 'Story', activity.stories || 0)}
                        ${this.generateActivityStat('👥', 'Takip', activity.follows || 0)}
                        ${this.generateActivityStat('💬', 'Yorum', activity.comments || 0)}
                    </div>
                </div>
                <div class="col-md-6">
                    <h6>Limit Durumu</h6>
                    <div class="limit-status">
                        ${this.generateLimitStatus('Beğeni', canPerform.likes)}
                        ${this.generateLimitStatus('Story', canPerform.stories)}
                        ${this.generateLimitStatus('Takip', canPerform.follows)}
                        ${this.generateLimitStatus('Yorum', canPerform.comments)}
                    </div>
                </div>
            </div>
            <div class="mt-3">
                <button class="btn btn-primary" onclick="automationManager.runManualActivity('${sessionId}')">
                    Bu Session için Aktivite Çalıştır
                </button>
            </div>
        `;
    }

    generateActivityStat(icon, label, count) {
        return `
            <div class="d-flex justify-content-between align-items-center mb-2">
                <span>${icon} ${label}</span>
                <span class="badge bg-primary">${count}</span>
            </div>
        `;
    }

    generateLimitStatus(label, canPerform) {
        const status = canPerform ? 'success' : 'warning';
        const icon = canPerform ? '✅' : '⚠️';
        const text = canPerform ? 'Yapabilir' : 'Limit doldu';
        
        return `
            <div class="d-flex justify-content-between align-items-center mb-2">
                <span>${label}</span>
                <span class="badge bg-${status}">${icon} ${text}</span>
            </div>
        `;
    }

    createModal(id, title) {
        const modal = document.createElement('div');
        modal.className = 'modal fade modal-automation';
        modal.id = id;
        modal.tabIndex = -1;
        
        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">${title}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <!-- Content will be loaded here -->
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        return modal;
    }

    createToastContainer() {
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        return container;
    }

    showToast(message, type = 'info', duration = 5000) {
        const toast = document.createElement('div');
        const alertClass = type === 'error' ? 'danger' : type === 'success' ? 'success' : 'info';
        
        toast.className = `alert alert-${alertClass} custom-toast fade-in`;
        toast.innerHTML = `
            <div class="d-flex align-items-center">
                <div class="flex-grow-1">${message}</div>
                <button type="button" class="btn-close btn-close-white ms-2" onclick="this.parentElement.parentElement.remove()"></button>
            </div>
        `;
        
        this.toastContainer.appendChild(toast);
        
        // Auto remove
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, duration);
    }

    startAutoRefresh() {
        // Refresh status every 30 seconds
        setInterval(async () => {
            if (document.visibilityState === 'visible') {
                try {
                    await this.refreshDashboardData();
                } catch (error) {
                    console.error('Auto refresh failed:', error);
                }
            }
        }, 30000);
    }

    // Utility methods
    formatDateTime(isoString) {
        if (!isoString) return 'N/A';
        return isoString.substring(0, 16).replace('T', ' ');
    }

    formatDuration(seconds) {
        if (seconds < 60) return `${seconds}s`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
        return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
    }

    copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            this.showToast('Panoya kopyalandı', 'success', 2000);
        }).catch(() => {
            this.showToast('Kopyalama başarısız', 'error');
        });
    }
}

// Global functions for compatibility
window.toggleAutomation = function() {
    if (window.automationManager) {
        window.automationManager.toggleAutomation();
    }
};

window.runManualActivity = function(sessionUser) {
    if (window.automationManager) {
        window.automationManager.runManualActivity(sessionUser);
    }
};

window.runActivityForSession = function(sessionUser) {
    if (window.automationManager) {
        window.automationManager.runManualActivity(sessionUser);
    }
};

window.refreshData = function() {
    if (window.automationManager) {
        window.automationManager.refreshSessions();
    }
};

window.refreshSessions = function() {
    if (window.automationManager) {
        window.automationManager.refreshSessions();
    }
};

window.viewSessionDetails = function(sessionId) {
    if (window.automationManager) {
        window.automationManager.viewSessionDetails(sessionId);
    }
};

window.viewSessionActivity = function(sessionId) {
    if (window.automationManager) {
        window.automationManager.viewSessionDetails(sessionId);
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    window.automationManager = new AutomationManager();
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AutomationManager;
}