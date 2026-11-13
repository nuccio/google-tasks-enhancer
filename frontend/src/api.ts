// frontend/src/api.ts

export interface Task {
    id: string;
    title: string;
    status: string;
    priority: string | null;
    project_name: string | null;
    hashtags: string | null;
    estimated_time_minutes: number | null;
    due_date: string | null;
    completed: string | null; // ISO format string
    updated: string | null; // ISO format string
    notes: string | null;
    links: Array<{ type: string; link: string }> | null;
}

export interface User {
    email: string;
}

export async function fetchTasks(): Promise<Task[]> {
    const response = await fetch("/tasks/");
    if (!response.ok) {
        if (response.status === 401) {
            // Not authenticated, trigger redirect via root path
            window.location.href = "/"; 
            return [];
        }
        throw new Error(`Error fetching tasks: ${response.statusText}`);
    }
    return response.json();
}

export async function syncTasks(): Promise<{ message: string }> {
    const response = await fetch("/tasks/sync", {
        method: "POST",
    });
    if (!response.ok) {
        throw new Error(`Error syncing tasks: ${response.statusText}`);
    }
    return response.json();
}

export async function updateTask(taskId: string, updates: Partial<Task>): Promise<Task> {
    const response = await fetch(`/tasks/${taskId}`, {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(updates),
    });
    if (!response.ok) {
        throw new Error(`Error updating task: ${response.statusText}`);
    }
    return response.json();
}

export async function fetchUser(): Promise<User | null> {
    try {
        const response = await fetch("/auth/me");

        if (response.status === 401) {
            return null; // Not authenticated
        }

        if (!response.ok) {
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.includes("application/json")) {
                const errorData = await response.json();
                throw new Error(`Error fetching user: ${errorData.detail || JSON.stringify(errorData)}`);
            } else {
                const errorText = await response.text();
                throw new Error(`Error fetching user: ${response.status} ${response.statusText} - ${errorText.substring(0, 100)}`);
            }
        }
        
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.includes("application/json")) {
            return response.json();
        } else {
            throw new Error(`Expected JSON but received ${contentType || 'no content type'}`);
        }

    } catch (error) {
        console.error("Error in fetchUser:", error);
        return null;
    }
}
