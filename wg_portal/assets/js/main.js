// WireGuard Panel - Main JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    initTooltips();
    
    // Initialize modals
    initModals();
    
    // Initialize notifications
    initNotifications();
    
    // Initialize theme
    initTheme();
    
    // Initialize network monitoring
    initNetworkMonitoring();
});

// Tooltip initialization
function initTooltips() {
    const tooltips = document.querySelectorAll('[data-tooltip]');
    tooltips.forEach(tooltip => {
        tooltip.addEventListener('mouseenter', showTooltip);
        tooltip.addEventListener('mouseleave', hideTooltip);
    });
}

// Modal functionality
function initModals() {
    const modalTriggers = document.querySelectorAll('[data-modal]');
    modalTriggers.forEach(trigger => {
        trigger.addEventListener('click', function(e) {
            e.preventDefault();
            const modalId = this.getAttribute('data-modal');
            openModal(modalId);
        });
    });
    
    // Close modal on backdrop click
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('modal-backdrop')) {
            closeModal();
        }
    });
}

// Notification system
function initNotifications() {
    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
}

// Theme management
function initTheme() {
    const themeToggle = document.querySelector('.theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }
    
    // Load saved theme
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
}

// Network monitoring
function initNetworkMonitoring() {
    // Check network status every 30 seconds
    setInterval(checkNetworkStatus, 30000);
    
    // Initial check
    checkNetworkStatus();
}

// Utility functions
function showTooltip(e) {
    const tooltip = e.target;
    const text = tooltip.getAttribute('data-tooltip');
    
    const tooltipEl = document.createElement('div');
    tooltipEl.className = 'tooltip';
    tooltipEl.textContent = text;
    
    document.body.appendChild(tooltipEl);
    
    const rect = tooltip.getBoundingClientRect();
    tooltipEl.style.left = rect.left + (rect.width / 2) - (tooltipEl.offsetWidth / 2) + 'px';
    tooltipEl.style.top = rect.top - tooltipEl.offsetHeight - 5 + 'px';
}

function hideTooltip() {
    const tooltip = document.querySelector('.tooltip');
    if (tooltip) {
        tooltip.remove();
    }
}

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }
}

function closeModal() {
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        modal.style.display = 'none';
    });
    document.body.style.overflow = '';
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
}

function checkNetworkStatus() {
    // TODO: Implement proper API endpoint when ready
    console.log('Network status monitoring disabled');
}

function updateNetworkIndicators(data) {
    // Update online device count
    const onlineCounters = document.querySelectorAll('.online-devices-count');
    onlineCounters.forEach(counter => {
        counter.textContent = data.online_devices || 0;
    });
    
    // Update status indicators
    const statusIndicators = document.querySelectorAll('.status-indicator');
    statusIndicators.forEach(indicator => {
        const service = indicator.getAttribute('data-service');
        if (data.services && data.services[service]) {
            indicator.className = `status-indicator ${data.services[service] ? 'online' : 'offline'}`;
        }
    });
}

// Export functions for global access
window.WireGuardPanel = {
    openModal,
    closeModal,
    toggleTheme,
    checkNetworkStatus
};
