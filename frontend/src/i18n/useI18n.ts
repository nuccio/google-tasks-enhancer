// frontend/src/i18n/useI18n.ts

import { useContext } from 'react';
import { I18nContext } from './context';
import type { I18n } from './context';

export function useI18n(): I18n {
    const value = useContext(I18nContext);
    if (!value) {
        throw new Error('useI18n must be used inside <I18nProvider>');
    }
    return value;
}
