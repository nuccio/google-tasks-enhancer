// frontend/src/Header.tsx

import React from 'react';
import type { User } from './api';

interface HeaderProps {
    user: User | null;
    onSync: () => void;
    isSyncing: boolean;
}

const Header: React.FC<HeaderProps> = ({ user, onSync, isSyncing }) => {
    return (
        <header className="app-header">
            <div className="header-left">
                <h1>Google Tasks Enhancer</h1>
                {user && <span className="user-email">Logged in as: {user.email}</span>}
            </div>
            <div className="header-right">
                <button onClick={onSync} disabled={isSyncing} className="sync-button">
                    {isSyncing ? 'Syncing...' : 'Sync Now'}
                </button>
            </div>
        </header>
    );
};

export default Header;
