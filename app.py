"""
app.py — PD KPI Meeting Attendance
Dash app with PostgreSQL backend, AD group access control
UI matches Power Apps design: dark blue header, data table, add/edit/delete
"""

import os
import uuid
import json
import dash
from dash import dcc, html, dash_table, Input, Output, State, callback, ctx, ALL
import dash_bootstrap_components as dbc
import pandas as pd
import psycopg2
import psycopg2.extras
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from ad_access import enforce_access, get_current_user, get_user_display_name

# ═══════════════════════════════════════════════════════════════════════
#  APP SETUP
# ═══════════════════════════════════════════════════════════════════════
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
    suppress_callback_exceptions=True, title="PD KPI Meeting Attendance")
server = app.server
enforce_access(server)

# ═══════════════════════════════════════════════════════════════════════
#  DATABASE
# ═══════════════════════════════════════════════════════════════════════
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port": os.getenv("DB_PORT", 5432),
}

SCHEMA_TABLE = "clin_trial_fnd_ref.pd_kpi_meeting_attandance"

COLUMNS = ["id", "attandance_id", "user_name", "user_email", "node_id", "dept_id",
    "role", "function", "attandance_expectation", "meeting_date",
    "attendee_type", "primary_node_yn", "active_yn",
    "created_by", "created_date", "modified_by", "modified_date"]

DISPLAY_COLUMNS = [
    {"id": "attandance_id", "name": "Att. ID", "type": "numeric"},
    {"id": "user_name", "name": "User Name", "type": "text"},
    {"id": "user_email", "name": "User Email", "type": "text"},
    {"id": "node_id", "name": "Node ID", "type": "text"},
    {"id": "dept_id", "name": "Dept ID", "type": "text"},
    {"id": "role", "name": "Role", "type": "text"},
    {"id": "function", "name": "Function", "type": "text"},
    {"id": "attandance_expectation", "name": "Att. Expectation", "type": "text"},
    {"id": "meeting_date", "name": "Meeting Date", "type": "text"},
    {"id": "attendee_type", "name": "Attendee Type", "type": "text"},
    {"id": "primary_node_yn", "name": "Primary", "type": "text"},
    {"id": "active_yn", "name": "Active", "type": "text"},
]


def get_db():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    return conn


def fetch_records():
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(f"SELECT {', '.join(COLUMNS)} FROM {SCHEMA_TABLE} ORDER BY created_date DESC LIMIT 500")
        rows = cur.fetchall()
        cur.close(); conn.close()
        # Convert dates and UUIDs to strings
        for r in rows:
            for k, v in r.items():
                if isinstance(v, (datetime,)): r[k] = v.strftime("%Y-%m-%d %H:%M")
                elif hasattr(v, 'isoformat'): r[k] = v.isoformat()
                elif isinstance(v, uuid.UUID): r[k] = str(v)
        return pd.DataFrame(rows), None
    except Exception as e:
        return pd.DataFrame(), str(e)


def insert_record(data):
    new_id = str(uuid.uuid4())
    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"""
        INSERT INTO {SCHEMA_TABLE}
            (id, user_name, user_email, node_id, dept_id, role, function,
             attandance_expectation, meeting_date, attendee_type,
             primary_node_yn, active_yn, created_by, created_date)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
    """, (new_id, data.get("user_name"), data.get("user_email"), data.get("node_id"),
          data.get("dept_id"), data.get("role"), data.get("function"),
          data.get("attandance_expectation"), data.get("meeting_date") or None,
          data.get("attendee_type"), data.get("primary_node_yn"), data.get("active_yn"),
          get_current_user()))
    cur.close(); conn.close()
    return True


