// frontend/src/TaskTable.tsx

import React from 'react';
import type { Task } from './api';
import TaskRow from './TaskRow';
import { useI18n } from './i18n/useI18n';

interface TaskTableProps {
    tasks: Task[];
    onTaskUpdate: (updatedTask: Task) => void;
}

const TaskTable: React.FC<TaskTableProps> = ({ tasks, onTaskUpdate }) => {
    const { t } = useI18n();
    const columns = t.table.columns;

    if (tasks.length === 0) {
        return <p>{t.table.empty}</p>;
    }

    return (
        <div className="task-table-container">
            <table className="task-table">
                <thead>
                    <tr>
                        <th>{columns.status}</th>
                        <th>{columns.title}</th>
                        <th>{columns.priority}</th>
                        <th>{columns.project}</th>
                        <th>{columns.estimatedTime}</th>
                        <th>{columns.dueDate}</th>
                        <th>{columns.notes}</th>
                        <th>{columns.link}</th>
                    </tr>
                </thead>
                <tbody>
                    {tasks.map(task => (
                        <TaskRow key={task.id} task={task} onTaskUpdate={onTaskUpdate} />
                    ))}
                </tbody>
            </table>
        </div>
    );
};

export default TaskTable;
