// frontend/src/LoginView.tsx

import React from 'react';

const LoginView: React.FC = () => {
    const handleLogin = () => {
        window.location.href = "/auth/login/google";
    };

    return (
        <div className="login-container">
            <h1>Welcome to Google Tasks Enhancer</h1>
            <p>Please log in with your Google account to manage your tasks.</p>
            <button onClick={handleLogin} className="login-button">
                Login with Google
            </button>
        </div>
    );
};

export default LoginView;