def update_record(record_id, data):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"""
        UPDATE {SCHEMA_TABLE} SET
            user_name=%s, user_email=%s, node_id=%s, dept_id=%s, role=%s, function=%s,
            attandance_expectation=%s, meeting_date=%s, attendee_type=%s,
            primary_node_yn=%s, active_yn=%s,
            modified_by=%s, modified_date=CURRENT_TIMESTAMP AT TIME ZONE 'UTC'
        WHERE id=%s
    """, (data.get("user_name"), data.get("user_email"), data.get("node_id"),
          data.get("dept_id"), data.get("role"), data.get("function"),
          data.get("attandance_expectation"), data.get("meeting_date") or None,
          data.get("attendee_type"), data.get("primary_node_yn"), data.get("active_yn"),
          get_current_user(), record_id))
    cur.close(); conn.close()
    return True


def delete_record(record_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {SCHEMA_TABLE} WHERE id=%s", (record_id,))
    cur.close(); conn.close()
    return True


# ═══════════════════════════════════════════════════════════════════════
#  STYLES
# ═══════════════════════════════════════════════════════════════════════
HEADER_BG = "#1a237e"
HEADER_LIGHT = "#283593"
ROW_EVEN = "#FFFFFF"
ROW_ODD = "#F5F7FA"
BORDER = "#E0E0E0"

TABLE_STYLE = {
    "style_header": {
        "backgroundColor": HEADER_BG, "color": "white", "fontWeight": "600",
        "fontSize": "12px", "textAlign": "center", "padding": "10px 8px",
        "border": f"1px solid {HEADER_LIGHT}",
    },
    "style_data": {
        "fontSize": "13px", "padding": "8px", "border": f"1px solid {BORDER}",
        "whiteSpace": "normal", "height": "auto",
    },
    "style_data_conditional": [
        {"if": {"row_index": "odd"}, "backgroundColor": ROW_ODD},
        {"if": {"row_index": "even"}, "backgroundColor": ROW_EVEN},
        {"if": {"state": "selected"}, "backgroundColor": "#E3F2FD", "border": f"1px solid #1565C0"},
    ],
    "style_cell": {
        "textAlign": "left", "minWidth": "80px", "maxWidth": "200px", "overflow": "hidden", "textOverflow": "ellipsis",
    },
    "style_cell_conditional": [
        {"if": {"column_id": "attandance_id"}, "width": "70px", "textAlign": "center"},
        {"if": {"column_id": "user_name"}, "width": "150px", "fontWeight": "500"},
        {"if": {"column_id": "user_email"}, "width": "220px"},
        {"if": {"column_id": "node_id"}, "width": "80px", "textAlign": "center"},
        {"if": {"column_id": "dept_id"}, "width": "80px", "textAlign": "center"},
        {"if": {"column_id": "role"}, "width": "80px"},
        {"if": {"column_id": "function"}, "width": "100px"},
        {"if": {"column_id": "meeting_date"}, "width": "110px", "textAlign": "center"},
        {"if": {"column_id": "attendee_type"}, "width": "110px", "textAlign": "center"},
        {"if": {"column_id": "primary_node_yn"}, "width": "70px", "textAlign": "center"},
        {"if": {"column_id": "active_yn"}, "width": "60px", "textAlign": "center"},
    ],
    "style_table": {"overflowX": "auto", "borderRadius": "8px", "border": f"1px solid {BORDER}"},
}


# ═══════════════════════════════════════════════════════════════════════
#  FORM FIELDS FOR ADD/EDIT MODAL
# ═══════════════════════════════════════════════════════════════════════
def form_field(label, field_id, field_type="text", options=None, width=6):
    if options:
        comp = dcc.Dropdown(id=field_id, options=[{"label": o, "value": o} for o in options],
            placeholder=f"Select {label}...", style={"fontSize": "13px"})
    elif field_type == "date":
        comp = dcc.DatePickerSingle(id=field_id, display_format="MM/DD/YYYY", className="w-100",
            style={"fontSize": "13px"})
    else:
        comp = dbc.Input(id=field_id, type=field_type, size="sm",
            placeholder=f"Enter {label.lower()}...", style={"fontSize": "13px"})
    return dbc.Col([
        dbc.Label(label, className="small fw-semibold text-muted mb-1"), comp
    ], md=width, className="mb-3")


# ═══════════════════════════════════════════════════════════════════════
#  LAYOUT
# ═══════════════════════════════════════════════════════════════════════
app.layout = html.Div([
    # Header
    html.Div([
        html.Div([
            html.H4([html.I(className="fas fa-clipboard-check me-2"),
                "PD KPI Meeting Attendance"], className="text-white fw-bold mb-0"),
        ], className="d-flex align-items-center"),
        html.Div(id="header-user", className="d-flex align-items-center"),
    ], className="d-flex justify-content-between align-items-center px-4 py-3",
        style={"background": f"linear-gradient(135deg, {HEADER_BG}, {HEADER_LIGHT})", "boxShadow": "0 2px 8px rgba(0,0,0,0.15)"}),

    # Main Content
    html.Div([
        # Record count + Add button row
        html.Div([
            html.Div(id="record-count", className="text-muted"),
            html.Div([
                dbc.Button([html.I(className="fas fa-sync me-1"), "Refresh"], id="refresh-btn",
                    color="light", size="sm", className="me-2", style={"fontSize": "13px"}),
                dbc.Button([html.I(className="fas fa-trash me-1"), "Delete Selected"], id="delete-btn",
                    color="danger", size="sm", className="me-2", disabled=True, style={"fontSize": "13px"}),
                dbc.Button([html.I(className="fas fa-plus me-1"), "Add Row"], id="add-btn",
                    size="sm", style={"backgroundColor": HEADER_BG, "border": "none", "fontSize": "13px"}),
            ]),
        ], className="d-flex justify-content-between align-items-center mb-3"),

        # Data Table
        html.Div(id="table-container"),

        # Status message
        html.Div(id="status-msg"),
    ], className="px-4 py-3"),

    # Add/Edit Modal
    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle(id="modal-title"), style={"background": HEADER_BG, "color": "white"},
            close_button=True),
        dbc.ModalBody([
            dbc.Row([
                form_field("User Name", "f-user_name"),
                form_field("User Email", "f-user_email"),
            ]),
            dbc.Row([
                form_field("Node ID", "f-node_id", width=4),
                form_field("Dept ID", "f-dept_id", width=4),
                form_field("Role", "f-role", width=4),
            ]),
            dbc.Row([
                form_field("Function", "f-function"),
                form_field("Attendance Expectation", "f-att_expectation"),
            ]),
            dbc.Row([
                form_field("Meeting Date", "f-meeting_date", "date"),
                form_field("Attendee Type", "f-attendee_type", options=["core", "NonCore"]),
            ]),
            dbc.Row([
                form_field("Primary Node", "f-primary_node", options=["Y", "N"]),
                form_field("Active", "f-active", options=["Y", "N"]),
            ]),
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancel", id="modal-cancel", color="secondary", size="sm"),
            dbc.Button([html.I(className="fas fa-save me-1"), "Save"], id="modal-save",
                size="sm", style={"backgroundColor": HEADER_BG, "border": "none"}),
        ]),
    ], id="edit-modal", size="lg", is_open=False),
    dcc.Store(id="edit-record-id"),

    # Delete Confirmation Modal
    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Confirm Delete"), style={"background": "#D32F2F", "color": "white"}),
        dbc.ModalBody([
            html.Div([html.I(className="fas fa-exclamation-triangle fa-2x text-danger mb-2"),
                html.P("Are you sure you want to delete this record?", className="mb-1"),
                html.Small("This action cannot be undone.", className="text-muted")],
                className="text-center py-2"),
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancel", id="del-cancel", color="secondary", size="sm"),
            dbc.Button([html.I(className="fas fa-trash me-1"), "Delete"], id="del-confirm",
                color="danger", size="sm"),
        ]),
    ], id="del-modal", size="sm", centered=True, is_open=False),
    dcc.Store(id="del-record-id"),

    # Data store
    dcc.Store(id="data-store"),
], style={"backgroundColor": "#F5F7FA", "minHeight": "100vh"})


