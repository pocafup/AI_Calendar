document.addEventListener("DOMContentLoaded", () => {
    console.log("[Calendar.js] Loaded. BACKEND_URL =", BACKEND_URL, "CURRENT_USER =", CURRENT_USER);

    const monthName = document.getElementById("month-name");
    const grid = document.getElementById("calendar-grid");
    const taskList = document.getElementById("task-list");
    const modal = document.getElementById("task-modal");
    const modalDate = document.getElementById("modal-date");
    const taskForm = document.getElementById("task-form");
    const addTaskBtn = document.getElementById("add-task-btn");
    const saveBtn = document.getElementById("task-save-btn");

    let current = new Date();
    let selectedDate = null;
    let currentTasks = [];

    // ---------------------- Calendar Rendering ----------------------

    function renderCalendar() {
        grid.innerHTML = "";
        monthName.textContent = current.toLocaleString("default", {
            month: "long",
            year: "numeric",
        });

        const firstDay = new Date(current.getFullYear(), current.getMonth(), 1).getDay();
        const days = new Date(current.getFullYear(), current.getMonth() + 1, 0).getDate();

        // Empty slots before the first day
        for (let i = 0; i < firstDay; i++) {
            grid.innerHTML += `<div></div>`;
        }

        // Day cells
        for (let d = 1; d <= days; d++) {
            const dateKey = formatDate(current.getFullYear(), current.getMonth(), d);

            grid.innerHTML += `
                <div
                    class="p-3 text-center border rounded-lg bg-white hover:bg-blue-100 cursor-pointer"
                    onclick="selectDate('${dateKey}')"
                >
                    ${d}
                </div>
            `;
        }
    }

    // Global function used by inline onclick
    window.selectDate = async (dateKey) => {
        selectedDate = dateKey;
        modalDate.textContent = selectedDate;
        console.log("[Calendar] Selected date:", selectedDate);
        await loadTasksForSelectedDate();
    };

    // ---------------------- Backend Calls ----------------------

    async function loadTasksForSelectedDate() {
        if (!selectedDate) {
            taskList.innerHTML = `<p class="text-gray-500">Select a date to view tasks.</p>`;
            return;
        }

        try {
            const url = `${BACKEND_URL}/tasks?date=${encodeURIComponent(
                selectedDate
            )}&username=${encodeURIComponent(CURRENT_USER)}`;
            console.log("[Calendar] Fetching tasks from:", url);

            const res = await fetch(url);
            if (!res.ok) {
                console.error("[Calendar] GET /tasks failed:", res.status);
                throw new Error(`Failed to fetch tasks: ${res.status}`);
            }

            currentTasks = await res.json();
            console.log("[Calendar] Tasks from server:", currentTasks);
            renderTasks();
        } catch (err) {
            console.error(err);
            taskList.innerHTML = `<p class="text-red-500">Error loading tasks.</p>`;
        }
    }

    async function createTaskOnServer({ text, description, priority, dueDate, deadline }) {
        let eventDescription = description || "";

        // Attach due date / deadline metadata
        const metaParts = [];
        if (dueDate) metaParts.push(`Due: ${dueDate}`);
        if (deadline) metaParts.push(`Time: ${deadline}`);
        const metaStr = metaParts.join(" | ");

        if (metaStr) {
            eventDescription = eventDescription
                ? `${eventDescription}\n\n${metaStr}`
                : metaStr;
        }

        const payload = {
          event_name: text,
          event_description: eventDescription,
          date: selectedDate,          // calendar day
          due_date: dueDate || null,   // actual due date for ranking
          priority: priority,
          username: CURRENT_USER,
        };

        
        console.log("[Calendar] Creating task with payload:", payload);

        const res = await fetch(`${BACKEND_URL}/tasks`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });

        if (!res.ok) {
            const errText = await res.text();
            console.error("[Calendar] POST /tasks failed:", res.status, errText);
            throw new Error(`Failed to create task: ${res.status} ${errText}`);
        }

        const created = await res.json();
        console.log("[Calendar] Created task:", created);
        return created;
    }

    // ---------------------- Task Rendering ----------------------

    function renderTasks() {
        taskList.innerHTML = "";

        if (!selectedDate) {
            taskList.innerHTML = `<p class="text-gray-500">Select a date to view tasks.</p>`;
            return;
        }

        if (!currentTasks || currentTasks.length === 0) {
            taskList.innerHTML = `<p class="text-gray-500">No tasks for this day.</p>`;
            return;
        }

        currentTasks.forEach((task) => {
            const priorityClass = priorityColor(task.priority);

            taskList.innerHTML += `
                <div class="p-3 bg-white shadow rounded-lg mb-2">
                    <div class="flex justify-between">
                        <span>${escapeHtml(task.event_name || "")}</span>
                        <span class="px-3 py-1 rounded text-white text-sm ${priorityClass}">
                            ${task.priority || "Medium"}
                        </span>
                    </div>

                    ${
                        task.event_description
                            ? `<div class="text-sm text-gray-600 mt-1 whitespace-pre-line">
                                   ${escapeHtml(task.event_description)}
                               </div>`
                            : ""
                    }
                </div>
            `;
        });
    }

    // ---------------------- Modal & Form ----------------------

    addTaskBtn.onclick = () => {
        if (!selectedDate) {
            alert("Please select a date first.");
            console.warn("[Calendar] Add Task clicked with no selectedDate");
            return;
        }
        console.log("[Calendar] Opening modal for date:", selectedDate);
        modal.classList.remove("hidden");
    };

    window.closeModal = () => {
        modal.classList.add("hidden");
    };

    console.log("[Calendar] taskForm:", taskForm);
    console.log("[Calendar] saveBtn:", saveBtn);

    // Use form submit (simpler) – Save button is type="submit"
    taskForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        console.log("[Calendar] Form submit handler fired");

        if (!selectedDate) {
            alert("Please select a date first.");
            console.warn("[Calendar] Submit with no selectedDate");
            return;
        }

        const text = document.getElementById("task-text").value.trim();
        const description = document.getElementById("task-description").value.trim();
        const priority = document.getElementById("task-priority").value;
        const dueDate = document.getElementById("task-due-date").value;
        const deadline = document.getElementById("task-deadline").value;

        console.log("[Calendar] Form values:", {
            text,
            description,
            priority,
            dueDate,
            deadline,
            selectedDate,
            CURRENT_USER,
        });

        if (!text) {
            alert("Task title is required.");
            console.warn("[Calendar] Empty task title, aborting");
            return;
        }

        try {
            await createTaskOnServer({ text, description, priority, dueDate, deadline });
            taskForm.reset();
            closeModal();
            await loadTasksForSelectedDate();
        } catch (err) {
            console.error("[Calendar] Error saving task:", err);
            alert("Error saving task. See console for details.");
        }
    });

    // ---------------------- Helpers ----------------------

    function priorityColor(level) {
        if (level === "High") return "bg-red-500";
        if (level === "Medium") return "bg-yellow-500";
        return "bg-green-500"; // Low or anything else
    }

    function formatDate(y, m, d) {
        return `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    }

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Month navigation
    document.getElementById("prev").onclick = () => {
        current.setMonth(current.getMonth() - 1);
        renderCalendar();
    };

    document.getElementById("next").onclick = () => {
        current.setMonth(current.getMonth() + 1);
        renderCalendar();
    };

    // Initial render
    renderCalendar();
});


