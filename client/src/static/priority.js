document.addEventListener("DOMContentLoaded", () => {
    const statusEl = document.getElementById("priority-status");
    const tbody = document.getElementById("priority-table-body");

    async function loadPrioritizedTasks() {
      statusEl.textContent = "Loading tasks...";

      try {
          const url = `${BACKEND_URL}/tasks/priorities?username=${encodeURIComponent(CURRENT_USER)}`;
          const res = await fetch(url);
          if (!res.ok) {
              throw new Error(`Failed to fetch prioritized tasks: ${res.status}`);
          }
          const tasks = await res.json();
          renderTable(tasks);
          statusEl.textContent = `Loaded ${tasks.length} task(s).`;
      } catch (err) {
          console.error(err);
          statusEl.textContent = "Error loading tasks.";
      }
    }
    function renderTable(tasks) {
      tbody.innerHTML = "";

      tasks.forEach((t, idx) => {
          const row = document.createElement("tr");
          row.innerHTML = `
              <td class="px-4 py-2 text-center">${idx + 1}</td>
              <td class="px-4 py-2">${t.event_name || ""}</td>
              <td class="px-4 py-2">${t.due_date || t.date || ""}</td>
              <td class="px-4 py-2">
                  <span class="px-3 py-1 rounded-full text-white text-sm ${
                      t.priority === "High"
                          ? "bg-red-500"
                          : t.priority === "Medium"
                          ? "bg-yellow-500"
                          : "bg-green-500"
                  }">
                      ${t.priority}
                  </span>
              </td>
              <td class="px-4 py-2 text-sm text-gray-600">
                  ${t.event_description || ""}
              </td>
          `;
          tbody.appendChild(row);
      });
    }

    
    function priorityColor(level) {
        if (level === "High") return "bg-red-500";
        if (level === "Medium") return "bg-yellow-500";
        return "bg-green-500"; // Low or anything else
    }

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    loadPrioritizedTasks();
});

