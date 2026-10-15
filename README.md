# NETCOM Employee Management System Pro

Enterprise-grade, modular Django Human Resource Management System (HRMS) built with modern design principles, role-based workflows, automated attendance tracking, leave management, payroll processing, and business intelligence reporting.

---

## 1. Project Directory Structure

```text
employee_management/
│
├── manage.py
├── requirements.txt
├── .env
├── .gitignore
├── run_server.bat
│
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── apps/
│   ├── __init__.py
│   │
│   ├── employees/
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── forms.py
│   │   ├── admin.py
│   │   └── migrations/
│   │
│   ├── departments/
│   ├── attendance/
│   ├── leave_management/
│   ├── payroll/
│   ├── users/
│   ├── dashboard/
│   └── reports/
│
├── templates/
│   ├── base.html
│   ├── users/
│   ├── employees/
│   ├── departments/
│   ├── attendance/
│   ├── leave_management/
│   ├── payroll/
│   ├── dashboard/
│   └── reports/
│
├── static/
│   ├── css/
│   │   └── styles.css
│   ├── js/
│   │   └── main.js
│   └── images/
│
├── media/
│   └── employee_documents/
│
├── database/
│   ├── schema.sql
│   └── backups/
│       ├── employee_db_backup.json
│       └── employee_db_mysql_dump.sql
│
├── logs/
│   └── application.log
└── tests/
    ├── __init__.py
    └── test_all_features.py
```

---

## 2. Default Access Credentials

All existing user records and history have been preserved and migrated:

| Role | Username | Password | Dedicated Portal |
| :--- | :--- | :--- | :--- |
| **Administrator** | `NETCOM` | `Netcom@2026@Netcom` | `http://127.0.0.1:8000/dashboard/` |
| **HR Manager** | `hr` | `hr12345` | `http://127.0.0.1:8000/dashboard/` |
| **Employee** | `emp` | `emp12345` | `http://127.0.0.1:8000/dashboard/` |
| **Django Admin** | `NETCOM` | `Netcom@2026@Netcom` | `http://127.0.0.1:8000/django-admin/` |

> **Important:** The login endpoint remains strictly preserved at **`/login/`** (and `/` redirects directly to login/dashboard).

---

## 3. Quick Start & Execution

### Option A: One-Click Launcher (Windows)
Double-click `run_server.bat`. It will automatically:
1. Verify database migrations.
2. Start the Django server listening on `0.0.0.0:8000` (allowing local and LAN access).
3. Automatically open your browser to `http://127.0.0.1:8000/login/`.

### Option B: Command Line Terminal
```powershell
# 1. Navigate to employee_management
cd D:\employee_management\django_employee_management_pro\employee_management

# 2. Run database migrations
python manage.py migrate

# 3. Start server
python manage.py runserver 0.0.0.0:8000
```

Open your browser at: **`http://127.0.0.1:8000/login/`**

---

## 4. Multi-Computer & LAN Sharing Guide

To enable team members on other computers to access the system:

1. Find your host machine's local IP address (e.g., `192.168.1.50`):
   ```powershell
   ipconfig
   ```
2. Start the server bound to `0.0.0.0`:
   ```powershell
   python manage.py runserver 0.0.0.0:8000
   ```
3. Any computer on the same Wi-Fi / office network can access the portal via:
   ```text
   http://192.168.1.50:8000/login/
   ```
4. All links use dynamic Django reverse routing (`{% url '...' %}`), ensuring **zero broken links** when accessed across different domains or IPs.

---

## 5. Dual Database Architecture (MySQL & SQLite)

The application supports both **MySQL** (Default, with PyMySQL) and **SQLite**, configured directly in `.env`:

```ini
# Database Settings in .env
USE_MYSQL=True
DB_NAME=employee_db
DB_USER=root
DB_PASSWORD=root
DB_HOST=127.0.0.1
DB_PORT=3306
```

- When `USE_MYSQL=True`: Connects natively to MySQL Server 8.0 `employee_db`.
- When `USE_MYSQL=False`: Connects to `database/employee_db.sqlite3`.

---

## 6. Biometric Machine CSV Upload Format

When importing punches through the HR portal or Attendance page:

```csv
employee_code,date,time,type
EMP001,2026-10-12,09:30:00,in
EMP001,2026-10-12,18:15:00,out
HR001,2026-10-12,09:45:00,in
HR001,2026-10-12,18:30:00,out
```

---

## 7. Automated Test Suite

Run the comprehensive test suite verifying authentication, punch calculations, leave deduction, biometric import, and payroll vouchers:

```powershell
python manage.py test tests
```
*Expected: 7 tests passing in ~8s (`OK`).*
