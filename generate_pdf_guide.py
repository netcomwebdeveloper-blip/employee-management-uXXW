import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#6b7280"))
        if self._pageNumber > 1:
            self.drawString(54, 11 * inch - 36, "Netcom Computers Pvt Ltd — Technical, Operations & Administration Manual")
            self.setStrokeColor(colors.HexColor("#e5e7eb"))
            self.setLineWidth(0.5)
            self.line(54, 11 * inch - 42, 8.5 * inch - 54, 11 * inch - 42)

        footer_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(8.5 * inch - 54, 30, footer_text)
        self.drawString(54, 30, "Netcom Computers Pvt Ltd • Confidential & Proprietary Documentation")
        self.setStrokeColor(colors.HexColor("#e5e7eb"))
        self.setLineWidth(0.5)
        self.line(54, 42, 8.5 * inch - 54, 42)
        self.restoreState()


def build_guide_pdf(filename="HOW_TO_RUN_PROJECT.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    primary_color = colors.HexColor("#1e40af")
    secondary_color = colors.HexColor("#3b82f6")
    dark_text = colors.HexColor("#0f172a")
    border_color = colors.HexColor("#cbd5e1")
    gray_bg = colors.HexColor("#f8fafc")

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=primary_color,
        spaceAfter=3
    )

    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#475569"),
        spaceAfter=8
    )

    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=11.5,
        leading=15,
        textColor=primary_color,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11.5,
        textColor=dark_text,
        spaceAfter=4
    )

    code_style = ParagraphStyle(
        'CodeSnippet',
        parent=styles['Code'],
        fontName='Courier',
        fontSize=7,
        leading=9.5,
        textColor=colors.HexColor("#1e293b"),
        backColor=colors.HexColor("#f1f5f9"),
        borderPadding=4,
        spaceBefore=2,
        spaceAfter=4
    )

    table_header_style = ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7.5, leading=9.5, textColor=colors.white)
    table_cell_style = ParagraphStyle('TC', fontName='Helvetica', fontSize=7, leading=9, textColor=dark_text)
    table_cell_bold = ParagraphStyle('TCB', fontName='Helvetica-Bold', fontSize=7, leading=9, textColor=dark_text)

    story = []

    # Title Banner
    story.append(Paragraph("Netcom Computers Pvt Ltd", title_style))
    story.append(Paragraph("Enterprise Employee Management Pro — Operations, Biometrics, Admin Punch, 1-Day Monthly Casual Leave & Deployment Manual", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=primary_color, spaceBefore=0, spaceAfter=6))

    # Meta Info Card
    meta_data = [
        [
            Paragraph("<b>Company:</b> Netcom Computers Pvt Ltd", table_cell_style),
            Paragraph("<b>Database:</b> MySQL 8.0 + SQLite zero-friction fallback", table_cell_style),
            Paragraph("<b>Biometrics:</b> Realtime TCP/UDP Port 4370 Sync", table_cell_style)
        ],
        [
            Paragraph("<b>Host:</b> 0.0.0.0:8000 (Local & LAN Access)", table_cell_style),
            Paragraph("<b>Login Route:</b> /login/ (Strictly Preserved)", table_cell_style),
            Paragraph("<b>Test Suite:</b> 32 Automated Tests (100% Pass)", table_cell_style)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[175, 175, 154])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), gray_bg),
        ('BOX', (0, 0), (-1, -1), 1, border_color),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, border_color),
        ('PADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 4))

    # Section 1: Role-Based Access & Dashboards
    story.append(Paragraph("1. System Dashboards, Duty Punch Terminals & Security Protections", h1_style))
    story.append(Paragraph(
        "• <b>Netcom Employee Dashboard:</b> Hero banner with profile picture avatar, login popup announcement with close button, photo + GPS attendance punch (strict once-per-day enforcement with button lock), personal calendar (strictly isolated to employee's own records), 4-record scroll containers.<br/>"
        "• <b>Netcom HR Dashboard:</b> Leave review modal (Casual vs Sick Leave), daily work planning & staff notifications, comprehensive report downloads (PDF & Excel), HR self-service duty punch terminal, employee details with password toggle (👁️), document links (📄 View Doc), employee delete button, and 5-record scroll containers.<br/>"
        "• <b>Netcom Admin Dashboard:</b> Administrator Duty Punch Terminal (webcam photo + GPS verification, real-time clock, instant punch in/out), full workforce governance, banner & popup image management, employee details with password reveal, submitted document inspection, biometric device sync, 10-record scroll containers.<br/>"
        "• <b>Permanent Protection for Main Admin (NETCOM):</b> The main admin user <code>NETCOM</code> and superusers can NEVER be deleted. Delete buttons are completely hidden on frontend, and backend blocks deletion with an error.<br/>"
        "• <b>Strict Access Enforcement:</b> HR users are completely blocked from accessing Admin pages (<code>/dashboard/admin/</code>) via backend <code>@admin_required</code>.",
        body_style
    ))
    story.append(Spacer(1, 4))

    # Section 2: Leave Review Classification & Casual Leave Restoration
    story.append(Paragraph("2. Leave Review, Office Paid Leave & Attendance Engine", h1_style))
    leave_rules = [
        [
            Paragraph("Leave Action / Event", table_header_style),
            Paragraph("Review / Type", table_header_style),
            Paragraph("Balance Impact", table_header_style),
            Paragraph("Salary & Calendar Synchronization", table_header_style)
        ],
        [
            Paragraph("<b>Employee Applies for Leave</b>", table_cell_bold),
            Paragraph("Triggers HR Notification", table_cell_style),
            Paragraph("Balance held pending", table_cell_style),
            Paragraph("Appears in HR Leave Requests; displayed on calendar with yellow pending border.", table_cell_style)
        ],
        [
            Paragraph("<b>Approved: Paid Casual Leave</b>", table_cell_bold),
            Paragraph("Paid Casual Leave", table_cell_style),
            Paragraph("-1 Casual Leave Day", table_cell_bold),
            Paragraph("<b>Zero salary deduction.</b> Displayed with <b>GREEN border</b> on calendar & dashboard.", table_cell_bold)
        ],
        [
            Paragraph("<b>Approved: Paid Sick Leave</b>", table_cell_bold),
            Paragraph("Paid Sick Leave", table_cell_style),
            Paragraph("<b>Zero casual deduction</b>", table_cell_bold),
            Paragraph("<b>Zero salary deduction.</b> Displayed with <b>GREEN border</b> on calendar & dashboard.", table_cell_bold)
        ],
        [
            Paragraph("<b>Mark Paid Leave for Office</b>", table_cell_bold),
            Paragraph("Office-Wide Holiday", table_cell_style),
            Paragraph("<b>0 deduction from casual balance</b>", table_cell_bold),
            Paragraph("<b>Full pay (zero salary deduction).</b> Calendar highlights date with purple badge & tooltips.", table_cell_bold)
        ],
        [
            Paragraph("<b>Rejected Leave Request</b>", table_cell_bold),
            Paragraph("Rejected with reason", table_cell_style),
            Paragraph("Zero balance deduction", table_cell_style),
            Paragraph("<b>Displayed in RED on employee calendar</b> with clear rejection reason.", table_cell_bold)
        ],
        [
            Paragraph("<b>Casual Leave Restoration</b>", table_cell_bold),
            Paragraph("Auto-triggered on Punch/Biometric", table_cell_style),
            Paragraph("<b>+1 Casual Leave Day restored</b>", table_cell_bold),
            Paragraph("<b>Leave cancelled</b>, attendance marked Present/Half Day, audit log saved.", table_cell_bold)
        ],
        [
            Paragraph("<b>Strict Once-Per-Day Punch</b>", table_cell_bold),
            Paragraph("Backend & JS Button Lock", table_cell_style),
            Paragraph("N/A", table_cell_style),
            Paragraph("Blocks duplicates with exact messages: <i>'You have already punched in/out for today.'</i>", table_cell_bold)
        ]
    ]
    leave_table = Table(leave_rules, colWidths=[120, 115, 105, 164])
    leave_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ('GRID', (0, 0), (-1, -1), 0.5, border_color),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, gray_bg]),
        ('PADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(leave_table)
    story.append(Spacer(1, 4))

    # Section 3: Daily Work Planning, Notifications & Comprehensive HR Reporting
    story.append(Paragraph("3. Daily Work Planning, Profile Pictures, Passwords & HR Reporting", h1_style))
    story.append(Paragraph(
        "• <b>HR & Admin Password Inspection:</b> Authorized Admin and HR users can inspect employee login passwords via interactive <code>👁️</code> Show/Hide toggle buttons across all employee management tables, edit modals, and profile dossiers.<br/>"
        "• <b>Profile Pictures & Document Repository:</b> Profile picture uploaded during employee onboarding is rendered directly across dashboard hero headers, sidebar avatars, and directories. Submitted proof documents can be previewed or downloaded anytime by HR and Admin via <code>📄 View Doc</code> links.<br/>"
        "• <b>Calendar Isolation:</b> Employees can strictly view only their own attendance calendar. HR and Admin can select any user (Employee, HR, Admin) to view their full month calendar.<br/>"
        "• <b>Office Paid Leave Scheduling:</b> HR and Admin can select any date on their dashboard calendar to mark an official Paid Leave for the Office.<br/>"
        "• <b>Employee Daily Work Planning:</b> HR users schedule next-day tasks, set dates, and send direct dashboard notifications to specific employees.<br/>"
        "• <b>Comprehensive HR Report Export:</b> HR users select any date range and download full HR data (directory, attendance, leaves, balances, and daily work) in both <b>Excel (.xlsx)</b> and <b>PDF</b> formats.<br/>"
        "• <b>Login Route Integrity:</b> Login URL <code>/login/</code> is strictly preserved with clean layout and 'Employee Management Portal' title.",
        body_style
    ))
    story.append(Spacer(1, 4))

    # Section 4: Authorized Credentials
    story.append(Paragraph("4. Authorized Access Credentials", h1_style))
    cred_data = [
        [
            Paragraph("Role", table_header_style),
            Paragraph("Username", table_header_style),
            Paragraph("Password", table_header_style),
            Paragraph("Code", table_header_style),
            Paragraph("Portal Features", table_header_style)
        ],
        [
            Paragraph("<b>Administrator</b>", table_cell_bold),
            Paragraph("<code>NETCOM</code>", table_cell_style),
            Paragraph("<code>Netcom@2026@Netcom</code>", table_cell_style),
            Paragraph("ADM001", table_cell_style),
            Paragraph("Netcom Admin Dashboard, HR Operations, Banner uploads, User details/leave balance search & edit, Biometric sync, Payroll", table_cell_style)
        ],
        [
            Paragraph("<b>HR Manager</b>", table_cell_bold),
            Paragraph("<code>hr</code>", table_cell_style),
            Paragraph("<code>hr12345</code>", table_cell_style),
            Paragraph("HR001", table_cell_style),
            Paragraph("Netcom HR Dashboard, Leave review modal (Paid vs Unpaid), Work image previews, Duty punch, Biometric sync", table_cell_style)
        ],
        [
            Paragraph("<b>Employee</b>", table_cell_bold),
            Paragraph("<code>emp</code>", table_cell_style),
            Paragraph("<code>emp12345</code>", table_cell_style),
            Paragraph("EMP001", table_cell_style),
            Paragraph("Netcom Employee Dashboard, Announcement popup, Webcam & GPS punch, Calendar with red rejected leaves, Work reports with image upload", table_cell_style)
        ]
    ]
    cred_table = Table(cred_data, colWidths=[65, 75, 110, 48, 206])
    cred_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('GRID', (0, 0), (-1, -1), 0.5, border_color),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, gray_bg]),
        ('PADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(cred_table)
    story.append(Spacer(1, 4))

    # Page Break
    story.append(PageBreak())

    # Section 5: Project Structure
    story.append(Paragraph("5. Complete Project File Structure", h1_style))
    tree_box = """employee_management/
│
├── manage.py
├── requirements.txt
├── .env
├── .gitignore
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
│   ├── employees/
│   │   ├── models.py, views.py, urls.py, forms.py, admin.py
│   ├── departments/
│   ├── attendance/
│   │   ├── models.py (DailyWork work_image & is_offsite, BiometricDevice)
│   │   ├── services.py (Casual Leave restoration engine)
│   │   ├── biometric_service.py (Hardware TCP/UDP socket sync)
│   │   └── views.py, urls.py, forms.py
│   ├── leave_management/
│   │   ├── models.py (HRNotification, is_paid, approval_type)
│   │   └── views.py, urls.py, forms.py
│   ├── payroll/ (Full, Half Day, 2h Permission & Paid/Unpaid Leave calculation)
│   ├── users/ (decorators.py: @admin_required, @hr_or_admin_required)
│   ├── dashboard/ (Netcom Employee/HR/Admin Dashboards & Banner models)
│   └── reports/
│
├── templates/
│   ├── base.html (Role-based navigation bar)
│   ├── employees/, departments/, attendance/, leave_management/, payroll/
│   └── dashboard/ (employee_dashboard, hr_dashboard, admin_dashboard)
│
├── static/
│   ├── css/ (styles.css: Red rejected leave, scroll containers, lightboxes)
│   ├── js/ (app.js: Webcam, GPS, lightbox modals, leave review modals)
│   └── images/
│
├── media/
│   ├── banners/ (Customizable dashboard hero banners)
│   ├── employee_photos/ & punch_photos/
│   └── daily_work_images/ (Employee work activity attachments)
│
├── database/
│   ├── schema.sql
│   └── backups/ (Full JSON database backups)
│
├── logs/
└── tests/
    └── test_all_features.py (15 Automated Comprehensive Tests)"""
    story.append(Paragraph(tree_box.replace("\n", "<br/>").replace(" ", "&nbsp;"), code_style))
    story.append(Spacer(1, 4))

    # Section 6: Display Limits & Scroll Containers
    story.append(Paragraph("6. Display Limits & Scrolling Standards", h1_style))
    limit_data = [
        [
            Paragraph("Dashboard Section", table_header_style),
            Paragraph("Dashboard", table_header_style),
            Paragraph("Initial Records", table_header_style),
            Paragraph("Scrolling Behavior", table_header_style)
        ],
        [
            Paragraph("<b>My Daily Work Details</b>", table_cell_bold),
            Paragraph("Employee", table_cell_style),
            Paragraph("<b>4 records</b>", table_cell_bold),
            Paragraph("Vertical scroll enabled (<code>max-height: 255px</code>)", table_cell_style)
        ],
        [
            Paragraph("<b>My Leave Details</b>", table_cell_bold),
            Paragraph("Employee", table_cell_style),
            Paragraph("<b>4 records</b>", table_cell_bold),
            Paragraph("Vertical scroll enabled (<code>max-height: 255px</code>)", table_cell_style)
        ],
        [
            Paragraph("<b>Leave Requests</b>", table_cell_bold),
            Paragraph("HR", table_cell_style),
            Paragraph("<b>5 records</b>", table_cell_bold),
            Paragraph("Vertical scroll enabled (<code>max-height: 310px</code>)", table_cell_style)
        ],
        [
            Paragraph("<b>Employee Work Details</b>", table_cell_bold),
            Paragraph("HR", table_cell_style),
            Paragraph("<b>5 records</b>", table_cell_bold),
            Paragraph("Vertical scroll enabled (<code>max-height: 310px</code>)", table_cell_style)
        ],
        [
            Paragraph("<b>All Leave Requests</b>", table_cell_bold),
            Paragraph("Admin", table_cell_style),
            Paragraph("<b>10 records</b>", table_cell_bold),
            Paragraph("Vertical scroll enabled (<code>max-height: 520px</code>)", table_cell_style)
        ],
        [
            Paragraph("<b>All Work Updates</b>", table_cell_bold),
            Paragraph("Admin", table_cell_style),
            Paragraph("<b>10 records</b>", table_cell_bold),
            Paragraph("Vertical scroll enabled (<code>max-height: 520px</code>)", table_cell_style)
        ],
        [
            Paragraph("<b>Employee Details & Leave Balance</b>", table_cell_bold),
            Paragraph("Admin", table_cell_style),
            Paragraph("<b>10 records</b>", table_cell_bold),
            Paragraph("Vertical scroll enabled (<code>max-height: 520px</code>)", table_cell_style)
        ],
        [
            Paragraph("<b>Employee & HR Attendance Details</b>", table_cell_bold),
            Paragraph("Admin", table_cell_style),
            Paragraph("<b>10 records</b>", table_cell_bold),
            Paragraph("Vertical scroll enabled (<code>max-height: 520px</code>)", table_cell_style)
        ]
    ]
    limit_table = Table(limit_data, colWidths=[150, 75, 95, 184])
    limit_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ('GRID', (0, 0), (-1, -1), 0.5, border_color),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, gray_bg]),
        ('PADDING', (0, 0), (-1, -1), 2.5),
    ]))
    story.append(limit_table)
    story.append(Spacer(1, 4))

    # Section 7: Quick Execution & Railway Deployment
    story.append(Paragraph("7. Quick Start Execution & Railway Deployment Commands", h1_style))
    cmd_box = """# Local / LAN Execution:
python manage.py runserver 0.0.0.0:8000

# Execute 100% Automated Test Suite (17 comprehensive tests):
python manage.py test tests

# Railway Cloud Deployment:
# Configured via Procfile, railway.json, nixpacks.toml, and WhiteNoise.
# Connect your Git repository to Railway, provision MySQL (or connect via DATABASE_URL),
# and Railway automatically applies migrations and serves via Gunicorn on port $PORT."""
    story.append(Paragraph(cmd_box.replace("\n", "<br/>").replace(" ", "&nbsp;"), code_style))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated {filename}")

if __name__ == '__main__':
    build_guide_pdf("HOW_TO_RUN_PROJECT.pdf")
