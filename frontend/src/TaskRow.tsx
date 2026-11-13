// frontend/src/TaskRow.tsx

import React, { useState, useEffect } from 'react';
import type { Task } from './api';
import { updateTask } from './api';

interface TaskRowProps {
    task: Task;
    onTaskUpdate: (updatedTask: Task) => void;
}

const PRIORITY_OPTIONS = ['none', 'low', 'medium', 'high'];

const TaskRow: React.FC<TaskRowProps> = ({ task, onTaskUpdate }) => {
    const [localTask, setLocalTask] = useState<Task>(task);
    const [isUpdating, setIsUpdating] = useState(false);

    useEffect(() => {
        setLocalTask(task);
    }, [task]);

    const handleFieldChange = async (field: keyof Task, value: any) => {
        const updatedFields = { [field]: value };
        setLocalTask(prev => ({ ...prev, ...updatedFields }));
        setIsUpdating(true);
        try {
            const response = await updateTask(task.id, updatedFields);
            onTaskUpdate(response);
        } catch (error) {
            console.error("Failed to update task", error);
            // Revert to original task on error
            setLocalTask(task);
        } finally {
            setIsUpdating(false);
        }
    };

    const handleStatusChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const newStatus = e.target.checked ? "completed" : "needsAction";
        handleFieldChange("status", newStatus);
    };

    const handlePriorityChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        const newPriority = e.target.value === "none" ? null : e.target.value;
        handleFieldChange("priority", newPriority);
    };

    const handleProjectNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        handleFieldChange("project_name", e.target.value || null);
    };

    const handleEstimatedTimeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const value = parseInt(e.target.value, 10);
        handleFieldChange("estimated_time_minutes", isNaN(value) ? null : value);
    };

    const formatDueDate = (dateString: string | null) => {
        if (!dateString) return "-";
        try {
            // Attempt to parse ISO format first (e.g., from Google Tasks API)
            let date = new Date(dateString);
            // If parsing as ISO fails or results in an invalid date, try DD/MM/YYYY
            if (isNaN(date.getTime()) && dateString.match(/^\d{2}\/\d{2}\/\d{4}$/)) {
                const [day, month, year] = dateString.split('/').map(Number);
                date = new Date(year, month - 1, day);
            }
            if (!isNaN(date.getTime())) {
                return date.toLocaleDateString();
            }
            return dateString; // Return original if still invalid
        } catch (e) {
            return dateString; // Return original if any error occurs
        }
    };

    return (
        <tr className={`task-row ${localTask.status === "completed" ? "completed" : ""} ${isUpdating ? "updating" : ""}`}>
            <td>
                <input
                    type="checkbox"
                    checked={localTask.status === "completed"}
                    onChange={handleStatusChange}
                    disabled={isUpdating}
                />
            </td>
            <td>{localTask.title}</td>
            <td>
                <select
                    value={localTask.priority || "none"}
                    onChange={handlePriorityChange}
                    disabled={isUpdating}
                >
                    {PRIORITY_OPTIONS.map(option => (
                        <option key={option} value={option}>
                            {option.charAt(0).toUpperCase() + option.slice(1)}
                        </option>
                    ))}
                </select>
            </td>
            <td>
                <input
                    type="text"
                    value={localTask.project_name || ""}
                    onChange={handleProjectNameChange}
                    onBlur={() => handleFieldChange("project_name", localTask.project_name || null)}
                    disabled={isUpdating}
                />
            </td>
            <td>
                <input
                    type="number"
                    value={localTask.estimated_time_minutes !== null ? localTask.estimated_time_minutes : ""}
                    onChange={handleEstimatedTimeChange}
                    onBlur={() => handleFieldChange("estimated_time_minutes", localTask.estimated_time_minutes)}
                    disabled={isUpdating}
                    min="0"
                />
            </td>
            <td>{formatDueDate(localTask.due_date)}</td>
            <td>{localTask.notes || "-"}</td>
            <td>
                {
                    localTask.links && localTask.links.map((linkObj, index) => {
                        if (linkObj.type === "email") {
                            return <a key={index} href={linkObj.link} target="_blank" rel="noopener noreferrer">Mail</a>;
                        } else if (linkObj.type === "chat") {
                            return <a key={index} href={linkObj.link} target="_blank" rel="noopener noreferrer">Chat</a>;
                        }
                        return null;
                    })
                }
            </td>
        </tr>
    );
};

export default TaskRow;
