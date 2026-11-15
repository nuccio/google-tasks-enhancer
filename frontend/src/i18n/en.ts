// frontend/src/i18n/en.ts
//
// The reference dictionary. Its shape is the type every other language must
// satisfy (see `Messages`), so a key missing in another language fails the
// type-check in `npm run build`. A text that takes a value is a typed function.

export const enMessages = {
    language: {
        // Accessible name of the language selector.
        label: 'Language',
        // The name of this language in itself, listed in the selector.
        name: 'English',
    },
    app: {
        title: 'Google Tasks Enhancer',
        loading: 'Loading...',
    },
    errors: {
        loadTasks: 'Could not load your tasks',
        syncTasks: 'Could not sync your tasks',
    },
    header: {
        loggedInAs: (email: string) => `Logged in as: ${email}`,
        syncNow: 'Sync Now',
        syncing: 'Syncing...',
    },
    login: {
        welcome: 'Welcome to Google Tasks Enhancer',
        prompt: 'Please log in with your Google account to manage your tasks.',
        loginWithGoogle: 'Login with Google',
    },
    table: {
        empty: 'No tasks found. Click "Sync Now" to fetch your tasks from Google.',
        columns: {
            status: 'Status',
            title: 'Title',
            priority: 'Priority',
            project: 'Project',
            estimatedTime: 'Est. Time (min)',
            dueDate: 'Due Date',
            notes: 'Notes',
            link: 'Link',
        },
        // Shown where a task has no value (for example no due date).
        emptyValue: '-',
        links: {
            email: 'Mail',
            chat: 'Chat',
        },
    },
    priority: {
        none: 'None',
        low: 'Low',
        medium: 'Medium',
        high: 'High',
    },
};

export type Messages = typeof enMessages;
