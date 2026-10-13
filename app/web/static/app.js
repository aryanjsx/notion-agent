let currentTaskId = null;
let pollInterval = null;

const form = document.getElementById("task-form");
const promptInput = document.getElementById("prompt");
const attachmentInput = document.getElementById("attachment");
const modeSelect = document.getElementById("mode");
const submitBtn = document.getElementById("submit-btn");
const statusPill = document.getElementById("task-status-pill");
const summaryBox = document.getElementById("task-summary-box");
const summaryText = document.getElementById("task-summary-text");
const createdLinksList = document.getElementById("created-links-list");
const confirmationBox = document.getElementById("confirmation-box");
const confirmationReason = document.getElementById("confirmation-reason");
const approveBtn = document.getElementById("approve-btn");
const rejectBtn = document.getElementById("reject-btn");
const stepsContainer = document.getElementById("steps-container");
const uploadStatus = document.getElementById("upload-status");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const prompt = promptInput.value.trim();
  if (!prompt) return;

  submitBtn.disabled = true;
  submitBtn.textContent = "Submitting...";
  resetUI();

  let attachments = [];
  if (attachmentInput.files.length > 0) {
    const file = attachmentInput.files[0];
    uploadStatus.textContent = `Uploading ${file.name}...`;
    const formData = new FormData();
    formData.append("file", file);
    try {
      const uploadRes = await fetch("/tasks/upload", {
        method: "POST",
        body: formData,
      });
      const uploadData = await uploadRes.json();
      attachments.push(uploadData.storage_uri);
      uploadStatus.textContent = `Uploaded: ${file.name}`;
    } catch (err) {
      uploadStatus.textContent = `Upload failed: ${err.message}`;
    }
  }

  const notifyChannels = [];
  if (document.getElementById("notify-notion").checked) notifyChannels.push("notion_comment");
  if (document.getElementById("notify-slack").checked) notifyChannels.push("slack");
  if (document.getElementById("notify-email").checked) notifyChannels.push("email");

  const payload = {
    prompt,
    mode: modeSelect.value,
    attachments,
    notify_channels: notifyChannels,
  };

  try {
    const res = await fetch("/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const task = await res.json();
    currentTaskId = task.task_id;
    updateStatusPill(task.status);
    startPolling(currentTaskId);
  } catch (err) {
    alert("Error submitting task: " + err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "🚀 Run Agent";
  }
});

function resetUI() {
  if (pollInterval) clearInterval(pollInterval);
  summaryBox.style.display = "none";
  confirmationBox.style.display = "none";
  createdLinksList.innerHTML = "";
  stepsContainer.innerHTML = "<p class='placeholder-text'>Planning steps...</p>";
}

function startPolling(taskId) {
  if (pollInterval) clearInterval(pollInterval);
  pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/tasks/${taskId}`);
      if (!res.ok) return;
      const task = await res.json();
      renderTask(task);

      if (["succeeded", "failed", "cancelled"].includes(task.status)) {
        clearInterval(pollInterval);
      }
    } catch (e) {
      console.error("Polling error", e);
    }
  }, 1200);
}

function renderTask(task) {
  updateStatusPill(task.status);

  // Render Steps
  if (task.steps && task.steps.length > 0) {
    stepsContainer.innerHTML = "";
    task.steps.forEach((s) => {
      const div = document.createElement("div");
      div.className = `step-item ${s.status}`;
      div.innerHTML = `
        <div class="step-header">
          <span>Step ${s.step_number}: ${s.title}</span>
          <span>${s.status.toUpperCase()}</span>
        </div>
        ${s.tool_name ? `<div class="step-tool">Tool: ${s.tool_name}</div>` : ""}
        ${s.error ? `<div style="color: var(--danger); margin-top: 4px;">Error: ${s.error}</div>` : ""}
      `;
      stepsContainer.appendChild(div);
    });
  }

  // Render Confirmation Gate
  if (task.status === "awaiting_confirmation") {
    confirmationBox.style.display = "block";
    confirmationReason.textContent = "A sensitive or destructive operation requires your approval before proceeding.";
  } else {
    confirmationBox.style.display = "none";
  }

  // Render Completion Summary & Links
  if (task.summary || (task.created_links && task.created_links.length > 0)) {
    summaryBox.style.display = "block";
    summaryText.textContent = task.summary || "Task finished.";
    if (task.created_links && task.created_links.length > 0) {
      createdLinksList.innerHTML = "";
      task.created_links.forEach((l) => {
        const li = document.createElement("li");
        li.innerHTML = `<a href="${l.url}" target="_blank" rel="noopener noreferrer">${l.title} (${l.type}) ↗</a>`;
        createdLinksList.appendChild(li);
      });
    }
  }
}

function updateStatusPill(status) {
  statusPill.className = `status-pill status-${status}`;
  statusPill.textContent = status.replace("_", " ");
}

approveBtn.addEventListener("click", async () => {
  if (!currentTaskId) return;
  await fetch(`/tasks/${currentTaskId}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved: true }),
  });
  confirmationBox.style.display = "none";
});

rejectBtn.addEventListener("click", async () => {
  if (!currentTaskId) return;
  await fetch(`/tasks/${currentTaskId}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved: false }),
  });
  confirmationBox.style.display = "none";
});
