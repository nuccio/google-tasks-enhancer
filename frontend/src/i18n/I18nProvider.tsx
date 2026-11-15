// frontend/src/i18n/I18nProvider.tsx

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { I18nContext } from './context';
import type { I18n } from './context';
import { formatDate, getMessages, loadLocale, saveLocale, setDocumentLang } from './core';
import type { Locale } from './core';

export function I18nProvider({ children }: { children: ReactNode }) {
    const [locale, setLocaleState] = useState<Locale>(() => loadLocale());

    // `<html lang>` follows the active language at start-up and on every change.
    useEffect(() => {
        setDocumentLang(document, locale);
    }, [locale]);

    const setLocale = useCallback((next: Locale) => {
        saveLocale(next);
        setLocaleState(next);
    }, []);

    const value = useMemo<I18n>(
        () => ({
            locale,
            t: getMessages(locale),
            setLocale,
            formatDate: (date: string) => formatDate(date, locale),
        }),
        [locale, setLocale],
    );

    return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}
