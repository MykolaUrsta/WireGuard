// Device creation form handling
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('deviceForm');
    const step1 = document.getElementById('step1');
    const step2 = document.getElementById('step2');
    const nextButton = document.getElementById('nextBtn');
    const qrCodeDiv = document.getElementById('qr-code');
    const deviceNameSpan = document.getElementById('device-name-display');
    const deviceIpSpan = document.getElementById('device-ip-display');
    const deviceKeySpan = document.getElementById('device-key-display');
    const downloadBtn = document.getElementById('downloadBtn');
    const backBtn = document.getElementById('backStepBtn');
    const finishBtn = document.getElementById('finishBtn');
    
    let deviceConfig = null;

    // Form validation
    function validateForm() {
        const name = document.getElementById('device_name').value.trim();
        const locationId = document.getElementById('location_id').value;
        
        if (name && locationId) {
            nextButton.disabled = false;
            nextButton.classList.remove('disabled');
        } else {
            nextButton.disabled = true;
            nextButton.classList.add('disabled');
        }
    }

    // Add event listeners for validation
    document.getElementById('device_name').addEventListener('input', validateForm);
    document.getElementById('location_id').addEventListener('change', validateForm);

    // Next button click handler
    nextButton.addEventListener('click', function(e) {
        e.preventDefault();
        
        if (nextButton.disabled) {
            return;
        }
        
        // Show loading state
        nextButton.disabled = true;
        nextButton.innerHTML = '<div class="spinner"></div> Створення...';
        
        // Prepare form data
        const formData = new FormData(form);
        formData.append('key_option', 'generate'); // Always generate keys
        // Якщо є приховане поле user_id — додаємо його явно (для сумісності)
        const userIdInput = document.getElementById('user_id');
        if (userIdInput) {
            formData.append('user_id', userIdInput.value);
        }
        
        // Add CSRF token
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        
        fetch(window.location.pathname, {
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
                showError(data.error || 'Сталася помилка при створенні пристрою');
                resetNextButton();
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showError('Помилка мережі');
            resetNextButton();
        });
    });

    function resetNextButton() {
        nextButton.disabled = false;
        const nextBtnText = document.getElementById('nextBtnText');
        if (nextBtnText) {
            // Don't change text if we're on step 2
            if (step2.style.display !== 'block') {
                nextBtnText.textContent = 'Далі';
            }
        } else {
            nextButton.innerHTML = 'Далі <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24"><path d="M4 13h12.17l-5.59 5.59L12 20l8-8-8-8-1.41 1.41L16.17 11H4v2z"/></svg>';
        }
    }

    function showStep2(data) {
        // Hide step 1, show step 2
        step1.style.display = 'none';
        step2.style.display = 'block';
        
        // Change next button to finish button
        const nextBtnText = document.getElementById('nextBtnText');
        if (nextBtnText) {
            nextBtnText.textContent = 'Завершити';
        }
        nextButton.onclick = function() {
            window.location.href = '/locations/';
        };
        
        // Fill in device information
        deviceNameSpan.textContent = data.device.name;
        deviceIpSpan.textContent = data.device.ip_address;
        deviceKeySpan.textContent = data.device.public_key.substring(0, 20) + '...';
        
        // Show QR code
        qrCodeDiv.innerHTML = `<img src="data:image/png;base64,${data.qr_code}" alt="QR Code" class="qr-image">`;
        
        // Reset next button
        resetNextButton();
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
        
        // Insert at top of form container
        const formContainer = document.querySelector('.form-container');
        formContainer.insertBefore(alert, formContainer.firstChild);
        
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
            
            // Reset next button text and functionality
            const nextBtnText = document.getElementById('nextBtnText');
            if (nextBtnText) {
                nextBtnText.textContent = 'Далі';
            }
            nextButton.onclick = null; // Remove custom onclick
            
            // Reset form
            form.reset();
            
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
