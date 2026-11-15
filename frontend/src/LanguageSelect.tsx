// frontend/src/LanguageSelect.tsx

import React from 'react';
import { getLanguageOptions, resolveLocale } from './i18n/core';
import { useI18n } from './i18n/useI18n';

const OPTIONS = getLanguageOptions();

const LanguageSelect: React.FC = () => {
    const { locale, setLocale, t } = useI18n();

    return (
        <select
            className="language-select"
            aria-label={t.language.label}
            value={locale}
            onChange={e => setLocale(resolveLocale(e.target.value))}
        >
            {OPTIONS.map(option => (
                <option key={option.locale} value={option.locale}>
                    {option.name}
                </option>
            ))}
        </select>
    );
};

export default LanguageSelect;
