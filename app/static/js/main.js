let isLogoutEventAttached = false;

document.addEventListener('DOMContentLoaded', function() {
    checkAuthStatus();
    setupPasswordToggles();
    setupFormValidation();
    setupAuthForms();

    attachLogoutEvent();
});

function setupPasswordToggles() {
    document.querySelectorAll('.toggle-password').forEach(button => {
        button.addEventListener('click', function() {
            const input = this.closest('.input-group').querySelector('input');
            const icon = this.querySelector('i');
            
            if (input.type === 'password') {
                input.type = 'text';
                icon.classList.remove('fa-eye');
                icon.classList.add('fa-eye-slash');
            } else {
                input.type = 'password';
                icon.classList.remove('fa-eye-slash');
                icon.classList.add('fa-eye');
            }
        });
    });
}

function setupFormValidation() {
    // Password validation
    document.getElementById('registerPassword').addEventListener('input', function() {
        const isValid = this.value.length >= 6;
        this.classList.toggle('is-invalid', !isValid);
    });

    // Confirm password validation
    document.getElementById('confirmPassword').addEventListener('input', function() {
        const password = document.getElementById('registerPassword').value;
        const isValid = this.value === password;
        this.classList.toggle('is-invalid', !isValid);
    });

    // Email validation
    ['loginEmail', 'registerEmail'].forEach(id => {
        document.getElementById(id).addEventListener('input', function() {
            const isValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(this.value);
            this.classList.toggle('is-invalid', !isValid);
        });
    });

    // Phone validation
    document.getElementById('registerPhone').addEventListener('input', function() {
        const isValid = /^[0-9]{10}$/.test(this.value.replace(/\D/g, ''));
        this.classList.toggle('is-invalid', !isValid);
    });
}

function setupAuthForms() {
    // Login form submission
    document.getElementById('loginForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        
        if (!validateForm(this)) return;

        const formData = {
            email: document.getElementById('loginEmail').value,
            password: document.getElementById('loginPassword').value
        };

        try {
            const response = await fetch('/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(formData)
            });

            const data = await response.json();
            if (response.ok) {
                updateUIForLoggedInUser(data.user);
                $('#authModal').modal('hide');
                showToast('success', 'Đăng nhập thành công!');
            } else {
                showToast('error', data.message || 'Đăng nhập thất bại!');
            }
        } catch (error) {
            console.error('Login error:', error);
            showToast('error', 'Có lỗi xảy ra. Vui lòng thử lại sau.');
        }
    });

    // Register form submission
    document.getElementById('registerForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        
        if (!validateForm(this)) return;

        const formData = {
            name: document.getElementById('registerName').value,
            email: document.getElementById('registerEmail').value,
            phone_number: document.getElementById('registerPhone').value.replace(/\D/g, ''),
            password: document.getElementById('registerPassword').value
        };

        try {
            const response = await fetch('/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            const data = await response.json();
            
            if (response.ok) {
                showToast('success', 'Đăng ký thành công! Vui lòng đăng nhập.');
                $('#authModal').modal('hide');
                setTimeout(() => {
                    $('#authModal').modal('show');
                    document.getElementById('login-tab').click();
                }, 1500);
            } else {
                showToast('error', data.message || 'Đăng ký thất bại!');
            }
        } catch (error) {
            console.error('Registration error:', error);
            showToast('error', 'Có lỗi xảy ra. Vui lòng thử lại sau.');
        }
    });
}

function validateForm(form) {
    let isValid = true;
    form.querySelectorAll('input[required]').forEach(input => {
        if (!input.value) {
            input.classList.add('is-invalid');
            isValid = false;
        } else {
            input.classList.remove('is-invalid');
        }
    });
    return isValid;
}

function updateUIForLoggedInUser(user) {
    document.getElementById('welcomeText').textContent = `Xin chào, ${user.email}!`;
    document.getElementById('welcomeText').style.display = 'inline';
    document.getElementById('loginButton').style.display = 'none';
    document.getElementById('logoutButton').style.display = 'inline';

    attachLogoutEvent();
}

async function checkAuthStatus() {
    try {
        const response = await fetch('/check-auth', {
            method: 'GET',
            credentials: 'include'
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.authenticated) {
                updateUIForLoggedInUser(data.user);
            } else {
                resetAuthUI();
            }
        } else {
            resetAuthUI();
        }
    } catch (error) {
        console.error('Auth check error:', error);
        resetAuthUI();
    }
}

function resetAuthUI() {
    document.getElementById('welcomeText').style.display = 'none';
    document.getElementById('loginButton').style.display = 'inline';
    document.getElementById('logoutButton').style.display = 'none';
}

function showToast(type, message) {
    alert(message);
}

function attachLogoutEvent() {
    if (!isLogoutEventAttached) {
        const logoutButton = document.getElementById('logoutButton');
        if (logoutButton) {
            logoutButton.addEventListener('click', handleLogout);
            isLogoutEventAttached = true;
        }
    }
}

async function handleLogout() {
    try {
        const response = await fetch('/logout', {
            method: 'POST',
            credentials: 'include'
        });
        
        if (response.ok) {
            localStorage.removeItem('userEmail');
            resetAuthUI();
            alert("Đã đăng xuất!");
            location.reload();
        }
    } catch (error) {
        console.error("Error during logout:", error);
        alert("Có lỗi xảy ra khi đăng xuất.");
    }
}



