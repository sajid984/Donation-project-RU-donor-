// /assets/js/main.js
document.addEventListener('DOMContentLoaded', () => {
    // Toggle password visibility for login form
    const toggleLoginPassword = document.querySelector('#login-eye');
    const loginPassword = document.querySelector('#login-pass');
    
    toggleLoginPassword.addEventListener('click', () => {
        togglePasswordVisibility(toggleLoginPassword, loginPassword);
    });
 
    // Toggle password visibility for register form
    const toggleRegisterPassword = document.querySelector('#register-eye');
    const registerPassword = document.querySelector('#register-pass');
    
    toggleRegisterPassword.addEventListener('click', () => {
        togglePasswordVisibility(toggleRegisterPassword, registerPassword);
    });
 
    // Function to toggle password visibility
    function togglePasswordVisibility(toggleElement, passwordField) {
        const type = passwordField.getAttribute('type') === 'password' ? 'text' : 'password';
        passwordField.setAttribute('type', type);
        
        // Toggle the icon classes
        toggleElement.classList.toggle('ri-eye-line');
        toggleElement.classList.toggle('ri-eye-off-line');
    }
 });
 