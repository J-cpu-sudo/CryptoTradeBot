// Global dashboard functionality and utilities

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeDashboard();
});

function initializeDashboard() {
    // Set up global event listeners
    setupGlobalEventListeners();
    
    // Initialize tooltips
    initializeTooltips();
    
    // Start periodic updates
    startPeriodicUpdates();
}

function setupGlobalEventListeners() {
    // Handle navigation active states
    updateActiveNavigation();
    
    // Handle responsive table scrolling
    setupTableResponsiveness();
}

function initializeTooltips() {
    // Initialize Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

function startPeriodicUpdates() {
    // Update bot status in navbar every 30 seconds
    setInterval(updateNavbarStatus, 30000);
    updateNavbarStatus(); // Initial update
}

function updateActiveNavigation() {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav-link');
    
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });
}

function setupTableResponsiveness() {
    // Add horizontal scroll indicators for responsive tables
    const responsiveTables = document.querySelectorAll('.table-responsive');
    
    responsiveTables.forEach(table => {
        table.addEventListener('scroll', function() {
            const scrollLeft = this.scrollLeft;
            const scrollWidth = this.scrollWidth;
            const clientWidth = this.clientWidth;
            
            // Add visual indicators if needed
            if (scrollLeft > 0) {
                this.classList.add('scrolled-left');
            } else {
                this.classList.remove('scrolled-left');
            }
            
            if (scrollLeft < scrollWidth - clientWidth) {
                this.classList.add('scrolled-right');
            } else {
                this.classList.remove('scrolled-right');
            }
        });
    });
}

function updateNavbarStatus() {
    fetch('/api/status')
        .then(response => response.json())
        .then(status => {
            const statusBadge = document.getElementById('bot-status');
            if (statusBadge) {
                const statusConfig = {
                    'running': { class: 'bg-success', icon: 'play', text: 'Running' },
                    'stopped': { class: 'bg-danger', icon: 'stop', text: 'Stopped' },
                    'paused': { class: 'bg-warning', icon: 'pause', text: 'Paused' },
                    'error': { class: 'bg-danger', icon: 'exclamation-triangle', text: 'Error' }
                };
                
                const config = statusConfig[status.status] || statusConfig['stopped'];
                statusBadge.className = `badge ${config.class}`;
                statusBadge.innerHTML = `<i class="fas fa-${config.icon} me-1"></i>${config.text}`;
            }
        })
        .catch(error => {
            console.error('Error updating navbar status:', error);
        });
}

// Utility Functions

function formatCurrency(value, currency = 'USD') {
    if (value === null || value === undefined || isNaN(value)) {
        return '$0.00';
    }
    
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(value);
}

function formatPercentage(value, decimals = 1) {
    if (value === null || value === undefined || isNaN(value)) {
        return '0.0%';
    }
    
    return value.toFixed(decimals) + '%';
}

function formatNumber(value, decimals = 2) {
    if (value === null || value === undefined || isNaN(value)) {
        return '0';
    }
    
    return new Intl.NumberFormat('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    }).format(value);
}

function updatePnLColor(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) {
        element.classList.remove('pnl-positive', 'pnl-negative', 'text-success', 'text-danger');
        
        if (value > 0) {
            element.classList.add('pnl-positive', 'text-success');
        } else if (value < 0) {
            element.classList.add('pnl-negative', 'text-danger');
        }
    }
}

function showAlert(message, type = 'info', duration = 5000) {
    const alertsContainer = document.getElementById('alerts-container') || createAlertsContainer();
    const alertId = 'alert-' + Date.now();
    
    const alertHTML = `
        <div id="${alertId}" class="alert alert-${type} alert-dismissible fade show" role="alert">
            <i class="fas fa-${getAlertIcon(type)} me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    alertsContainer.insertAdjacentHTML('beforeend', alertHTML);
    
    // Auto-dismiss after specified duration
    if (duration > 0) {
        setTimeout(() => {
            const alert = document.getElementById(alertId);
            if (alert) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, duration);
    }
}

function createAlertsContainer() {
    const container = document.createElement('div');
    container.id = 'alerts-container';
    container.className = 'position-fixed top-0 end-0 p-3';
    container.style.zIndex = '1050';
    document.body.appendChild(container);
    return container;
}

function getAlertIcon(type) {
    const icons = {
        'success': 'check-circle',
        'danger': 'exclamation-circle',
        'warning': 'exclamation-triangle',
        'info': 'info-circle'
    };
    return icons[type] || 'info-circle';
}

function formatTimeAgo(timestamp) {
    const now = new Date();
    const time = new Date(timestamp);
    const diffInSeconds = Math.floor((now - time) / 1000);
    
    if (diffInSeconds < 60) {
        return `${diffInSeconds}s ago`;
    } else if (diffInSeconds < 3600) {
        return `${Math.floor(diffInSeconds / 60)}m ago`;
    } else if (diffInSeconds < 86400) {
        return `${Math.floor(diffInSeconds / 3600)}h ago`;
    } else {
        return `${Math.floor(diffInSeconds / 86400)}d ago`;
    }
}

function sanitizeHtml(str) {
    const temp = document.createElement('div');
    temp.textContent = str;
    return temp.innerHTML;
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Loading state management
function showLoadingState(containerId, message = 'Loading...') {
    const container = document.getElementById(containerId);
    if (container) {
        container.innerHTML = `
            <div class="loading-state">
                <div class="spinner-border spinner-border-sm text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <span class="ms-2">${message}</span>
            </div>
        `;
    }
}

function hideLoadingState(containerId) {
    const container = document.getElementById(containerId);
    if (container) {
        const loadingState = container.querySelector('.loading-state');
        if (loadingState) {
            loadingState.remove();
        }
    }
}

// Error handling
function handleApiError(error, context = 'API call') {
    console.error(`Error in ${context}:`, error);
    
    let message = 'An unexpected error occurred';
    if (error.message) {
        message = error.message;
    } else if (typeof error === 'string') {
        message = error;
    }
    
    showAlert(`${context} failed: ${message}`, 'danger');
}

// Chart utilities
function getChartColors() {
    return {
        primary: '#0d6efd',
        success: '#198754',
        danger: '#dc3545',
        warning: '#ffc107',
        info: '#0dcaf0',
        light: '#f8f9fa',
        dark: '#212529',
        secondary: '#6c757d'
    };
}

function createGradient(ctx, color1, color2) {
    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, color1);
    gradient.addColorStop(1, color2);
    return gradient;
}

// Local storage utilities
function saveToLocalStorage(key, value) {
    try {
        localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
        console.warn('Failed to save to localStorage:', error);
    }
}

function loadFromLocalStorage(key, defaultValue = null) {
    try {
        const item = localStorage.getItem(key);
        return item ? JSON.parse(item) : defaultValue;
    } catch (error) {
        console.warn('Failed to load from localStorage:', error);
        return defaultValue;
    }
}

// Export functions for use in other scripts
window.dashboardUtils = {
    formatCurrency,
    formatPercentage,
    formatNumber,
    updatePnLColor,
    showAlert,
    formatTimeAgo,
    sanitizeHtml,
    debounce,
    throttle,
    showLoadingState,
    hideLoadingState,
    handleApiError,
    getChartColors,
    createGradient,
    saveToLocalStorage,
    loadFromLocalStorage
};
