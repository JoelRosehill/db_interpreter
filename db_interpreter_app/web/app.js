const THEMES = ["modern-light", "modern-dark", "retro-95"];
const AUTOCOMPLETE_LIMIT = 6;
const IDENTIFIER_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*$/;

const SQL_ALIAS_STOP_WORDS = new Set([
  "AS",
  "AND",
  "BY",
  "FROM",
  "GROUP",
  "HAVING",
  "INNER",
  "INTO",
  "JOIN",
  "LEFT",
  "LIMIT",
  "OFFSET",
  "ON",
  "OR",
  "ORDER",
  "OUTER",
  "RIGHT",
  "SET",
  "UNION",
  "USING",
  "VALUES",
  "WHERE",
]);

const SQL_BASE_SUGGESTIONS = [
  "SELECT",
  "FROM",
  "WHERE",
  "INSERT INTO",
  "UPDATE",
  "DELETE FROM",
  "CREATE TABLE",
  "ALTER TABLE",
  "DROP TABLE",
  "JOIN",
  "LEFT JOIN",
  "RIGHT JOIN",
  "INNER JOIN",
  "ORDER BY",
  "GROUP BY",
  "HAVING",
  "VALUES",
  "SET",
  "DISTINCT",
  "LIMIT",
  "OFFSET",
  "AS",
  "AND",
  "OR",
  "NOT",
  "NULL",
  "LIKE",
  "BETWEEN",
  "IN",
  "EXISTS",
  "CASE",
  "WHEN",
  "THEN",
  "ELSE",
  "END",
  "COMMIT",
  "ROLLBACK",
  "*",
];

const SQL_START_SUGGESTIONS = [
  "SELECT",
  "INSERT INTO",
  "UPDATE",
  "DELETE FROM",
  "CREATE TABLE",
  "ALTER TABLE",
  "DROP TABLE",
];

const SQL_CONTINUATIONS = {
  ALTER: ["TABLE"],
  CREATE: ["TABLE"],
  DELETE: ["FROM"],
  DROP: ["TABLE"],
  GROUP: ["BY"],
  INNER: ["JOIN"],
  INSERT: ["INTO"],
  LEFT: ["JOIN"],
  ORDER: ["BY"],
  OUTER: ["JOIN"],
  RIGHT: ["JOIN"],
};

const NOSQL_SUGGESTIONS = [
  {
    label: "db.",
    value: "db.",
    kind: "command",
    detail: "start a collection command",
    appendSpace: false,
    searchText: "db",
    boost: 80,
  },
  {
    label: "find()",
    value: "find()",
    kind: "command",
    detail: "list documents",
    appendSpace: false,
    searchText: "find",
  },
  {
    label: "insertOne({})",
    value: "insertOne({})",
    kind: "command",
    detail: "insert one document",
    appendSpace: false,
    searchText: "insertOne",
  },
];

const PYMYSQL_SUGGESTIONS = [
  {
    label: "import pymysql",
    value: "import pymysql",
    kind: "snippet",
    detail: "load the mock client",
    appendSpace: true,
    searchText: "import pymysql",
    boost: 60,
  },
  {
    label: "pymysql.connect()",
    value: "pymysql.connect()",
    kind: "snippet",
    detail: "open a connection",
    appendSpace: false,
    searchText: "connect",
  },
  {
    label: "conn.cursor()",
    value: "conn.cursor()",
    kind: "snippet",
    detail: "create a cursor",
    appendSpace: false,
    searchText: "cursor",
  },
  {
    label: 'cursor.execute("")',
    value: 'cursor.execute("")',
    kind: "snippet",
    detail: "run a SQL statement",
    appendSpace: false,
    searchText: "execute",
  },
  {
    label: "conn.commit()",
    value: "conn.commit()",
    kind: "snippet",
    detail: "commit pending changes",
    appendSpace: false,
    searchText: "commit",
  },
];

