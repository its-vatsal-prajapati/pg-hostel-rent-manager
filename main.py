from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3
from datetime import datetime, date

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

DATABASE = "database.db"


# -------------------------
# DATABASE INIT
# -------------------------
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tenants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            room TEXT NOT NULL,
            phone TEXT NOT NULL,
            rent REAL NOT NULL,
            due_date TEXT NOT NULL,
            late_fee_type TEXT NOT NULL,
            late_fee_value REAL NOT NULL,
            last_paid_date TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()


# -------------------------
# HELPER: MONTHS LATE
# -------------------------
def months_late(due_date, today):
    months = (today.year - due_date.year) * 12 + today.month - due_date.month
    return max(0, months)


# -------------------------
# HOME PAGE
# -------------------------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tenants")
    tenants = cursor.fetchall()
    conn.close()

    today = date.today()
    updated = []

    for t in tenants:
        due_date = datetime.strptime(t["due_date"], "%Y-%m-%d").date()
        delay = months_late(due_date, today)

        if delay > 0:
            if t["late_fee_type"] == "percentage":
                late_fee = (t["rent"] * (t["late_fee_value"] / 100)) * delay
            else:
                late_fee = t["late_fee_value"] * delay
        else:
            late_fee = 0

        total = t["rent"] + late_fee

        status = "Paid" if t["last_paid_date"] else (
            "Late" if delay > 0 else "Pending"
        )

        updated.append({
            "id": t["id"],
            "name": t["name"],
            "room": t["room"],
            "rent": t["rent"],
            "late_fee": round(late_fee, 2),
            "total": round(total, 2),
            "status": status
        })

    return templates.TemplateResponse("index.html", {
        "request": request,
        "tenants": updated
    })


# -------------------------
# ADD TENANT
# -------------------------
@app.post("/add")
def add_tenant(
    name: str = Form(...),
    room: str = Form(...),
    phone: str = Form(...),
    rent: float = Form(...),
    due_date: str = Form(...),
    late_fee_type: str = Form(...),
    late_fee_value: float = Form(...)
):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO tenants 
        (name, room, phone, rent, due_date, late_fee_type, late_fee_value)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, room, phone, rent, due_date, late_fee_type, late_fee_value))

    conn.commit()
    conn.close()

    return RedirectResponse("/", status_code=303)


# -------------------------
# MARK PAID
# -------------------------
@app.get("/mark_paid/{tenant_id}")
def mark_paid(tenant_id: int):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE tenants
        SET last_paid_date = ?
        WHERE id = ?
    """, (date.today().isoformat(), tenant_id))
    conn.commit()
    conn.close()

    return RedirectResponse("/", status_code=303)


# -------------------------
# REMINDER MESSAGE
# -------------------------
@app.get("/reminder/{tenant_id}")
def reminder(tenant_id: int):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,))
    t = cursor.fetchone()
    conn.close()

    if not t:
        return JSONResponse({"error": "Not found"}, status_code=404)

    today = date.today()
    due_date = datetime.strptime(t["due_date"], "%Y-%m-%d").date()
    delay = months_late(due_date, today)

    if delay > 0:
        if t["late_fee_type"] == "percentage":
            late_fee = (t["rent"] * (t["late_fee_value"] / 100)) * delay
            policy = f"{t['late_fee_value']}% per month"
        else:
            late_fee = t["late_fee_value"] * delay
            policy = f"₹{t['late_fee_value']} per month"
    else:
        late_fee = 0
        policy = "No Late Fee"

    total = t["rent"] + late_fee

    message = f"""
Hi {t['name']},

Your rent of ₹{t['rent']} for Room {t['room']} is pending.

Late Fee Policy: {policy}
Late Fee Applied: ₹{round(late_fee,2)}

Total Payable: ₹{round(total,2)}

Kindly clear the payment soon.

Thank you.
"""

    return JSONResponse({"message": message.strip()})
