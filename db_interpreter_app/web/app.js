const THEMES = ["modern-light", "modern-dark", "retro-95"];

const state = {
  lastColumns: [],
  lastRows: [],
};

const refs = {
  themeSelect: document.getElementById("themeSelect"),
  activeDbLabel: document.getElementById("activeDbLabel"),
  timeLabel: document.getElementById("timeLabel"),
  rowCountLabel: document.getElementById("rowCountLabel"),

  historyList: document.getElementById("historyList"),
  tablesList: document.getElementById("tablesList"),

  modeSelect: document.getElementById("modeSelect"),
  dbSelect: document.getElementById("dbSelect"),
  autocommitToggle: document.getElementById("autocommitToggle"),
  sqlEditor: document.getElementById("sqlEditor"),
  lineNumbers: document.getElementById("lineNumbers"),
  statusBar: document.getElementById("statusBar"),

  executeBtn: document.getElementById("executeBtn"),
  explainBtn: document.getElementById("explainBtn"),
  schemaBtn: document.getElementById("schemaBtn"),
  clearBtn: document.getElementById("clearBtn"),

  generateBtn: document.getElementById("generateBtn"),
  commitBtn: document.getElementById("commitBtn"),
  rollbackBtn: document.getElementById("rollbackBtn"),
  loadBtn: document.getElementById("loadBtn"),
  exportBtn: document.getElementById("exportBtn"),
  nukeBtn: document.getElementById("nukeBtn"),
  newDbBtn: document.getElementById("newDbBtn"),

  outputText: document.getElementById("outputText"),
  tableContainer: document.getElementById("tableContainer"),

  sqlFileInput: document.getElementById("sqlFileInput"),
};

function setStatus(message, type = "info") {
  refs.statusBar.textContent = message;
  refs.statusBar.classList.remove("ok", "error");
  if (type === "ok") {
    refs.statusBar.classList.add("ok");
  }
  if (type === "error") {
    refs.statusBar.classList.add("error");
  }
}

function updateTime(value) {
  refs.timeLabel.textContent = value === null || value === undefined ? "-- ms" : `${value} ms`;
}

function updateRowCount(value) {
  refs.rowCountLabel.textContent = value === null || value === undefined ? "--" : String(value);
}

function truncateQuery(query) {
  return query.length > 72 ? `${query.slice(0, 69)}...` : query;
}

function renderHistory(history) {
  refs.historyList.innerHTML = "";

  if (!history || history.length === 0) {
    const item = document.createElement("li");
    item.textContent = "No history yet.";
    item.className = "muted-item";
    refs.historyList.appendChild(item);
    return;
  }

  history.forEach((query) => {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = truncateQuery(query);
    button.title = query;
    button.addEventListener("click", () => {
      refs.sqlEditor.value = query;
      updateLineNumbers();
      refs.sqlEditor.focus();
    });
    li.appendChild(button);
    refs.historyList.appendChild(li);
  });
}

function renderTables(tables) {
  refs.tablesList.innerHTML = "";

  if (!tables || tables.length === 0) {
    const item = document.createElement("li");
    item.textContent = "No tables found.";
    item.className = "muted-item";
    refs.tablesList.appendChild(item);
    return;
  }

  tables.forEach((tableName) => {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = tableName;
    button.addEventListener("click", () => {
      const escaped = tableName.replace(/"/g, '""');
      refs.sqlEditor.value = `SELECT * FROM "${escaped}";`;
      updateLineNumbers();
      refs.sqlEditor.focus();
    });
    li.appendChild(button);
    refs.tablesList.appendChild(li);
  });
}

function renderDatabases(databases, currentDb) {
  refs.dbSelect.innerHTML = "";

  (databases || []).forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    refs.dbSelect.appendChild(option);
  });

  if (currentDb) {
    refs.dbSelect.value = currentDb;
    refs.activeDbLabel.textContent = currentDb;
  }
}

function clearTable() {
  refs.tableContainer.innerHTML = "";
  refs.tableContainer.classList.add("hidden");
}

