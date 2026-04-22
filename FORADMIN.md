# Developer Quick Reference

This file is a quick navigation guide to the codebase. See the main README.md for usage instructions.

## Project Structure

```
db_interpreter/
├── python-db-interpreter.py          # Entry point - run this to start the app
├── databases/                   # SQLite database files (*.db)
├── db_interpreter_app/
│   ├── app.py                # Wrapper - imports and runs web_server
│   ├── web_server.py          # HTTP server + all API endpoints
│   ├── core/
│   │   ├── constants.py      # Mode names (SQL/NoSQL/PyMySQL) + config
│   │   ├── database_service.py  # Main backend logic - all DB operations
│   │   ├── explainer.py    # SQL to English translation
│   │   └── sql_utils.py    # SQL parsing helpers
│   └── web/
│       ├── index.html      # Frontend HTML layout
│       ├── styles.css     # All themes (light/dark/retro)
│       └── app.js        # Frontend logic + autocomplete
```

## File Summary

### Entry Point
- **`python-db-interpreter.py`** - Run `python python-db-interpreter.py` to start. Imports `run_app()` from `db_interpreter_app`.

### Core Backend (`db_interpreter_app/`)

| File | Purpose |
|------|--------|
| `app.py` | Simple wrapper - calls `run_web_app(host, port)` |
| `web_server.py` | HTTP server with all `/api/*` endpoints. Handles GET/POST requests, serves static files |

### Core Logic (`db_interpreter_app/core/`)

| File | Purpose |
|------|--------|
| `constants.py` | `MODE_SQL`, `MODE_NOSQL`, `MODE_PYMYSQL`, `DEFAULT_DB_FILE`, `SAFE_PYTHON_BUILTINS` for mock PyMySQL |
| `database_service.py` | **Main class: `DatabaseService`** - query execution, transactions, schema, generate SQL, autocomplete metadata |
| `explainer.py` | `explain_sql_query()` - converts SQL to plain English |
| `sql_utils.py` | `quote_identifier()` - escapes table/column names, `sql_literal()` - escapes values, `split_sql_statements()` - parses SQL |

### Frontend (`db_interpreter_app/web/`)

| File | Purpose |
|------|--------|
| `index.html` | HTML structure - toolbar, editor, output, sidebar panels |
| `styles.css` | All CSS - themes defined in `:root` and `[data-theme]` |
| `app.js` | All frontend JS - autocomplete, API calls, table rendering |

## Key Classes and Functions

### Backend

```python
# database_service.py
class DatabaseService:
    def __init__(self, base_dir)           # Initialize, connect to default DB
    def execute(mode, code, autocommit)      # Execute SQL/NoSQL/PyMySQL
    def switch_database(name)               # Switch to another .db file
    def create_database(name)             # Create new .db file
    def commit() / rollback()           # Transaction control
    def explain(query)                 # Call explainer.py
    def view_schema()                 # Get full schema (tables, columns, FKs)
    def generate_sql_code()             # Reverse engineer to CREATE/INSERT
    def nuke_database()              # DROP all tables
    def get_autocomplete_metadata()   # Tables + columns for autocomplete
```

### Frontend API Calls

```javascript
// app.js - all async API functions:
await request('/api/bootstrap')     // Initial state
await request('/api/execute', {method:'POST', body:{mode, code, autocommit}})
await request('/api/explain', {method:'POST', body:{query}})
await request('/api/schema')
await request('/api/generate-sql')
await request('/api/switch-db', {method:'POST', body:{name}})
await request('/api/create-db', {method:'POST', body:{name}})
await request('/api/commit', {method:'POST'})
await request('/api/rollback', {method:'POST'})
await request('/api/nuke', {method:'POST'})
```

## Adding New Features

1. **Backend logic**: Add method to `DatabaseService` in `database_service.py`
2. **API endpoint**: Add route in `web_server.py` (`_handle_api_get` or `_handle_api_post`)
3. **Frontend**: Add handler in `app.js`, call it from button click in `index.html`

## Key Locations

| Feature | File Location |
|---------|-------------|
| SQL execution | `database_service.py:186` (`_execute_sql`) |
| NoSQL mock | `database_service.py:252` (`_execute_nosql`) |
| PyMySQL mock | `database_service.py:339` (`_execute_python_mock`) |
| Schema view | `database_service.py:381` (`view_schema`) |
| Generate SQL | `database_service.py:612` (`generate_sql_code`) |
| Autocomplete building | `app.js:678` (`buildSqlSuggestions`) |
| Themes | `styles.css` (search `data-theme`) |
| Modes dropdown | `index.html:57` (`modeSelect`) |