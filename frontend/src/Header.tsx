// frontend/src/Header.tsx

import React from 'react';
import type { User } from './api';
import LanguageSelect from './LanguageSelect';
import { useI18n } from './i18n/useI18n';

interface HeaderProps {
    user: User | null;
    onSync: () => void;
    isSyncing: boolean;
}

const Header: React.FC<HeaderProps> = ({ user, onSync, isSyncing }) => {
    const { t } = useI18n();

    return (
        <header className="app-header">
            <div className="header-left">
                <h1>{t.app.title}</h1>
                {user && <span className="user-email">{t.header.loggedInAs(user.email)}</span>}
            </div>
            <div className="header-right">
                <LanguageSelect />
                <button onClick={onSync} disabled={isSyncing} className="sync-button">
                    {isSyncing ? t.header.syncing : t.header.syncNow}
                </button>
            </div>
        </header>
    );
};

export default Header;
