const state = {
  date: todayStr(),
  habits: [],
  checks: new Set(), // "habitId:date"
  editing: null,
};

function todayStr() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function fmtJaDate(s) {
  const d = new Date(s + "T00:00:00");
  const days = ["日", "月", "火", "水", "木", "金", "土"];
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日（${days[d.getDay()]}）`;
}

function shiftDate(s, delta) {
  const d = new Date(s + "T00:00:00");
  d.setDate(d.getDate() + delta);
  return d.toISOString().slice(0, 10);
}

async function fetchJson(url, opts = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`${res.status}: ${err}`);
  }
  return res.json();
}

async function loadAll() {
  const [habits, checks] = await Promise.all([
    fetchJson("/api/habits"),
    fetchJson(`/api/checks?start=${state.date}&end=${state.date}`),
  ]);
  state.habits = habits;
  state.checks = new Set(checks.map(c => `${c.habit_id}:${c.check_date}`));
  render();
}

function render() {
  document.getElementById("date-input").value = state.date;
  document.getElementById("date-label").textContent = fmtJaDate(state.date);

  for (const type of ["morning", "evening"]) {
    const list = document.getElementById(`${type}-list`);
    list.innerHTML = "";
    const items = state.habits
      .filter(h => h.task_type === type)
      .sort((a, b) => a.sort_order - b.sort_order);

    if (items.length === 0) {
      const li = document.createElement("li");
      li.className = "text-xs text-gray-400 text-center py-3";
      li.textContent = "タスクが登録されていません";
      list.appendChild(li);
    }

    let checkedCount = 0;
    for (const h of items) {
      const key = `${h.id}:${state.date}`;
      const checked = state.checks.has(key);
      if (checked) checkedCount++;

      const li = document.createElement("li");
      li.dataset.id = h.id;
      li.className = `flex items-center gap-2 p-3 rounded-md border cursor-grab active:cursor-grabbing ${
        checked ? "bg-emerald-50 border-emerald-200" : "bg-white border-gray-200"
      }`;

      li.innerHTML = `
        <span class="drag-handle text-gray-300 select-none touch-none px-1" aria-label="ドラッグ">⋮⋮</span>
        <button class="check-btn flex-1 flex items-center gap-3 text-left">
          <span class="w-6 h-6 rounded-full border-2 flex items-center justify-center shrink-0 ${
            checked ? "bg-emerald-500 border-emerald-500" : "border-gray-300"
          }">
            ${checked ? '<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>' : ""}
          </span>
          <span class="${checked ? "line-through text-gray-400" : ""}">${escapeHtml(h.name)}</span>
        </button>
        <a href="/stats?habit=${h.id}" class="text-xs text-gray-400 hover:text-gray-600 px-1" title="集計を見る">📊</a>
        <button class="edit-btn text-xs text-gray-400 hover:text-gray-600 px-1" title="編集">✎</button>
      `;
      li.querySelector(".check-btn").addEventListener("click", () => toggleCheck(h.id));
      li.querySelector(".edit-btn").addEventListener("click", () => openEdit(h));
      list.appendChild(li);
    }

    document.getElementById(`${type}-progress`).textContent =
      items.length ? `${checkedCount} / ${items.length}` : "";
  }

  initSortable();
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

let sortables = [];
function initSortable() {
  for (const s of sortables) s.destroy();
  sortables = [];
  for (const type of ["morning", "evening"]) {
    const el = document.getElementById(`${type}-list`);
    sortables.push(new Sortable(el, {
      group: "habits",
      handle: ".drag-handle",
      animation: 150,
      onEnd: persistOrder,
    }));
  }
}

async function persistOrder() {
  const items = [];
  for (const type of ["morning", "evening"]) {
    const lis = document.querySelectorAll(`#${type}-list li[data-id]`);
    lis.forEach((li, idx) => {
      items.push({
        id: Number(li.dataset.id),
        sort_order: idx,
        task_type: type,
      });
    });
  }
  // Optimistic local update
  for (const it of items) {
    const h = state.habits.find(h => h.id === it.id);
    if (h) {
      h.sort_order = it.sort_order;
      h.task_type = it.task_type;
    }
  }
  await fetchJson("/api/habits/reorder", {
    method: "POST",
    body: JSON.stringify({ items }),
  });
}

async function toggleCheck(habitId) {
  const key = `${habitId}:${state.date}`;
  // Optimistic
  const wasChecked = state.checks.has(key);
  if (wasChecked) state.checks.delete(key);
  else state.checks.add(key);
  render();

  try {
    await fetchJson("/api/checks/toggle", {
      method: "POST",
      body: JSON.stringify({ habit_id: habitId, check_date: state.date }),
    });
  } catch (e) {
    // Revert
    if (wasChecked) state.checks.add(key);
    else state.checks.delete(key);
    render();
    alert("チェックの保存に失敗しました: " + e.message);
  }
}

