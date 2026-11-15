// frontend/src/App.tsx

import { useState, useEffect, useCallback } from 'react';
import type { Task, User } from './api';
import { fetchTasks, fetchUser, syncTasks } from './api';
import Header from './Header';
import TaskTable from './TaskTable';
import LoginView from './LoginView';
import { useI18n } from './i18n/useI18n';
import './App.css'; // Import main app styles

function App() {
    const { t } = useI18n();
    const [user, setUser] = useState<User | null>(null);
    const [tasks, setTasks] = useState<Task[]>([]);
    const [loading, setLoading] = useState(true);
    // Which request failed. The sentence shown comes from the dictionary, so it
    // follows the language; the technical detail goes to the browser console.
    const [error, setError] = useState<'loadTasks' | 'syncTasks' | null>(null);
    const [isSyncing, setIsSyncing] = useState(false);

    const sortTasks = useCallback((tasksToSort: Task[]): Task[] => {
        const incompleteTasks = tasksToSort.filter(task => task.status === 'needsAction');
        const completedTasks = tasksToSort.filter(task => task.status === 'completed');

        // Sort incomplete tasks by due date, soonest first
        incompleteTasks.sort((a, b) => {
            if (!a.due_date && !b.due_date) return 0;
            if (!a.due_date) return 1;
            if (!b.due_date) return -1;
            // Sort ascending (soonest due date first)
            return new Date(a.due_date).getTime() - new Date(b.due_date).getTime();
        });

        // Sort completed tasks by completed date, most recently completed first
        completedTasks.sort((a, b) => {
            if (!a.completed && !b.completed) return 0;
            if (!a.completed) return 1;
            if (!b.completed) return -1;
            return new Date(b.completed).getTime() - new Date(a.completed).getTime();
        });

        return [...incompleteTasks, ...completedTasks];
    }, []);

    // Initial load, once on mount. `loading` already starts as true; state is
    // only set from the promise callbacks, after the requests have finished.
    useEffect(() => {
        fetchUser()
            .then(async currentUser => {
                setUser(currentUser);
                if (currentUser) {
                    const fetchedTasks = await fetchTasks();
                    setTasks(sortTasks(fetchedTasks));
                }
            })
            .catch((err: unknown) => {
                console.error('Could not load tasks', err);
                setError('loadTasks');
            })
            .finally(() => {
                setLoading(false);
            });
    }, [sortTasks]);

    const handleSync = async () => {
        setIsSyncing(true);
        setError(null);
        try {
            await syncTasks();
            // Re-fetch tasks after sync to get updated data and re-sort
            const fetchedTasks = await fetchTasks();
            setTasks(sortTasks(fetchedTasks));
        } catch (err) {
            console.error('Could not sync tasks', err);
            setError('syncTasks');
        } finally {
            setIsSyncing(false);
        }
    };

    const handleTaskUpdate = useCallback((updatedTask: Task) => {
        setTasks(prevTasks =>
            sortTasks(prevTasks.map(task => (task.id === updatedTask.id ? updatedTask : task)))
        );
    }, [sortTasks]);

    if (loading) {
        return <div className="loading">{t.app.loading}</div>;
    }

    if (error) {
        return <div className="error">{t.errors[error]}</div>;
    }

    return (
        <div className="App">
            {!user ? (
                <LoginView />
            ) : (
                <>
                    <Header user={user} onSync={handleSync} isSyncing={isSyncing} />
                    <main className="main-content">
                        <TaskTable tasks={tasks} onTaskUpdate={handleTaskUpdate} />
                    </main>
                </>
            )}
        </div>
    );
}

export default App;