# ═══════════════════════════════════════════════════════════════════════
#  CALLBACKS
# ═══════════════════════════════════════════════════════════════════════

# Show user in header
@callback(Output("header-user", "children"), Input("data-store", "data"))
def show_user(_):
    uid = get_current_user()
    name = get_user_display_name(uid)
    email = f"{uid}@lilly.com"
    return html.Div([
        html.I(className="fas fa-envelope me-2 text-white-50"),
        html.Span(name or email, className="text-white", style={"fontSize": "14px"}),
    ], className="px-3 py-1", style={"backgroundColor": "rgba(255,255,255,0.1)", "borderRadius": "20px"})


# Load data
@callback([Output("data-store", "data"), Output("table-container", "children"),
    Output("record-count", "children")],
    [Input("refresh-btn", "n_clicks"), Input("data-store", "modified_timestamp")],
    prevent_initial_call=False)
def load_data(n, ts):
    df, err = fetch_records()
    if err:
        return [], dbc.Alert(f"Database error: {err}", color="danger"), "Error loading data"

    if df.empty:
        return [], dbc.Alert("No records found.", color="info", className="mt-3"), "0 records"

    # Build row number column
    df.insert(0, "row_num", range(1, len(df) + 1))

    # Format meeting_date for display
    if "meeting_date" in df.columns:
        df["meeting_date"] = df["meeting_date"].astype(str).str[:10]

    table = dash_table.DataTable(
        id="main-table",
        columns=[{"id": "row_num", "name": "#", "type": "numeric"}] + DISPLAY_COLUMNS,
        data=df.to_dict("records"),
        row_selectable="single",
        selected_rows=[],
        page_size=20,
        page_action="native",
        sort_action="native",
        sort_mode="single",
        filter_action="native",
        **TABLE_STYLE,
    )

    count_html = html.Span([
        "Showing ", html.Strong(str(len(df)), className="text-primary"), " records"
    ], style={"fontSize": "14px"})

    return df.to_dict("records"), table, count_html