function renderResultTable(columns, rows) {
  clearTable();
  if (!columns || columns.length === 0) {
    return;
  }

  const table = document.createElement("table");
  table.className = "result-table";

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  columns.forEach((column) => {
    const th = document.createElement("th");
    th.textContent = column;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  (rows || []).forEach((row) => {
    const tr = document.createElement("tr");
    row.forEach((value) => {
      const td = document.createElement("td");
      td.textContent = value === null ? "NULL" : String(value);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);

  refs.tableContainer.appendChild(table);
  refs.tableContainer.classList.remove("hidden");
}

function renderOutputText(text) {
  refs.outputText.textContent = text && text.trim() ? text : "(No output)";
}

function updateLineNumbers() {
  const lineCount = refs.sqlEditor.value.split("\n").length;
  refs.lineNumbers.textContent = Array.from({ length: lineCount }, (_, i) => String(i + 1)).join("\n");
}

function syncLineScroll() {
  refs.lineNumbers.scrollTop = refs.sqlEditor.scrollTop;
}

function updateAutocommitState() {
  const manualMode = !refs.autocommitToggle.checked;
  refs.commitBtn.disabled = !manualMode;
  refs.rollbackBtn.disabled = !manualMode;
}

function asCsvCell(value) {
  if (value === null || value === undefined) {
    return "";
  }
  const str = String(value);
  if (/[",\n]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function downloadCsv(columns, rows) {
  if ((!columns || columns.length === 0) && (!rows || rows.length === 0)) {
    throw new Error("No table results available to export.");
  }

  const lines = [];
  if (columns && columns.length > 0) {
    lines.push(columns.map(asCsvCell).join(","));
  }

  (rows || []).forEach((row) => {
    lines.push(row.map(asCsvCell).join(","));
  });

  const blob = new Blob([`${lines.join("\n")}\n`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "query-results.csv";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

async function request(path, options = {}) {
  const config = {
    method: options.method || "GET",
  };

  if (options.body !== undefined) {
    config.headers = { "Content-Type": "application/json" };
    config.body = JSON.stringify(options.body);
  }

  const response = await fetch(path, config);
  const payload = await response.json().catch(() => ({}));

  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || `Request failed with status ${response.status}`);
  }

  return payload;
}

async function refreshBootstrap() {
  const payload = await request("/api/bootstrap");
  renderDatabases(payload.databases, payload.currentDb);
  renderHistory(payload.history || []);
  renderTables(payload.tables || []);
}

async function handleExecute() {
  const code = refs.sqlEditor.value.trim();
  if (!code) {
    setStatus("Please enter commands first.", "error");
    return;
  }

  setStatus("Running...");

  try {
    const payload = await request("/api/execute", {
      method: "POST",
      body: {
        mode: refs.modeSelect.value,
        code,
        autocommit: refs.autocommitToggle.checked,
      },
    });

    state.lastColumns = payload.columns || [];
    state.lastRows = payload.rows || [];

    renderResultTable(state.lastColumns, state.lastRows);
    renderOutputText(payload.output || payload.status || "Done.");
    renderHistory(payload.history || []);
    renderTables(payload.tables || []);
    updateTime(payload.executionMs);
    updateRowCount(payload.rowCount);
    setStatus(payload.status || "Execution finished.", "ok");
  } catch (error) {
    clearTable();
    renderOutputText(`ERROR: ${error.message}`);
    setStatus(error.message, "error");
  }
}

async function handleExplain() {
  const query = refs.sqlEditor.value.trim();
  if (!query) {
    setStatus("Please enter a query first.", "error");
    return;
  }

  try {
    const payload = await request("/api/explain", {
      method: "POST",
      body: { query },
    });
    clearTable();
    renderOutputText(payload.explanation || "");
    setStatus("Explanation ready.", "ok");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

async function handleSchema() {
  try {
    const payload = await request("/api/schema");
    clearTable();
    renderOutputText(payload.schema || "");
    setStatus("Schema loaded.", "ok");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

async function handleGenerateSql() {
  try {
    const payload = await request("/api/generate-sql");
    clearTable();
    renderOutputText(payload.sql || "");
    setStatus("SQL code generated.", "ok");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

async function handleCommit() {
  try {
    const payload = await request("/api/commit", { method: "POST", body: {} });
    setStatus(payload.status || "Committed.", "ok");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

async function handleRollback() {
  try {
    const payload = await request("/api/rollback", { method: "POST", body: {} });
    setStatus(payload.status || "Rolled back.", "ok");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

async function handleSwitchDb() {
  try {
    const payload = await request("/api/switch-db", {
      method: "POST",
      body: { name: refs.dbSelect.value },
    });

    renderDatabases(payload.databases, payload.currentDb);
    renderTables(payload.tables || []);
    state.lastColumns = [];
    state.lastRows = [];
    clearTable();
    renderOutputText(payload.status || "Database switched.");
    setStatus(payload.status || "Database switched.", "ok");
    updateRowCount(null);
  } catch (error) {
    setStatus(error.message, "error");
    refreshBootstrap().catch(() => null);
  }
}

async function handleCreateDb() {
  const name = window.prompt("Enter a new database name:", "mydb.db");
  if (!name) {
    return;
  }

  try {
    const payload = await request("/api/create-db", {
      method: "POST",
      body: { name },
    });
    renderDatabases(payload.databases, payload.currentDb);
    renderTables(payload.tables || []);
    state.lastColumns = [];
    state.lastRows = [];
    clearTable();
    renderOutputText(payload.status || "Database created.");
    setStatus(payload.status || "Database created.", "ok");
    updateRowCount(null);
  } catch (error) {
    setStatus(error.message, "error");
  }
}

async function handleNuke() {
  const ok = window.confirm("This will permanently delete all tables and data in the active database. Continue?");
  if (!ok) {
    return;
  }

  try {
    const payload = await request("/api/nuke", { method: "POST", body: {} });
    renderTables(payload.tables || []);
    state.lastColumns = [];
    state.lastRows = [];
    clearTable();
    renderOutputText(payload.status || "Database reset complete.");
    setStatus(payload.status || "Database reset complete.", "ok");
    updateRowCount(0);
  } catch (error) {
    setStatus(error.message, "error");
  }
}

function handleClearOutput() {
  clearTable();
  renderOutputText("(Output cleared)");
  setStatus("Output cleared.", "ok");
  updateRowCount(null);
}

function applyTheme(theme) {
  const resolvedTheme = THEMES.includes(theme) ? theme : THEMES[0];
  document.documentElement.dataset.theme = resolvedTheme;
  refs.themeSelect.value = resolvedTheme;
  localStorage.setItem("dbi-theme", resolvedTheme);
}

function setupEditor() {
  refs.sqlEditor.addEventListener("input", updateLineNumbers);
  refs.sqlEditor.addEventListener("scroll", syncLineScroll);

  refs.sqlEditor.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      handleExecute();
      return;
    }

    if (event.key === "Tab") {
      event.preventDefault();
      const start = refs.sqlEditor.selectionStart;
      const end = refs.sqlEditor.selectionEnd;
      const current = refs.sqlEditor.value;
      refs.sqlEditor.value = `${current.slice(0, start)}  ${current.slice(end)}`;
      refs.sqlEditor.selectionStart = refs.sqlEditor.selectionEnd = start + 2;
      updateLineNumbers();
    }
  });
}

function setupFileLoading() {
  refs.loadBtn.addEventListener("click", () => refs.sqlFileInput.click());

  refs.sqlFileInput.addEventListener("change", async (event) => {
    const [file] = event.target.files || [];
    if (!file) {
      return;
    }

    const content = await file.text();
    refs.sqlEditor.value = content;
    updateLineNumbers();
    setStatus(`Loaded file: ${file.name}`, "ok");
    refs.sqlFileInput.value = "";
  });
}

function setupEvents() {
  refs.executeBtn.addEventListener("click", handleExecute);
  refs.explainBtn.addEventListener("click", handleExplain);
  refs.schemaBtn.addEventListener("click", handleSchema);
  refs.clearBtn.addEventListener("click", handleClearOutput);

  refs.generateBtn.addEventListener("click", handleGenerateSql);
  refs.commitBtn.addEventListener("click", handleCommit);
  refs.rollbackBtn.addEventListener("click", handleRollback);
  refs.nukeBtn.addEventListener("click", handleNuke);
  refs.newDbBtn.addEventListener("click", handleCreateDb);

  refs.dbSelect.addEventListener("change", handleSwitchDb);

  refs.autocommitToggle.addEventListener("change", () => {
    updateAutocommitState();
    const status = refs.autocommitToggle.checked ? "Autocommit enabled." : "Autocommit disabled.";
    setStatus(status);
  });

  refs.exportBtn.addEventListener("click", () => {
    try {
      downloadCsv(state.lastColumns, state.lastRows);
      setStatus("CSV exported.", "ok");
    } catch (error) {
      setStatus(error.message, "error");
    }
  });

  refs.themeSelect.addEventListener("change", () => {
    applyTheme(refs.themeSelect.value);
  });
}

async function bootstrap() {
  setupEditor();
  setupFileLoading();
  setupEvents();

  updateLineNumbers();
  updateAutocommitState();

  const savedTheme = localStorage.getItem("dbi-theme");
  applyTheme(savedTheme || "modern-light");

  refs.sqlEditor.value = "SELECT name FROM sqlite_master WHERE type='table';";
  updateLineNumbers();

  try {
    await refreshBootstrap();
    clearTable();
    renderOutputText("Ready. Write a query and run it.");
    setStatus("Connected.", "ok");
  } catch (error) {
    renderOutputText(`ERROR: ${error.message}`);
    setStatus(`Failed to initialize: ${error.message}`, "error");
  }
}

bootstrap();
