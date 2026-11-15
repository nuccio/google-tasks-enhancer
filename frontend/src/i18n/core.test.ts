// frontend/src/i18n/core.test.ts
//
// Unit tests of the translation layer. They run in Node: the browser storage
// and the document are replaced by small stand-ins, so no jsdom is needed.

import { afterEach, describe, expect, test, vi } from 'vitest';
import {
    DEFAULT_LOCALE,
    LOCALES,
    STORAGE_KEY,
    formatDate,
    getLanguageOptions,
    getMessages,
    loadLocale,
    resolveLocale,
    saveLocale,
    setDocumentLang,
} from './core';
import type { Dictionaries, StorageLike } from './core';
import { enMessages } from './en';
import { itMessages } from './it';

function memoryStorage(initial: Record<string, string> = {}): StorageLike & { data: Record<string, string> } {
    const data = { ...initial };
    return {
        data,
        getItem: key => (key in data ? data[key] : null),
        setItem: (key, value) => {
            data[key] = value;
        },
    };
}

const blockedStorage: StorageLike = {
    getItem: () => {
        throw new Error('storage is blocked');
    },
    setItem: () => {
        throw new Error('storage is blocked');
    },
};

// Every path to a leaf of a dictionary, with the type of the leaf.
function leaves(value: unknown, path = ''): string[] {
    if (typeof value === 'object' && value !== null) {
        return Object.entries(value).flatMap(([key, child]) => leaves(child, path ? `${path}.${key}` : key));
    }
    return [`${path}:${typeof value}`];
}

describe('choosing the language', () => {
    test('English is the default when nothing is saved', () => {
        expect(loadLocale(memoryStorage())).toBe('en');
        expect(DEFAULT_LOCALE).toBe('en');
    });

    test('a saved supported language is used', () => {
        expect(loadLocale(memoryStorage({ [STORAGE_KEY]: 'it' }))).toBe('it');
    });

    test('an unknown or malformed code gives English', () => {
        for (const code of ['fr', '', ' ', 'xx-YY', 'it-', '-it', 'i', 'italiano', '__proto__', 'constructor', 'it IT', '<script>']) {
            expect(loadLocale(memoryStorage({ [STORAGE_KEY]: code })), JSON.stringify(code)).toBe('en');
        }
        for (const code of [null, undefined, 42, {}, ['it']]) {
            expect(resolveLocale(code)).toBe('en');
        }
    });

    test('blocked storage gives English and does not throw', () => {
        expect(loadLocale(blockedStorage)).toBe('en');
        expect(loadLocale(null)).toBe('en');
        expect(() => saveLocale('it', blockedStorage)).not.toThrow();
        expect(() => saveLocale('it', null)).not.toThrow();
    });

    test('a regional code gives its language', () => {
        expect(resolveLocale('it-IT')).toBe('it');
        expect(resolveLocale('it_IT')).toBe('it');
        expect(resolveLocale('IT')).toBe('it');
        expect(resolveLocale('en-GB')).toBe('en');
        expect(loadLocale(memoryStorage({ [STORAGE_KEY]: 'it-IT' }))).toBe('it');
    });

    test('the chosen language is saved under one key and read back', () => {
        const storage = memoryStorage();
        saveLocale('it', storage);
        expect(storage.data).toEqual({ 'gte.locale': 'it' });
        expect(loadLocale(storage)).toBe('it');
    });
});

describe('dictionaries', () => {
    test('an incomplete dictionary falls back to English for the missing key', () => {
        const incomplete: Dictionaries = {
            it: {
                header: { syncNow: 'Sync (translated)' },
                priority: { high: 'High (translated)' },
            },
        };
        const t = getMessages('it', incomplete);
        expect(t.header.syncNow).toBe('Sync (translated)');
        expect(t.priority.high).toBe('High (translated)');
        // Missing in the incomplete dictionary: the English text, not nothing.
        expect(t.header.syncing).toBe(enMessages.header.syncing);
        expect(t.priority.low).toBe(enMessages.priority.low);
        expect(t.header.loggedInAs('a@example.com')).toBe('Logged in as: a@example.com');
        expect(t.table.columns.title).toBe('Title');
    });

    test('a language without a dictionary, or with a value of the wrong type, gives English', () => {
        expect(getMessages('it', {})).toEqual(enMessages);
        const wrong = { it: { header: { syncNow: 42, loggedInAs: 'not a function' } } } as unknown as Dictionaries;
        const t = getMessages('it', wrong);
        expect(t.header.syncNow).toBe('Sync Now');
        expect(t.header.loggedInAs('a@example.com')).toBe('Logged in as: a@example.com');
    });

    test('the Italian dictionary has every English key', () => {
        expect(leaves(itMessages)).toEqual(leaves(enMessages));
    });

    test('the active dictionary is the one of the language', () => {
        expect(getMessages('en').header.syncNow).toBe('Sync Now');
        expect(getMessages('it').header.syncNow).toBe(itMessages.header.syncNow);
        expect(getMessages('it').header.syncNow).not.toBe(enMessages.header.syncNow);
        expect(getMessages('it').header.loggedInAs('a@example.com')).toBe(itMessages.header.loggedInAs('a@example.com'));
    });

    test('every language is listed by its own name', () => {
        expect(getLanguageOptions()).toEqual([
            { locale: 'en', name: 'English' },
            { locale: 'it', name: itMessages.language.name },
        ]);
        expect(getLanguageOptions().map(option => option.locale)).toEqual([...LOCALES]);
    });
});

describe('dates', () => {
    afterEach(() => {
        vi.unstubAllEnvs();
    });

    test('are formatted in the active language, month as a word', () => {
        expect(formatDate('2026-11-15T00:00:00.000Z', 'en')).toBe('Nov 15, 2026');
        expect(formatDate('2026-11-15T00:00:00.000Z', 'it')).toBe('15 nov 2026');
    });

    test('a due date of 2026-11-15T00:00:00.000Z is 15 November west of UTC', () => {
        vi.stubEnv('TZ', 'America/Los_Angeles');
        // The precondition: in this time zone the instant is on the 14th.
        expect(new Date('2026-11-15T00:00:00.000Z').getDate()).toBe(14);
        expect(formatDate('2026-11-15T00:00:00.000Z', 'en')).toBe('Nov 15, 2026');
        expect(formatDate('2026-11-15T00:00:00.000Z', 'it')).toBe('15 nov 2026');
    });

    test('are the same east of UTC', () => {
        vi.stubEnv('TZ', 'Pacific/Auckland');
        expect(formatDate('2026-11-15T00:00:00.000Z', 'en')).toBe('Nov 15, 2026');
    });

    test('accept the legacy day/month/year form, and reject what is not a date', () => {
        expect(formatDate('15/11/2026', 'en')).toBe('Nov 15, 2026');
        expect(formatDate('not a date', 'en')).toBeNull();
        expect(formatDate('', 'en')).toBeNull();
    });
});

describe('<html lang>', () => {
    test('is set on the document for each language', () => {
        const doc = { documentElement: { lang: 'en' } };
        setDocumentLang(doc, 'it');
        expect(doc.documentElement.lang).toBe('it');
        setDocumentLang(doc, 'en');
        expect(doc.documentElement.lang).toBe('en');
    });
});
