const requestBox = document.querySelector("#request");
const runButton = document.querySelector("#run");
const taskBox = document.querySelector("#task");
const eventsBox = document.querySelector("#events");

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
  row.append(title, meta);
  eventsBox.appendChild(row);
  eventsBox.scrollTop = eventsBox.scrollHeight;
}

async function refreshTask(taskId) {
  const response = await fetch("/tasks/" + encodeURIComponent(taskId));
  if (response.ok) renderTask(await response.json());
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
    await refreshTask(created.task_id);

    const socket = new WebSocket(
      (location.protocol === "https:" ? "wss://" : "ws://") +
      location.host + "/tasks/" + encodeURIComponent(created.task_id) + "/events/stream"
    );
    socket.onmessage = async (message) => {
      const event = JSON.parse(message.data);
      if (event.type === "STREAM_COMPLETE") {
        socket.close();
        await refreshTask(created.task_id);
        runButton.disabled = false;
        return;
      }
      addEvent(event);
      await refreshTask(created.task_id);
    };
    socket.onerror = () => { runButton.disabled = false; };
  } catch (error) {
    addEvent({type: "ERROR", timestamp: String(error)});
    runButton.disabled = false;
  }
});