# Open Add modal
@callback([Output("edit-modal", "is_open", allow_duplicate=True), Output("modal-title", "children"),
    Output("edit-record-id", "data"),
    Output("f-user_name", "value"), Output("f-user_email", "value"),
    Output("f-node_id", "value"), Output("f-dept_id", "value"), Output("f-role", "value"),
    Output("f-function", "value"), Output("f-att_expectation", "value"),
    Output("f-meeting_date", "date"), Output("f-attendee_type", "value"),
    Output("f-primary_node", "value"), Output("f-active", "value")],
    Input("add-btn", "n_clicks"), prevent_initial_call=True)
def open_add(n):
    return True, "Add New Record", None, "", "", "", "", "", "", "", None, None, None, None


# Edit on row double-click (via selected row)
@callback([Output("edit-modal", "is_open", allow_duplicate=True), Output("modal-title", "children", allow_duplicate=True),
    Output("edit-record-id", "data", allow_duplicate=True),
    Output("f-user_name", "value", allow_duplicate=True), Output("f-user_email", "value", allow_duplicate=True),
    Output("f-node_id", "value", allow_duplicate=True), Output("f-dept_id", "value", allow_duplicate=True),
    Output("f-role", "value", allow_duplicate=True), Output("f-function", "value", allow_duplicate=True),
    Output("f-att_expectation", "value", allow_duplicate=True), Output("f-meeting_date", "date", allow_duplicate=True),
    Output("f-attendee_type", "value", allow_duplicate=True), Output("f-primary_node", "value", allow_duplicate=True),
    Output("f-active", "value", allow_duplicate=True)],
    Input("main-table", "active_cell"),
    State("main-table", "data"), prevent_initial_call=True)
