// frontend/src/TaskTable.tsx

import React from 'react';
import type { Task } from './api';
import TaskRow from './TaskRow';

interface TaskTableProps {
    tasks: Task[];
    onTaskUpdate: (updatedTask: Task) => void;
}

const TaskTable: React.FC<TaskTableProps> = ({ tasks, onTaskUpdate }) => {
    if (tasks.length === 0) {
        return <p>No tasks found. Click "Sync Now" to fetch your tasks from Google.</p>;
    }

    return (
        <div className="task-table-container">
            <table className="task-table">
                <thead>
                    <tr>
                        <th>Status</th>
                        <th>Title</th>
                        <th>Priority</th>
                        <th>Project</th>
                        <th>Est. Time (min)</th>
                        <th>Due Date</th>
                        <th>Notes</th>
                        <th>Link</th>
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
