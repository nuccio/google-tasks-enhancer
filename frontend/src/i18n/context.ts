// frontend/src/i18n/context.ts

import { createContext } from 'react';
import type { Locale } from './core';
import type { Messages } from './en';

export interface I18n {
    /** The active language. */
    locale: Locale;
    /** The dictionary of the active language, laid over the English one. */
    t: Messages;
    /** Switch language and remember the choice in this browser. */
    setLocale: (locale: Locale) => void;
    /** A calendar date in the active language, or null when `value` is not a date. */
    formatDate: (value: string) => string | null;
}

export const I18nContext = createContext<I18n | null>(null);
