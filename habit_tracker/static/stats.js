const params = new URLSearchParams(window.location.search);
const state = {
  mode: params.get("habit") ? "habit" : "overall",
  habitId: params.get("habit") ? Number(params.get("habit")) : null,
  habits: [],
};

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function fmtJa(s) {
  if (!s) return "—";
  const d = new Date(s + "T00:00:00");
  const days = ["日", "月", "火", "水", "木", "金", "土"];
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日（${days[d.getDay()]}）`;
}

function pctBadge(v) {
  if (v == null) return "";
  const arrow = v >= 0 ? "↑" : "↓";
  const color = v >= 0 ? "text-emerald-600" : "text-red-600";
  return `<span class="text-xs font-bold ${color}">${arrow}${Math.abs(v)}%</span>`;
}

function statCard(label, value, sublabel = "", extra = "") {
  return `
    <div class="bg-gray-100 rounded-lg p-4">
      <div class="text-xs text-gray-600 mb-2">${label}</div>
      <div class="text-3xl font-black tracking-tight">${value}</div>
      ${extra ? `<div class="text-right mt-1">${extra}</div>` : ""}
      ${sublabel ? `<div class="text-xs text-gray-500 mt-1">${sublabel}</div>` : ""}
    </div>`;
}

async function loadHabits() {
  state.habits = await fetchJson("/api/habits");
  const sel = document.getElementById("habit-select");
  sel.innerHTML = '<option value="">— タスクを選択 —</option>';
  for (const h of state.habits) {
    const opt = document.createElement("option");
    opt.value = h.id;
    opt.textContent = `${h.task_type === "morning" ? "☀" : "☾"} ${h.name}`;
    if (state.habitId === h.id) opt.selected = true;
    sel.appendChild(opt);
  }
  sel.addEventListener("change", e => {
    if (e.target.value) {
      state.mode = "habit";
      state.habitId = Number(e.target.value);
      const url = new URL(window.location);
      url.searchParams.set("habit", state.habitId);
      window.history.replaceState({}, "", url);
      render();
    }
  });

  document.querySelector(".tab-btn[data-tab=overall]").addEventListener("click", () => {
    state.mode = "overall";
    state.habitId = null;
    sel.value = "";
    const url = new URL(window.location);
    url.searchParams.delete("habit");
    window.history.replaceState({}, "", url);
    render();
  });
}

async function render() {
  const grid = document.getElementById("stat-grid");
  const monthlyEl = document.getElementById("monthly-section");
  const perHabitEl = document.getElementById("per-habit-section");

  // Tab visual
  const tab = document.querySelector(".tab-btn[data-tab=overall]");
  if (state.mode === "overall") {
    tab.classList.add("bg-gray-900", "text-white");
    tab.classList.remove("bg-gray-100");
  } else {
    tab.classList.remove("bg-gray-900", "text-white");
    tab.classList.add("bg-gray-100");
  }

  if (state.mode === "habit" && state.habitId) {
    const s = await fetchJson(`/api/stats/habit/${state.habitId}`);
    document.getElementById("period-total").textContent = s.period_total;
    grid.innerHTML = [
      statCard("累計", s.cumulative),
      statCard("今年", s.this_year),
      statCard("今月", s.this_month, "", pctBadge(s.this_month_change)),
      statCard("先月", s.last_month),
      statCard("今週", s.this_week, "", pctBadge(s.this_week_change)),
      statCard("先週", s.last_week),
      statCard("最終チェック日", `<span class="text-base font-bold">${fmtJa(s.last_check_date)}</span>`),
      statCard(
        "最長連続チェック数",
        s.longest_streak,
        s.longest_streak_start
          ? `${fmtJa(s.longest_streak_start)} - ${fmtJa(s.longest_streak_end)}`
          : "",
      ),
      statCard("作成日", `<span class="text-base font-bold">${fmtJa(s.created_at)}</span>`),
      statCard("経過日数", `${s.days_elapsed}<span class="text-base font-normal text-gray-500"> 日</span>`),
    ].join("");
    monthlyEl.style.display = "none";
    perHabitEl.style.display = "none";
  } else {
    const s = await fetchJson(`/api/stats/overall`);
    document.getElementById("period-total").textContent = s.period_total;
    grid.innerHTML = [
      statCard("累計", s.cumulative),
      statCard("今年", s.this_year),
      statCard("今月", s.this_month, "", pctBadge(s.this_month_change)),
      statCard("先月", s.last_month),
      statCard("今週", s.this_week, "", pctBadge(s.this_week_change)),
      statCard("先週", s.last_week),
      statCard("最終チェック日", `<span class="text-base font-bold">${fmtJa(s.last_check_date)}</span>`),
      statCard("経過日数", `${s.days_elapsed}<span class="text-base font-normal text-gray-500"> 日</span>`),
    ].join("");

    // Monthly breakdown
    monthlyEl.style.display = "block";
    const maxCount = Math.max(1, ...s.monthly_breakdown.map(m => m.count));
    document.getElementById("monthly-chart").innerHTML = s.monthly_breakdown
      .map(m => {
        const pct = Math.round((m.count / maxCount) * 100);
        return `
          <div class="flex items-center gap-2">
            <div class="w-14 text-xs text-gray-600 shrink-0">${m.year}/${String(m.month).padStart(2, "0")}</div>
            <div class="flex-1 h-5 bg-gray-100 rounded relative overflow-hidden">
              <div class="absolute inset-y-0 left-0 bg-blue-500" style="width:${pct}%"></div>
            </div>
            <div class="w-12 text-right text-sm font-semibold tabular-nums">${m.count}</div>
          </div>`;
      })
      .join("");

    // Per-habit
    perHabitEl.style.display = s.per_habit.length ? "block" : "none";
    document.getElementById("per-habit-list").innerHTML = s.per_habit
      .map(
        p => `
          <a href="/stats?habit=${p.id}" class="flex items-center justify-between p-3 hover:bg-gray-50">
            <div class="flex items-center gap-2 min-w-0">
              <span class="${p.task_type === "morning" ? "text-yellow-500" : "text-indigo-500"}">${p.task_type === "morning" ? "☀" : "☾"}</span>
              <span class="truncate">${escapeHtml(p.name)}</span>
            </div>
            <div class="flex gap-3 text-sm shrink-0 ml-2">
              <span class="text-gray-500">今週 <strong class="text-gray-900">${p.this_week}</strong></span>
              <span class="text-gray-500">今月 <strong class="text-gray-900">${p.this_month}</strong></span>
              <span class="text-gray-500">累計 <strong class="text-gray-900">${p.cumulative}</strong></span>
            </div>
          </a>`,
      )
      .join("");
  }
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

document.addEventListener("DOMContentLoaded", async () => {
  await loadHabits();
  await render();
});
