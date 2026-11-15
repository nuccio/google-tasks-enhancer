// frontend/src/TaskRow.tsx

import React, { useState } from 'react';
import type { Priority, Task } from './api';
import { updateTask } from './api';
import { useI18n } from './i18n/useI18n';

interface TaskRowProps {
    task: Task;
    onTaskUpdate: (updatedTask: Task) => void;
}

// The select value of an unset priority.
const NO_PRIORITY = '';
const PRIORITY_OPTIONS: Priority[] = ['low', 'medium', 'high'];

const TaskRow: React.FC<TaskRowProps> = ({ task, onTaskUpdate }) => {
    const { t, formatDate } = useI18n();
    const [localTask, setLocalTask] = useState<Task>(task);
    const [isUpdating, setIsUpdating] = useState(false);
    const [prevTask, setPrevTask] = useState<Task>(task);

    // Reset the local copy when the parent passes a new task object, during
    // render instead of in an effect:
    // https://react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes
    if (task !== prevTask) {
        setPrevTask(task);
        setLocalTask(task);
    }

    const handleFieldChange = async <K extends keyof Task>(field: K, value: Task[K]) => {
        const updatedFields: Partial<Task> = {};
        updatedFields[field] = value;
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
        const newPriority = PRIORITY_OPTIONS.find(option => option === e.target.value) ?? null;
        handleFieldChange("priority", newPriority);
    };

    const handleProjectNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        handleFieldChange("project_name", e.target.value || null);
    };

    const handleEstimatedTimeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const value = parseInt(e.target.value, 10);
        handleFieldChange("estimated_time_minutes", isNaN(value) ? null : value);
    };

    // A due date is a calendar date: read in UTC, shown in the active language.
    const formatDueDate = (dateString: string | null) => {
        if (!dateString) return t.table.emptyValue;
        return formatDate(dateString) ?? dateString; // Show the original if it is not a date
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
                    value={localTask.priority ?? NO_PRIORITY}
                    onChange={handlePriorityChange}
                    disabled={isUpdating}
                >
                    <option value={NO_PRIORITY}>{t.priority.none}</option>
                    {PRIORITY_OPTIONS.map(option => (
                        <option key={option} value={option}>
                            {t.priority[option]}
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
            <td>{localTask.notes || t.table.emptyValue}</td>
            <td>
                {
                    localTask.links && localTask.links.map((linkObj, index) => {
                        if (linkObj.type === "email") {
                            return <a key={index} href={linkObj.link} target="_blank" rel="noopener noreferrer">{t.table.links.email}</a>;
                        } else if (linkObj.type === "chat") {
                            return <a key={index} href={linkObj.link} target="_blank" rel="noopener noreferrer">{t.table.links.chat}</a>;
                        }
                        return null;
                    })
                }
            </td>
        </tr>
    );
};

export default TaskRow;
