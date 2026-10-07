const requestBox = document.querySelector("#request");
const runButton = document.querySelector("#run");
const taskBox = document.querySelector("#task");
const eventsBox = document.querySelector("#events");
const approvalsSection = document.querySelector("#approvals-section");
const approvalsBox = document.querySelector("#approvals");

let activeTaskId = null;
let approvalsTimer = null;

function renderTask(task) {
  taskBox.textContent = JSON.stringify(task, null, 2);
}

function addEvent(event) {
  const row = document.createElement("div");
  row.className = "event";
  const title = document.createElement("strong");
  title.textContent = event.type || "EVENT";
  const meta = document.createElement("small");
  meta.textContent = event.timestamp ? " " + event.timestamp : "";
  const detail = document.createElement("div");
  detail.className = "event-data";
  detail.textContent = event.data ? JSON.stringify(event.data).slice(0, 200) : "";
  row.append(title, meta, detail);
  eventsBox.appendChild(row);
  eventsBox.scrollTop = eventsBox.scrollHeight;
}

function permissionLabel(level) {
  if (level === 1) return "LOW";
  if (level === 2) return "MEDIUM";
  if (level === 3) return "HIGH";
  return "LEVEL " + String(level);
}

function renderApprovals(approvals) {
  approvalsBox.replaceChildren();
  for (const approval of approvals) {
    const card = document.createElement("div");
    card.className = "approval " + (approval.status || "").toLowerCase();
    const title = document.createElement("strong");
    title.textContent = approval.tool_name || "tool";
    const meta = document.createElement("small");
    meta.textContent =
      " " + permissionLabel(approval.permission_level) +
      " — " + (approval.reason || "") +
      " — " + (approval.status || "PENDING");
    card.append(title, meta);
    if (approval.status === "PENDING") {
      const actions = document.createElement("div");
      actions.className = "actions";
      const approveButton = document.createElement("button");
      approveButton.textContent = "Approve";
      approveButton.className = "approve";
      approveButton.addEventListener("click", () => decideApproval(approval.id, true));
      const denyButton = document.createElement("button");
      denyButton.textContent = "Deny";
      denyButton.className = "deny";
      denyButton.addEventListener("click", () => decideApproval(approval.id, false));
      actions.append(approveButton, denyButton);
      card.append(actions);
    }
    approvalsBox.appendChild(card);
  }
}

async function refreshTask(taskId) {
  const response = await fetch("/tasks/" + encodeURIComponent(taskId));
  if (response.ok) renderTask(await response.json());
}

async function refreshApprovals(taskId) {
  if (!taskId) return;
  const response = await fetch("/approvals?task_id=" + encodeURIComponent(taskId));
  if (!response.ok) return;
  renderApprovals(await response.json());
}

async function decideApproval(approvalId, approved) {
  const response = await fetch("/approvals/" + encodeURIComponent(approvalId), {
    method: "POST",
    headers: {"content-type": "application/json"},
    body: JSON.stringify({approved})
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    addEvent({
      type: "APPROVAL_ERROR",
      timestamp: (detail.detail || "decision failed") + " (" + response.status + ")"
    });
  }
  await refreshApprovals(activeTaskId);
}

function stopApprovalsPolling() {
  if (approvalsTimer !== null) {
    clearInterval(approvalsTimer);
    approvalsTimer = null;
  }
}

function startApprovalsPolling() {
  stopApprovalsPolling();
  approvalsTimer = setInterval(() => refreshApprovals(activeTaskId), 1000);
}

runButton.addEventListener("click", async () => {
  const request = requestBox.value.trim();
  if (!request) return;
  runButton.disabled = true;
  eventsBox.replaceChildren();
  try {
    const response = await fetch("/tasks", {
      method: "POST",
      headers: {"content-type": "application/json"},
      body: JSON.stringify({request, input_channel: "text"})
    });
    const created = await response.json();
    if (!response.ok) throw new Error(created.detail || "request failed");
    activeTaskId = created.task_id;
    approvalsSection.hidden = false;
    renderApprovals([]);
    await refreshTask(activeTaskId);
    await refreshApprovals(activeTaskId);
    startApprovalsPolling();

    const socket = new WebSocket(
      (location.protocol === "https:" ? "wss://" : "ws://") +
      location.host + "/tasks/" + encodeURIComponent(activeTaskId) + "/events/stream"
    );
    socket.onmessage = async (message) => {
      const event = JSON.parse(message.data);
      if (event.type === "STREAM_COMPLETE") {
        socket.close();
        stopApprovalsPolling();
        await refreshTask(activeTaskId);
        await refreshApprovals(activeTaskId);
        runButton.disabled = false;
        return;
      }
      addEvent(event);
      await refreshTask(activeTaskId);
      await refreshApprovals(activeTaskId);
    };
    socket.onerror = () => {
      stopApprovalsPolling();
      runButton.disabled = false;
    };
    socket.onclose = () => {
      stopApprovalsPolling();
      runButton.disabled = false;
    };
  } catch (error) {
    addEvent({type: "ERROR", timestamp: String(error)});
    stopApprovalsPolling();
    runButton.disabled = false;
  }
});
