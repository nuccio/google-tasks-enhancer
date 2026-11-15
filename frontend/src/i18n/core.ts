// frontend/src/i18n/core.ts
//
// Framework-free core of the translation layer: pick the language, fall back
// to English, format dates and set <html lang>. Everything that touches the
// browser (storage, document) takes it as a parameter so tests can pass a
// stand-in; there is no jsdom in the test set-up.

import { enMessages } from './en';
import type { Messages } from './en';
import { itMessages } from './it';

/** The languages the UI is available in. */
export const LOCALES = ['en', 'it'] as const;
export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = 'en';

/** The single `localStorage` key that remembers the chosen language. */
export const STORAGE_KEY = 'gte.locale';

export type DeepPartial<T> = {
    [K in keyof T]?: T[K] extends (...args: never[]) => unknown ? T[K] : DeepPartial<T[K]>;
};

export type Dictionaries = Partial<Record<Locale, DeepPartial<Messages>>>;

const DICTIONARIES: Record<Locale, Messages> = {
    en: enMessages,
    it: itMessages,
};

/** The subset of `Storage` the layer uses. */
export interface StorageLike {
    getItem(key: string): string | null;
    setItem(key: string, value: string): void;
}

// A language tag such as `it`, `it-IT` or `it_IT`: a 2-3 letter language, then
// optional subtags. Anything else is malformed.
const LANGUAGE_TAG = /^([a-z]{2,3})(?:[-_][a-z0-9]+)*$/i;

/**
 * Map any value to a supported language. A regional code (`it-IT`) gives its
 * language; an unknown, empty or malformed value gives English.
 */
export function resolveLocale(code: unknown): Locale {
    if (typeof code !== 'string') return DEFAULT_LOCALE;
    const match = LANGUAGE_TAG.exec(code.trim());
    if (!match) return DEFAULT_LOCALE;
    const language = match[1].toLowerCase();
    return (LOCALES as readonly string[]).includes(language) ? (language as Locale) : DEFAULT_LOCALE;
}

/**
 * The browser storage, or null when it is blocked. Even reading the
 * `localStorage` property can throw (blocked site data, some private modes).
 */
export function getBrowserStorage(): StorageLike | null {
    try {
        return globalThis.localStorage ?? null;
    } catch {
        return null;
    }
}

/**
 * The language to start in: the saved one, or English when nothing is saved,
 * the saved value is not supported, or the storage is blocked. The browser
 * language (`navigator.language`) is deliberately not used.
 */
export function loadLocale(storage: StorageLike | null = getBrowserStorage()): Locale {
    if (!storage) return DEFAULT_LOCALE;
    try {
        return resolveLocale(storage.getItem(STORAGE_KEY));
    } catch {
        return DEFAULT_LOCALE;
    }
}

/** Remember the chosen language. Blocked storage is ignored. */
export function saveLocale(locale: Locale, storage: StorageLike | null = getBrowserStorage()): void {
    if (!storage) return;
    try {
        storage.setItem(STORAGE_KEY, locale);
    } catch {
        // Storage is blocked or full: the choice just does not survive a reload.
    }
}

/**
 * Lay `override` over `base`, key by key. A key that is missing, or whose type
 * differs from the English one, keeps the English value.
 */
function overlay<T>(base: T, override: unknown): T {
    if (typeof base === 'object' && base !== null) {
        const source = typeof override === 'object' && override !== null ? override : {};
        const result: Record<string, unknown> = {};
        for (const [key, value] of Object.entries(base)) {
            result[key] = overlay(value, Object.hasOwn(source, key) ? (source as Record<string, unknown>)[key] : undefined);
        }
        return result as T;
    }
    return typeof override === typeof base ? (override as T) : base;
}

/**
 * The dictionary to render with: the one of `locale` laid over the English one,
 * so a missing key shows the English text instead of nothing.
 */
export function getMessages(locale: Locale, dictionaries: Dictionaries = DICTIONARIES): Messages {
    return overlay(enMessages, dictionaries[locale]);
}

/** The name of each supported language in that language, for the selector. */
export function getLanguageOptions(): Array<{ locale: Locale; name: string }> {
    return LOCALES.map(locale => ({ locale, name: DICTIONARIES[locale].language.name }));
}

// An ISO date or date-time, as Google Tasks and the API return it.
// Otherwise the legacy day/month/year form.
const DAY_MONTH_YEAR = /^(\d{2})\/(\d{2})\/(\d{4})$/;

function parseCalendarDate(value: string): Date | null {
    let date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        const match = DAY_MONTH_YEAR.exec(value);
        if (!match) return null;
        date = new Date(Date.UTC(Number(match[3]), Number(match[2]) - 1, Number(match[1])));
    }
    return Number.isNaN(date.getTime()) ? null : date;
}

/**
 * Format a calendar date in the language of `locale`, medium style with the
 * month as a word ("Nov 15, 2026", "15 nov 2026"). The date is read in UTC:
 * Google stores a due date as a date only, so `2026-11-15T00:00:00.000Z` is the
 * 15th everywhere, also west of UTC. Returns null when `value` is not a date.
 */
export function formatDate(value: string, locale: Locale): string | null {
    const date = parseCalendarDate(value);
    if (!date) return null;
    return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeZone: 'UTC' }).format(date);
}

/** Make `<html lang>` follow the active language. */
export function setDocumentLang(doc: { documentElement: { lang: string } }, locale: Locale): void {
    doc.documentElement.lang = locale;
}
