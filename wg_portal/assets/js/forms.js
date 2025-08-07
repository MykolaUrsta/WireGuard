// WireGuard Panel - Forms JavaScript
document.addEventListener('DOMContentLoaded', function() {
    initForms();
    initValidation();
    initFileUploads();
});

function initForms() {
    // Handle form submissions with loading states
    const forms = document.querySelectorAll('form[data-loading]');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
            }
        });
    });
    
    // Auto-save functionality
    const autoSaveForms = document.querySelectorAll('form[data-autosave]');
    autoSaveForms.forEach(form => {
        const inputs = form.querySelectorAll('input, textarea, select');
        inputs.forEach(input => {
            input.addEventListener('change', debounce(() => autoSaveForm(form), 1000));
        });
    });
}

function initValidation() {
    // Real-time validation
    const validatedInputs = document.querySelectorAll('input[data-validate], textarea[data-validate]');
    validatedInputs.forEach(input => {
        input.addEventListener('blur', validateField);
        input.addEventListener('input', debounce(validateField, 500));
    });
}

function initFileUploads() {
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach(input => {
        input.addEventListener('change', handleFileUpload);
    });
}

function validateField(e) {
    const field = e.target;
    const validationType = field.getAttribute('data-validate');
    let isValid = true;
    let message = '';
    
    switch (validationType) {
        case 'ip':
            isValid = validateIP(field.value);
            message = 'Please enter a valid IP address';
            break;
        case 'cidr':
            isValid = validateCIDR(field.value);
            message = 'Please enter a valid CIDR notation (e.g., 10.0.0.0/24)';
            break;
        case 'port':
            isValid = validatePort(field.value);
            message = 'Please enter a valid port number (1-65535)';
            break;
        case 'domain':
            isValid = validateDomain(field.value);
            message = 'Please enter a valid domain name';
            break;
    }
    
    showFieldValidation(field, isValid, message);
}

function validateIP(ip) {
    const ipRegex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    return ipRegex.test(ip);
}

function validateCIDR(cidr) {
    const cidrRegex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\/([0-9]|[1-2][0-9]|3[0-2])$/;
    return cidrRegex.test(cidr);
}

function validatePort(port) {
    const portNum = parseInt(port);
    return portNum >= 1 && portNum <= 65535;
}

function validateDomain(domain) {
    const domainRegex = /^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/i;
    return domainRegex.test(domain);
}

function showFieldValidation(field, isValid, message) {
    // Remove existing validation
    field.classList.remove('is-valid', 'is-invalid');
    const existingFeedback = field.parentNode.querySelector('.invalid-feedback, .valid-feedback');
    if (existingFeedback) {
        existingFeedback.remove();
    }
    
    // Add new validation
    if (field.value && !isValid) {
        field.classList.add('is-invalid');
        const feedback = document.createElement('div');
        feedback.className = 'invalid-feedback';
        feedback.textContent = message;
        field.parentNode.appendChild(feedback);
    } else if (field.value && isValid) {
        field.classList.add('is-valid');
    }
}

function autoSaveForm(form) {
    const formData = new FormData(form);
    const url = form.getAttribute('data-autosave-url') || form.action;
    
    fetch(url, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Changes saved automatically', 'success');
        }
    })
    .catch(error => {
        console.error('Auto-save failed:', error);
    });
}

function handleFileUpload(e) {
    const input = e.target;
    const file = input.files[0];
    
    if (file) {
        // Show file info
        const fileInfo = document.createElement('div');
        fileInfo.className = 'file-info';
        fileInfo.innerHTML = `
            <i class="fas fa-file"></i>
            <span>${file.name}</span>
            <small>${formatFileSize(file.size)}</small>
        `;
        
        // Replace any existing file info
        const existingInfo = input.parentNode.querySelector('.file-info');
        if (existingInfo) {
            existingInfo.remove();
        }
        
        input.parentNode.appendChild(fileInfo);
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} notification`;
    notification.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check' : type === 'error' ? 'exclamation-triangle' : 'info'}"></i>
        <span>${message}</span>
        <button type="button" class="alert-close" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    // Add to notifications container or body
    const container = document.querySelector('.notifications-container') || document.body;
    container.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
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

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
