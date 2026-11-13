// frontend/src/App.tsx

import { useState, useEffect, useCallback } from 'react';
import type { Task, User } from './api';
import { fetchTasks, fetchUser, syncTasks } from './api';
import Header from './Header';
import TaskTable from './TaskTable';
import LoginView from './LoginView';
import './App.css'; // Import main app styles

function App() {
    const [user, setUser] = useState<User | null>(null);
    const [tasks, setTasks] = useState<Task[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
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

    const loadUserData = useCallback(async () => {
        try {
            setLoading(true);
            const currentUser = await fetchUser();
            setUser(currentUser);
            if (currentUser) {
                const fetchedTasks = await fetchTasks();
                setTasks(sortTasks(fetchedTasks));
            }
        } catch (err) {
            setError((err as Error).message);
        } finally {
            setLoading(false);
        }
    }, [sortTasks]);

    useEffect(() => {
        loadUserData();
    }, [loadUserData]);

    const handleSync = async () => {
        setIsSyncing(true);
        setError(null);
        try {
            await syncTasks();
            // Re-fetch tasks after sync to get updated data and re-sort
            const fetchedTasks = await fetchTasks();
            setTasks(sortTasks(fetchedTasks));
        } catch (err) {
            setError((err as Error).message);
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
        return <div className="loading">Loading...</div>;
    }

    if (error) {
        return <div className="error">Error: {error}</div>;
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
