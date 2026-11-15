// frontend/src/LoginView.tsx

import React from 'react';
import LanguageSelect from './LanguageSelect';
import { useI18n } from './i18n/useI18n';

const LoginView: React.FC = () => {
    const { t } = useI18n();

    const handleLogin = () => {
        window.location.href = "/auth/login/google";
    };

    return (
        <div className="login-container">
            <LanguageSelect />
            <h1>{t.login.welcome}</h1>
            <p>{t.login.prompt}</p>
            <button onClick={handleLogin} className="login-button">
                {t.login.loginWithGoogle}
            </button>
        </div>
    );
};

export default LoginView;