def edit_on_click(active_cell, data):
    if not active_cell or not data:
        return [dash.no_update] * 14
    row = data[active_cell["row"]]
    md = row.get("meeting_date", "")
    if md and len(str(md)) >= 10:
        md = str(md)[:10]
    else:
        md = None
    return (True, f"Edit: {row.get('user_name', '')}", row.get("id"),
        row.get("user_name", ""), row.get("user_email", ""),
        row.get("node_id", ""), row.get("dept_id", ""), row.get("role", ""),
        row.get("function", ""), row.get("attandance_expectation", ""),
        md, row.get("attendee_type"), row.get("primary_node_yn"), row.get("active_yn"))


# Save (create or update)
@callback([Output("edit-modal", "is_open"), Output("status-msg", "children"),
    Output("refresh-btn", "n_clicks")],
    Input("modal-save", "n_clicks"),
    [State("edit-record-id", "data"),
     State("f-user_name", "value"), State("f-user_email", "value"),
     State("f-node_id", "value"), State("f-dept_id", "value"), State("f-role", "value"),
     State("f-function", "value"), State("f-att_expectation", "value"),
     State("f-meeting_date", "date"), State("f-attendee_type", "value"),
     State("f-primary_node", "value"), State("f-active", "value")],
    prevent_initial_call=True)
def save_record(n, record_id, user_name, user_email, node_id, dept_id, role,
    function, att_exp, meeting_date, attendee_type, primary_node, active):
    if not user_name:
        return dash.no_update, dbc.Alert("User Name is required.", color="danger", duration=3000), dash.no_update

    data = {"user_name": user_name, "user_email": user_email, "node_id": node_id,
        "dept_id": dept_id, "role": role, "function": function,
        "attandance_expectation": att_exp, "meeting_date": meeting_date,
        "attendee_type": attendee_type, "primary_node_yn": primary_node, "active_yn": active}
    try:
        if record_id:
            update_record(record_id, data)
            msg = dbc.Alert("Record updated!", color="success", duration=3000)
        else:
            insert_record(data)
            msg = dbc.Alert("Record created!", color="success", duration=3000)
        return False, msg, 1  # Close modal + refresh
    except Exception as e:
        return dash.no_update, dbc.Alert(f"Error: {e}", color="danger", duration=5000), dash.no_update


# Close modal on cancel
@callback(Output("edit-modal", "is_open", allow_duplicate=True),
    Input("modal-cancel", "n_clicks"), prevent_initial_call=True)
def close_modal(n): return False


# Enable/disable Delete button based on row selection
@callback(Output("delete-btn", "disabled"),
    Input("main-table", "selected_rows"), prevent_initial_call=True)
def toggle_delete_btn(selected):
    return not (selected and len(selected) > 0)


# Delete — open confirmation when Delete Selected is clicked
@callback([Output("del-modal", "is_open"), Output("del-record-id", "data")],
    Input("delete-btn", "n_clicks"),
    [State("main-table", "selected_rows"), State("main-table", "data")],
    prevent_initial_call=True)
def ask_delete(n, selected, data):
    if not selected or not data:
        return False, None
    row = data[selected[0]]
    return True, row.get("id")


# Confirm delete
@callback([Output("del-modal", "is_open", allow_duplicate=True), Output("status-msg", "children", allow_duplicate=True),
    Output("refresh-btn", "n_clicks", allow_duplicate=True)],
    [Input("del-confirm", "n_clicks"), Input("del-cancel", "n_clicks")],
    State("del-record-id", "data"), prevent_initial_call=True)
def confirm_del(y, n, rid):
    if ctx.triggered_id == "del-cancel" or not rid:
        return False, dash.no_update, dash.no_update
    try:
        delete_record(rid)
        return False, dbc.Alert("Record deleted!", color="warning", duration=3000), 1
    except Exception as e:
        return False, dbc.Alert(f"Error: {e}", color="danger", duration=5000), dash.no_update


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
