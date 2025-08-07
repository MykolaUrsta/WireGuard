// Device creation form handling
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('deviceForm');
    const step1 = document.getElementById('step1');
    const step2 = document.getElementById('step2');
    const keyOptionInputs = document.querySelectorAll('input[name="key_option"]');
    const publicKeyInput = document.getElementById('public_key');
    const publicKeyGroup = document.getElementById('public_key_input');
    const createButton = document.getElementById('nextBtn');
    const qrCodeDiv = document.getElementById('qr-code');
    const deviceNameSpan = document.getElementById('device-name-display');
    const deviceIpSpan = document.getElementById('device-ip-display');
    const deviceKeySpan = document.getElementById('device-key-display');
    const downloadBtn = document.getElementById('downloadBtn');
    const backBtn = document.getElementById('backStepBtn');
    const finishBtn = document.getElementById('finishBtn');
    const radioOptions = document.querySelectorAll('.radio-option');
    
    let deviceConfig = null;

    // Handle key option changes
    keyOptionInputs.forEach(input => {
        input.addEventListener('change', function() {
            if (this.value === 'provide') {
                publicKeyGroup.style.display = 'block';
                publicKeyInput.required = true;
            } else {
                publicKeyGroup.style.display = 'none';
                publicKeyInput.required = false;
                publicKeyInput.value = '';
            }
        });
    });

    // Handle radio option clicks
    radioOptions.forEach(option => {
        option.addEventListener('click', function() {
            // Remove active class from all options
            radioOptions.forEach(opt => opt.classList.remove('active'));
            // Add active class to clicked option
            this.classList.add('active');
            
            // Check the radio input
            const radio = this.querySelector('input[type="radio"]');
            radio.checked = true;
            
            // Trigger change event
            radio.dispatchEvent(new Event('change'));
            
            validateForm();
        });
    });

    // Form validation
    function validateForm() {
        const name = document.getElementById('device_name').value.trim();
        const userId = document.getElementById('user_id').value;
        const keyOption = document.querySelector('input[name="key_option"]:checked');
        
        if (name && userId && keyOption) {
            createButton.disabled = false;
            createButton.classList.remove('disabled');
        } else {
            createButton.disabled = true;
            createButton.classList.add('disabled');
        }
        
        if (keyOption && keyOption.value === 'provide' && !publicKeyInput.value.trim()) {
            createButton.disabled = true;
            createButton.classList.add('disabled');
        }
    }

    // Add event listeners for validation
    document.getElementById('device_name').addEventListener('input', validateForm);
    document.getElementById('user_id').addEventListener('change', validateForm);
    keyOptionInputs.forEach(input => {
        input.addEventListener('change', validateForm);
    });
    publicKeyInput.addEventListener('input', validateForm);

    // Submit form
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        if (!validateForm()) {
            return;
        }
        
        // Show loading state
        createButton.disabled = true;
        createButton.innerHTML = '<div class="spinner"></div> Creating...';
        
        // Prepare form data
        const formData = new FormData(form);
        
        // Add CSRF token
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        
        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                deviceConfig = data.device;
                showStep2(data);
            } else {
                showError(data.error || 'An error occurred while creating the device');
                resetCreateButton();
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showError('Network error occurred');
            resetCreateButton();
        });
    });

    function resetCreateButton() {
        createButton.disabled = false;
        createButton.innerHTML = 'Create Device';
    }

    function showStep2(data) {
        // Hide step 1, show step 2
        step1.style.display = 'none';
        step2.style.display = 'block';
        
        // Fill in device information
        deviceNameSpan.textContent = data.device.name;
        deviceIpSpan.textContent = data.device.ip_address;
        deviceKeySpan.textContent = data.device.public_key.substring(0, 20) + '...';
        
        // Show QR code
        qrCodeDiv.innerHTML = `<img src="data:image/png;base64,${data.qr_code}" alt="QR Code" class="qr-image">`;
        
        // Reset create button
        resetCreateButton();
    }

    function downloadConfig(deviceName, config) {
        const blob = new Blob([config], { type: 'text/plain' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${deviceName.replace(/\s+/g, '_')}.conf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }

    function showError(message) {
        // Remove existing alerts
        const existingAlert = document.querySelector('.alert-danger');
        if (existingAlert) {
            existingAlert.remove();
        }
        
        // Create new alert
        const alert = document.createElement('div');
        alert.className = 'alert alert-danger alert-dismissible fade show';
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        // Insert at top of form
        form.insertBefore(alert, form.firstChild);
        
        // Auto dismiss after 5 seconds
        setTimeout(() => {
            if (alert.parentNode) {
                alert.remove();
            }
        }, 5000);
    }

    // Back button functionality
    if (backBtn) {
        backBtn.addEventListener('click', function() {
            step2.style.display = 'none';
            step1.style.display = 'block';
            
            // Reset form
            form.reset();
            publicKeyGroup.style.display = 'none';
            publicKeyInput.required = false;
            
            // Reset radio options
            radioOptions.forEach(opt => opt.classList.remove('active'));
            radioOptions[0].classList.add('active');
            
            // Clear step 2 content
            qrCodeDiv.innerHTML = '';
            deviceConfig = null;
            
            validateForm();
        });
    }

    // Download button functionality
    if (downloadBtn) {
        downloadBtn.addEventListener('click', function() {
            if (deviceConfig) {
                downloadConfig(deviceConfig.name, deviceConfig.config);
            }
        });
    }

    // Finish button functionality
    if (finishBtn) {
        finishBtn.addEventListener('click', function() {
            window.location.href = '/accounts/users/';
        });
    }

    // Initial validation
    validateForm();
});
