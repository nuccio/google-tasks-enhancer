// frontend/src/i18n/it.ts
//
// Italian dictionary. Declaring it as `Messages` makes a missing key, or a key
// with the wrong parameters, a type error in `npm run build`.

import type { Messages } from './en';

export const itMessages: Messages = {
    language: {
        label: 'Lingua',
        name: 'Italiano',
    },
    app: {
        title: 'Google Tasks Enhancer',
        loading: 'Caricamento...',
    },
    errors: {
        loadTasks: 'Impossibile caricare le tue attività',
        syncTasks: 'Impossibile sincronizzare le tue attività',
    },
    header: {
        loggedInAs: (email: string) => `Accesso eseguito come: ${email}`,
        syncNow: 'Sincronizza ora',
        syncing: 'Sincronizzazione...',
    },
    login: {
        welcome: 'Benvenuto in Google Tasks Enhancer',
        prompt: 'Accedi con il tuo account Google per gestire le tue attività.',
        loginWithGoogle: 'Accedi con Google',
    },
    table: {
        empty: 'Nessuna attività trovata. Fai clic su "Sincronizza ora" per scaricare le tue attività da Google.',
        columns: {
            status: 'Stato',
            title: 'Titolo',
            priority: 'Priorità',
            project: 'Progetto',
            estimatedTime: 'Tempo stimato (min)',
            dueDate: 'Scadenza',
            notes: 'Note',
            link: 'Link',
        },
        emptyValue: '-',
        links: {
            email: 'Mail',
            chat: 'Chat',
        },
    },
    priority: {
        none: 'Nessuna',
        low: 'Bassa',
        medium: 'Media',
        high: 'Alta',
    },
};
