/**
 * Campus Facility Maintenance Request Management System
 * Authentication & Registration Handlers (auth.js)
 */

document.addEventListener('DOMContentLoaded', () => {
  const loginForm = document.getElementById('login-form');
  const registerForm = document.getElementById('register-form');
  const alertBox = document.getElementById('auth-alert');

  function showAlert(msg, isError = true) {
    if (!alertBox) return;
    alertBox.textContent = msg;
    alertBox.className = `auth-alert ${isError ? 'error' : 'success'}`;
    alertBox.style.display = 'block';
  }

  function hideAlert() {
    if (alertBox) alertBox.style.display = 'none';
  }

  // Handle Login
  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      hideAlert();

      const email = document.getElementById('email').value.trim();
      const password = document.getElementById('password').value;
      const roleHint = loginForm.dataset.role || null;
      const submitBtn = loginForm.querySelector('button[type="submit"]');

      if (!email || !password) {
        showAlert('Please enter both email and password.');
        return;
      }

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Authenticating...';
      }

      const res = await apiFetch('/api/auth/login', {
        method: 'POST',
        body: { email, password, role: roleHint }
      });

      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Sign In';
      }

      if (res.ok && res.data.redirect_url) {
        showAlert('Login successful! Redirecting...', false);
        window.location.href = res.data.redirect_url;
      } else {
        const errorMsg = res.data?.error || 'Authentication failed. Please check credentials.';
        showAlert(errorMsg, true);
      }
    });
  }

  // Handle Public Registration
  if (registerForm) {
    registerForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      hideAlert();

      const name = document.getElementById('name').value.trim();
      const email = document.getElementById('email').value.trim();
      const phone = document.getElementById('phone').value.trim();
      const dept = document.getElementById('dept').value.trim();
      const password = document.getElementById('password').value;
      const confirmPassword = document.getElementById('confirm-password').value;
      const submitBtn = registerForm.querySelector('button[type="submit"]');

      if (!name || !email || !password) {
        showAlert('Name, email, and password are required.');
        return;
      }

      if (password !== confirmPassword) {
        showAlert('Passwords do not match.');
        return;
      }

      if (password.length < 6) {
        showAlert('Password must be at least 6 characters.');
        return;
      }

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Creating Account...';
      }

      const res = await apiFetch('/api/auth/register', {
        method: 'POST',
        body: { name, email, phone, dept, password, role: 'student_staff' }
      });

      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Register Account';
      }

      if (res.ok) {
        showAlert('Account created successfully! Redirecting to login...', false);
        setTimeout(() => {
          window.location.href = res.data?.redirect_url || '/portal/login';
        }, 1200);
      } else {
        showAlert(res.data?.error || 'Registration failed.', true);
      }
    });
  }
});