// ----- Habit modal -----

function openAdd(type) {
  state.editing = null;
  document.getElementById("habit-modal-title").textContent = "タスクを追加";
  document.getElementById("habit-name").value = "";
  document.querySelector(`input[name="habit-type"][value="${type}"]`).checked = true;
  document.getElementById("habit-delete").classList.add("hidden");
  showModal("habit-modal");
  document.getElementById("habit-name").focus();
}

function openEdit(habit) {
  state.editing = habit;
  document.getElementById("habit-modal-title").textContent = "タスクを編集";
  document.getElementById("habit-name").value = habit.name;
  document.querySelector(`input[name="habit-type"][value="${habit.task_type}"]`).checked = true;
  document.getElementById("habit-delete").classList.remove("hidden");
  showModal("habit-modal");
}

function showModal(id) {
  const el = document.getElementById(id);
  el.classList.remove("hidden");
  el.classList.add("flex");
}
function hideModal(id) {
  const el = document.getElementById(id);
  el.classList.add("hidden");
  el.classList.remove("flex");
}

async function saveHabit() {
  const name = document.getElementById("habit-name").value.trim();
  const type = document.querySelector('input[name="habit-type"]:checked').value;
  if (!name) {
    alert("タスク名を入力してください");
    return;
  }
  if (state.editing) {
    await fetchJson(`/api/habits/${state.editing.id}`, {
      method: "PUT",
      body: JSON.stringify({ name, task_type: type }),
    });
  } else {
    await fetchJson("/api/habits", {
      method: "POST",
      body: JSON.stringify({ name, task_type: type }),
    });
  }
  hideModal("habit-modal");
  await loadAll();
}

async function deleteHabit() {
  if (!state.editing) return;
  if (!confirm(`「${state.editing.name}」を削除しますか？\nチェック記録も全て削除されます。`)) return;
  await fetchJson(`/api/habits/${state.editing.id}`, { method: "DELETE" });
  hideModal("habit-modal");
  await loadAll();
}

// ----- Settings modal -----

async function openSettings() {
  const s = await fetchJson("/api/settings");
  document.getElementById("setting-email").value = s.notification_email || "";
  document.getElementById("setting-enabled").checked = !!s.notification_enabled;
  document.getElementById("setting-status").textContent = "";
  showModal("settings-modal");
}

async function saveSettings() {
  const email = document.getElementById("setting-email").value.trim();
  const enabled = document.getElementById("setting-enabled").checked;
  await fetchJson("/api/settings", {
    method: "PUT",
    body: JSON.stringify({
      notification_email: email,
      notification_enabled: enabled,
    }),
  });
  document.getElementById("setting-status").textContent = "保存しました";
  setTimeout(() => hideModal("settings-modal"), 700);
}

async function testNotification() {
  document.getElementById("setting-status").textContent = "送信中...";
  try {
    const res = await fetchJson("/api/notifications/test", { method: "POST" });
    document.getElementById("setting-status").textContent = res.sent
      ? `送信しました: ${res.to}`
      : `送信されませんでした (${res.reason})`;
  } catch (e) {
    document.getElementById("setting-status").textContent = "エラー: " + e.message;
  }
}

// ----- Wire up -----

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("date-input").addEventListener("change", e => {
    state.date = e.target.value;
    loadAll();
  });
  document.getElementById("prev-day").addEventListener("click", () => {
    state.date = shiftDate(state.date, -1);
    loadAll();
  });
  document.getElementById("next-day").addEventListener("click", () => {
    state.date = shiftDate(state.date, 1);
    loadAll();
  });

  document.querySelectorAll(".add-habit").forEach(btn => {
    btn.addEventListener("click", () => openAdd(btn.dataset.type));
  });

  document.getElementById("habit-cancel").addEventListener("click", () => hideModal("habit-modal"));
  document.getElementById("habit-save").addEventListener("click", saveHabit);
  document.getElementById("habit-delete").addEventListener("click", deleteHabit);

  document.getElementById("open-settings").addEventListener("click", openSettings);
  document.getElementById("setting-cancel").addEventListener("click", () => hideModal("settings-modal"));
  document.getElementById("setting-save").addEventListener("click", saveSettings);
  document.getElementById("setting-test").addEventListener("click", testNotification);

  // Close modals on backdrop click
  for (const id of ["habit-modal", "settings-modal"]) {
    document.getElementById(id).addEventListener("click", e => {
      if (e.target.id === id) hideModal(id);
    });
  }

  loadAll();
});