const state = {
  lastColumns: [],
  lastRows: [],
  history: [],
  autocompleteSchema: {
    tables: [],
    byName: new Map(),
  },
  autocomplete: {
    label: "",
    suggestions: [],
    activeIndex: 0,
    replaceStart: 0,
    replaceEnd: 0,
    visible: false,
  },
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

  autocompletePanel: document.getElementById("autocompletePanel"),
  autocompleteLabel: document.getElementById("autocompleteLabel"),
  autocompleteHint: document.getElementById("autocompleteHint"),
  autocompleteList: document.getElementById("autocompleteList"),

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

function isSimpleIdentifier(identifier) {
  return IDENTIFIER_PATTERN.test(identifier || "");
}

function formatSqlIdentifier(identifier) {
  return isSimpleIdentifier(identifier) ? identifier : `"${String(identifier).replace(/"/g, '""')}"`;
}

function unquoteSqlIdentifier(identifier) {
  if (identifier.startsWith('"') && identifier.endsWith('"')) {
    return identifier.slice(1, -1).replace(/""/g, '"');
  }
  return identifier;
}

function getHistoryBoost(term) {
  if (!term || state.history.length === 0) {
    return 0;
  }

  const haystack = state.history.join("\n").toUpperCase();
  return haystack.includes(String(term).toUpperCase()) ? 16 : 0;
}

function setAutocompleteMetadata(metadata) {
  const tables = Array.isArray(metadata?.tables)
    ? metadata.tables
        .filter((table) => table && typeof table.name === "string")
        .map((table) => ({
          name: table.name,
          columns: Array.isArray(table.columns) ? table.columns : [],
        }))
    : [];

  state.autocompleteSchema = {
    tables,
    byName: new Map(tables.map((table) => [table.name, table])),
  };

  updateAutocomplete();
}

function renderHistory(history) {
  state.history = Array.isArray(history) ? history : [];
  refs.historyList.innerHTML = "";

  if (state.history.length === 0) {
    const item = document.createElement("li");
    item.textContent = "No history yet.";
    item.className = "muted-item";
    refs.historyList.appendChild(item);
    return;
  }

  state.history.forEach((query) => {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = truncateQuery(query);
    button.title = query;
    button.addEventListener("click", () => {
      refs.sqlEditor.value = query;
      updateLineNumbers();
      refs.sqlEditor.focus();
      updateAutocomplete();
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
      updateAutocomplete();
    });
    li.appendChild(button);
    refs.tablesList.appendChild(li);
  });
}

function hideAutocomplete() {
  state.autocomplete.visible = false;
  state.autocomplete.label = "";
  state.autocomplete.suggestions = [];
  state.autocomplete.activeIndex = 0;
  refs.autocompletePanel.classList.add("hidden");
  refs.autocompleteList.innerHTML = "";
}

function renderAutocomplete() {
  if (!state.autocomplete.visible || state.autocomplete.suggestions.length === 0) {
    hideAutocomplete();
    return;
  }

  refs.autocompleteLabel.textContent = state.autocomplete.label || "Suggestions";
  refs.autocompleteHint.textContent = "Tab or tap to insert, arrows to move, Esc to dismiss";
  refs.autocompleteList.innerHTML = "";

  state.autocomplete.suggestions.forEach((suggestion, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "autocomplete-item";
    button.setAttribute("role", "option");
    button.setAttribute("aria-selected", index === state.autocomplete.activeIndex ? "true" : "false");

    if (index === state.autocomplete.activeIndex) {
      button.classList.add("active");
    }

    const title = document.createElement("strong");
    title.textContent = suggestion.label;

    const detail = document.createElement("span");
    detail.className = "autocomplete-detail";
    detail.textContent = suggestion.detail || suggestion.kind;

    button.appendChild(title);
    button.appendChild(detail);

    button.addEventListener("mousedown", (event) => {
      event.preventDefault();
    });

    button.addEventListener("click", () => {
      applyAutocompleteSuggestion(index);
    });

    refs.autocompleteList.appendChild(button);
  });

  refs.autocompletePanel.classList.remove("hidden");
}

function getAutocompleteMatchScore(searchText, prefix) {
  const value = String(searchText || "").toUpperCase();
  const normalizedPrefix = String(prefix || "").trim().toUpperCase();

  if (!normalizedPrefix) {
    return 20;
  }

  if (value === normalizedPrefix) {
    return 220;
  }

  if (value.startsWith(normalizedPrefix)) {
    return 200 - Math.min(value.length - normalizedPrefix.length, 40);
  }

  const wordBoundaryIndex = value.indexOf(` ${normalizedPrefix}`);
  if (wordBoundaryIndex >= 0) {
    return 140 - Math.min(wordBoundaryIndex, 40);
  }

  const containsIndex = value.indexOf(normalizedPrefix);
  if (containsIndex >= 0) {
    return 80 - Math.min(containsIndex, 40);
  }

  return -1;
}

function rankAutocompleteSuggestions(candidates, prefix) {
  const deduped = new Map();

  candidates.forEach((candidate) => {
    const score = getAutocompleteMatchScore(candidate.searchText || candidate.label, prefix);
    if (score < 0) {
      return;
    }

    const rankedCandidate = {
      ...candidate,
      score: score + (candidate.boost || 0),
    };

    const key = `${candidate.kind}:${candidate.label}:${candidate.detail || ""}`;
    const existing = deduped.get(key);
    if (!existing || rankedCandidate.score > existing.score) {
      deduped.set(key, rankedCandidate);
    }
  });

  return [...deduped.values()]
    .sort((left, right) => right.score - left.score || left.label.localeCompare(right.label))
    .slice(0, AUTOCOMPLETE_LIMIT);
}

function isLikelyInsideSqlLiteral(text) {
  const normalized = text.replace(/''/g, "").replace(/""/g, "");
  const singleQuotes = normalized.match(/'/g) || [];
  const doubleQuotes = normalized.match(/"/g) || [];
  return singleQuotes.length % 2 === 1 || doubleQuotes.length % 2 === 1;
}

function getEditorAutocompleteContext() {
  if (refs.sqlEditor.selectionStart !== refs.sqlEditor.selectionEnd) {
    return null;
  }

  const value = refs.sqlEditor.value;
  const cursor = refs.sqlEditor.selectionStart;
  const beforeCursor = value.slice(0, cursor);
  const currentLine = beforeCursor.slice(beforeCursor.lastIndexOf("\n") + 1);
  const statementStart = beforeCursor.lastIndexOf(";") + 1;
  const currentStatement = beforeCursor.slice(statementStart);
  const qualifierMatch = currentStatement.match(/([A-Za-z_][A-Za-z0-9_]*)\.(?:([A-Za-z_][A-Za-z0-9_]*))?$/);

  if (qualifierMatch) {
    const prefix = qualifierMatch[2] || "";
    const replaceStart = cursor - prefix.length;
    return {
      cursor,
      beforeCursor,
      currentLine,
      currentStatement,
      currentPrefix: prefix,
      qualifier: qualifierMatch[1],
      replaceStart,
      replaceEnd: cursor,
      statementBeforePrefix: beforeCursor.slice(statementStart, replaceStart),
    };
  }

  const wordMatch = beforeCursor.match(/([A-Za-z_][A-Za-z0-9_]*)$/);
  const prefix = wordMatch ? wordMatch[1] : "";
  const replaceStart = cursor - prefix.length;

  return {
    cursor,
    beforeCursor,
    currentLine,
    currentStatement,
    currentPrefix: prefix,
    qualifier: "",
    replaceStart,
    replaceEnd: cursor,
    statementBeforePrefix: beforeCursor.slice(statementStart, replaceStart),
  };
}

function extractSqlReferences(statement) {
  const aliases = new Map();
  const tableNames = [];
  const seenTables = new Set();
  const pattern = /\b(?:FROM|JOIN|UPDATE|INTO)\s+("(?:[^"]|"")*"|[A-Za-z_][A-Za-z0-9_]*)(?:\s+(?:AS\s+)?([A-Za-z_][A-Za-z0-9_]*))?/gi;

  let match = pattern.exec(statement);
  while (match) {
    const tableName = unquoteSqlIdentifier(match[1]);
    if (!seenTables.has(tableName)) {
      seenTables.add(tableName);
      tableNames.push(tableName);
    }

    const alias = match[2];
    if (alias && !SQL_ALIAS_STOP_WORDS.has(alias.toUpperCase())) {
      aliases.set(alias, tableName);
    }

    match = pattern.exec(statement);
  }

  return {
    aliases,
    tables: tableNames,
  };
}

function buildKeywordSuggestion(label, boost = 0) {
  return {
    label,
    value: label,
    kind: "keyword",
    detail: "SQL keyword",
    appendSpace: label !== "*",
    searchText: label,
    boost,
  };
}

function buildTableSuggestions() {
  return state.autocompleteSchema.tables.map((table) => ({
    label: table.name,
    value: formatSqlIdentifier(table.name),
    kind: "table",
    detail: table.columns.length === 1 ? "1 column" : `${table.columns.length} columns`,
    appendSpace: true,
    searchText: table.name,
    boost: 30 + getHistoryBoost(table.name),
  }));
}

function buildColumnSuggestions(tableNames, qualified = false) {
  const uniqueTableNames = tableNames.length > 0
    ? [...new Set(tableNames)]
    : state.autocompleteSchema.tables.map((table) => table.name);

  if (qualified && uniqueTableNames.length === 1) {
    const table = state.autocompleteSchema.byName.get(uniqueTableNames[0]);
    if (!table) {
      return [];
    }

    return table.columns.map((column) => ({
      label: column,
      value: formatSqlIdentifier(column),
      kind: "column",
      detail: table.name,
      appendSpace: false,
      searchText: column,
      boost: 50 + getHistoryBoost(column) + getHistoryBoost(`${table.name}.${column}`),
    }));
  }

  const deduped = new Map();

  uniqueTableNames.forEach((tableName) => {
    const table = state.autocompleteSchema.byName.get(tableName);
    if (!table) {
      return;
    }

    table.columns.forEach((column) => {
      const key = column.toUpperCase();
      const existing = deduped.get(key);

      if (existing) {
        existing.sources.add(table.name);
        return;
      }

      deduped.set(key, {
        label: column,
        value: formatSqlIdentifier(column),
        kind: "column",
        appendSpace: true,
        searchText: column,
        boost: 40 + getHistoryBoost(column) + getHistoryBoost(`${table.name}.${column}`),
        sources: new Set([table.name]),
      });
    });
  });

  return [...deduped.values()].map((candidate) => ({
    label: candidate.label,
    value: candidate.value,
    kind: candidate.kind,
    detail: candidate.sources.size === 1 ? [...candidate.sources][0] : `${candidate.sources.size} tables`,
    appendSpace: candidate.appendSpace,
    searchText: candidate.searchText,
    boost: candidate.boost,
  }));
}

function isSqlTableContext(lastToken, previousToken) {
  if (["FROM", "JOIN", "UPDATE", "INTO"].includes(lastToken)) {
    return true;
  }

  if (lastToken === "TABLE" && ["ALTER", "DROP"].includes(previousToken)) {
    return true;
  }

  return false;
}

function isSqlColumnContext(lastToken, previousToken, context) {
  const trimmed = context.statementBeforePrefix.trimEnd();

  if (["SELECT", "WHERE", "AND", "OR", "ON", "SET", "HAVING"].includes(lastToken)) {
    return true;
  }

  if (lastToken === "BY" && ["ORDER", "GROUP"].includes(previousToken)) {
    return true;
  }

  if (trimmed.endsWith(",") && /\bSELECT\b/i.test(context.currentStatement)) {
    return true;
  }

  if (trimmed.endsWith("(") && /\bINSERT\s+INTO\b/i.test(context.currentStatement)) {
    return true;
  }

  return false;
}

function shouldOfferSqlSuggestions(context, lastToken, previousToken, force) {
  if (force || context.qualifier || context.currentPrefix) {
    return true;
  }

  const trimmed = context.statementBeforePrefix.trimEnd();
  if (!trimmed) {
    return true;
  }

  if (trimmed.endsWith(",") || trimmed.endsWith("(")) {
    return true;
  }

  if (isSqlTableContext(lastToken, previousToken) || isSqlColumnContext(lastToken, previousToken, context)) {
    return true;
  }

  return Boolean(SQL_CONTINUATIONS[lastToken]);
}

function buildSqlSuggestions(context, force) {
  const prefix = context.currentPrefix;
  const rawTail = context.statementBeforePrefix.trimEnd();
  const tokens = rawTail.toUpperCase().match(/[A-Z_]+/g) || [];
  const lastToken = tokens.at(-1) || "";
  const previousToken = tokens.at(-2) || "";
  const references = extractSqlReferences(context.currentStatement);

  if (!shouldOfferSqlSuggestions(context, lastToken, previousToken, force)) {
    return { label: "SQL suggestions", suggestions: [] };
  }

  if (context.qualifier) {
    const tableName = references.aliases.get(context.qualifier)
      || (state.autocompleteSchema.byName.has(context.qualifier) ? context.qualifier : "");

    if (!tableName) {
      return { label: "SQL suggestions", suggestions: [] };
    }

    return {
      label: `Columns from ${tableName}`,
      suggestions: rankAutocompleteSuggestions(buildColumnSuggestions([tableName], true), prefix),
    };
  }

  const candidates = [];
  let label = "SQL suggestions";

  (SQL_CONTINUATIONS[lastToken] || []).forEach((keyword) => {
    candidates.push(buildKeywordSuggestion(keyword, 220));
  });

  if (!rawTail) {
    label = "SQL starters";
    SQL_START_SUGGESTIONS.forEach((keyword) => {
      candidates.push(buildKeywordSuggestion(keyword, 180));
    });
  }

  if (isSqlTableContext(lastToken, previousToken)) {
    label = "Tables";
    candidates.push(
      ...buildTableSuggestions().map((candidate) => ({
        ...candidate,
        boost: candidate.boost + 120,
      }))
    );
  }

  if (isSqlColumnContext(lastToken, previousToken, context)) {
    const tableNames = references.tables.length > 0
      ? references.tables
      : state.autocompleteSchema.tables.map((table) => table.name);

    label = "Columns";
    candidates.push(...buildColumnSuggestions(tableNames));

    if (lastToken === "SELECT") {
      candidates.push(buildKeywordSuggestion("DISTINCT", 110));
      candidates.push(buildKeywordSuggestion("*", 105));
    }

    if (["WHERE", "AND", "OR", "ON"].includes(lastToken)) {
      candidates.push(buildKeywordSuggestion("IN", 90));
      candidates.push(buildKeywordSuggestion("EXISTS", 88));
      candidates.push(buildKeywordSuggestion("NOT", 86));
    }
  }

  if (!candidates.length || force || prefix) {
    candidates.push(...SQL_BASE_SUGGESTIONS.map((keyword) => buildKeywordSuggestion(keyword, rawTail ? 0 : 50)));

    if (references.tables.length === 0 || isSqlTableContext(lastToken, previousToken)) {
      candidates.push(...buildTableSuggestions());
    }
  }

  return {
    label,
    suggestions: rankAutocompleteSuggestions(candidates, prefix),
  };
}

function buildNosqlSuggestions(context, force) {
  const prefix = context.currentPrefix;
  const trimmedLine = context.currentLine.trim();
  let candidates = [];
  let label = "NoSQL suggestions";

  if (context.qualifier === "db") {
    label = "Collections";
    candidates = state.autocompleteSchema.tables
      .filter((table) => isSimpleIdentifier(table.name))
      .map((table) => ({
        label: table.name,
        value: table.name,
        kind: "table",
        detail: table.columns.length === 1 ? "1 field" : `${table.columns.length} fields`,
        appendSpace: false,
        searchText: table.name,
        boost: 60 + getHistoryBoost(table.name),
      }));
  } else if (context.qualifier && isSimpleIdentifier(context.qualifier)) {
    label = `${context.qualifier} actions`;
    candidates = [
      {
        label: "find()",
        value: "find()",
        kind: "command",
        detail: "list documents",
        appendSpace: false,
        searchText: "find",
        boost: 140,
      },
      {
        label: "insertOne({})",
        value: "insertOne({})",
        kind: "command",
        detail: "insert one document",
        appendSpace: false,
        searchText: "insertOne",
        boost: 135,
      },
    ];
  } else {
    label = "NoSQL starters";
    candidates = [...NOSQL_SUGGESTIONS];

    if (!trimmedLine || trimmedLine.startsWith("db")) {
      candidates.push(
        ...state.autocompleteSchema.tables
          .filter((table) => isSimpleIdentifier(table.name))
          .map((table) => ({
            label: `db.${table.name}`,
            value: `db.${table.name}`,
            kind: "snippet",
            detail: "collection reference",
            appendSpace: false,
            searchText: table.name,
            boost: 24 + getHistoryBoost(table.name),
          }))
      );
    }
  }

  if (!force && !prefix && !context.qualifier && trimmedLine) {
    return { label, suggestions: [] };
  }

  return {
    label,
    suggestions: rankAutocompleteSuggestions(candidates, prefix),
  };
}

function buildPymysqlSuggestions(context, force) {
  const prefix = context.currentPrefix;
  let label = "PyMySQL snippets";
  let candidates = [...PYMYSQL_SUGGESTIONS];

  if (context.qualifier === "pymysql") {
    label = "pymysql helpers";
    candidates = [
      {
        label: "connect()",
        value: "connect()",
        kind: "snippet",
        detail: "open a connection",
        appendSpace: false,
        searchText: "connect",
        boost: 140,
      },
    ];
  } else if (context.qualifier === "conn") {
    label = "Connection helpers";
    candidates = [
      {
        label: "cursor()",
        value: "cursor()",
        kind: "snippet",
        detail: "create a cursor",
        appendSpace: false,
        searchText: "cursor",
        boost: 140,
      },
      {
        label: "commit()",
        value: "commit()",
        kind: "snippet",
        detail: "commit pending changes",
        appendSpace: false,
        searchText: "commit",
        boost: 135,
      },
    ];
  } else if (context.qualifier === "cursor") {
    label = "Cursor helpers";
    candidates = [
      {
        label: 'execute("")',
        value: 'execute("")',
        kind: "snippet",
        detail: "run a SQL statement",
        appendSpace: false,
        searchText: "execute",
        boost: 140,
      },
    ];
  }

  if (!force && !prefix && !context.qualifier) {
    return { label, suggestions: [] };
  }

  return {
    label,
    suggestions: rankAutocompleteSuggestions(candidates, prefix),
  };
}

function updateAutocomplete(force = false) {
  const context = getEditorAutocompleteContext();
  if (!context) {
    hideAutocomplete();
    return;
  }

  if (refs.modeSelect.value === "SQL" && isLikelyInsideSqlLiteral(context.currentStatement)) {
    hideAutocomplete();
    return;
  }

  let payload;
  if (refs.modeSelect.value === "NoSQL") {
    payload = buildNosqlSuggestions(context, force);
  } else if (refs.modeSelect.value === "PyMySQL") {
    payload = buildPymysqlSuggestions(context, force);
  } else {
    payload = buildSqlSuggestions(context, force);
  }

  if (!payload.suggestions || payload.suggestions.length === 0) {
    hideAutocomplete();
    return;
  }

  state.autocomplete = {
    label: payload.label || "Suggestions",
    suggestions: payload.suggestions,
    activeIndex: 0,
    replaceStart: context.replaceStart,
    replaceEnd: context.replaceEnd,
    visible: true,
  };

  renderAutocomplete();
}

function moveAutocompleteSelection(step) {
  if (!state.autocomplete.visible || state.autocomplete.suggestions.length === 0) {
    return;
  }

  const total = state.autocomplete.suggestions.length;
  state.autocomplete.activeIndex = (state.autocomplete.activeIndex + step + total) % total;
  renderAutocomplete();
}

function buildAutocompleteInsertText(suggestion, nextChar) {
  if (!suggestion.appendSpace) {
    return suggestion.value;
  }

  if (!nextChar || !/[\s,.;()]/.test(nextChar)) {
    return `${suggestion.value} `;
  }

  return suggestion.value;
}

function applyAutocompleteSuggestion(index = state.autocomplete.activeIndex) {
  const suggestion = state.autocomplete.suggestions[index];
  if (!suggestion) {
    return;
  }

  const currentValue = refs.sqlEditor.value;
  const nextChar = currentValue.slice(state.autocomplete.replaceEnd, state.autocomplete.replaceEnd + 1);
  const insertText = buildAutocompleteInsertText(suggestion, nextChar);

  refs.sqlEditor.value = `${currentValue.slice(0, state.autocomplete.replaceStart)}${insertText}${currentValue.slice(state.autocomplete.replaceEnd)}`;

  const nextCursor = state.autocomplete.replaceStart + insertText.length;
  refs.sqlEditor.selectionStart = nextCursor;
  refs.sqlEditor.selectionEnd = nextCursor;

  updateLineNumbers();
  syncLineScroll();
  refs.sqlEditor.focus();
  updateAutocomplete();
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
  setAutocompleteMetadata(payload.autocomplete);
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
    setAutocompleteMetadata(payload.autocomplete);
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
    renderHistory(payload.history || []);
    renderTables(payload.tables || []);
    setAutocompleteMetadata(payload.autocomplete);
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
    renderHistory(payload.history || []);
    renderTables(payload.tables || []);
    setAutocompleteMetadata(payload.autocomplete);
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
    setAutocompleteMetadata(payload.autocomplete);
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
  refs.sqlEditor.addEventListener("input", () => {
    updateLineNumbers();
    updateAutocomplete();
  });
  refs.sqlEditor.addEventListener("scroll", syncLineScroll);
  refs.sqlEditor.addEventListener("click", () => updateAutocomplete());
  refs.sqlEditor.addEventListener("focus", () => updateAutocomplete());
  refs.sqlEditor.addEventListener("keyup", (event) => {
    if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End", "PageUp", "PageDown"].includes(event.key)) {
      updateAutocomplete();
    }
  });

  refs.sqlEditor.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      handleExecute();
      return;
    }

    if ((event.ctrlKey || event.metaKey) && event.code === "Space") {
      event.preventDefault();
      updateAutocomplete(true);
      return;
    }

    if (state.autocomplete.visible) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        moveAutocompleteSelection(1);
        return;
      }

      if (event.key === "ArrowUp") {
        event.preventDefault();
        moveAutocompleteSelection(-1);
        return;
      }

      if (event.key === "Escape") {
        event.preventDefault();
        hideAutocomplete();
        return;
      }

      if (event.key === "Tab") {
        event.preventDefault();
        if (event.shiftKey) {
          moveAutocompleteSelection(-1);
        } else {
          applyAutocompleteSuggestion();
        }
        return;
      }
    }

    if (event.key === "Tab") {
      event.preventDefault();
      const start = refs.sqlEditor.selectionStart;
      const end = refs.sqlEditor.selectionEnd;
      const current = refs.sqlEditor.value;
      refs.sqlEditor.value = `${current.slice(0, start)}  ${current.slice(end)}`;
      refs.sqlEditor.selectionStart = refs.sqlEditor.selectionEnd = start + 2;
      updateLineNumbers();
      updateAutocomplete();
      return;
    }

    if (event.key === "Escape") {
      hideAutocomplete();
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
    updateAutocomplete();
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
  refs.modeSelect.addEventListener("change", () => updateAutocomplete());

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

  document.addEventListener("mousedown", (event) => {
    if (refs.sqlEditor.contains(event.target) || refs.autocompletePanel.contains(event.target)) {
      return;
    }
    hideAutocomplete();
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
