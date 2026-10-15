import csv
import io
import os
from datetime import date, timedelta, datetime
from django.conf import settings
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable, Image as RLImage
)
from apps.users.decorators import hr_or_admin_required
from apps.employees.models import Employee
from apps.departments.models import Department
from apps.attendance.models import Attendance
from apps.leave_management.models import LeaveRequest
from apps.payroll.models import PayrollRecord

@login_required
@hr_or_admin_required
def reports_index(request):
    total_staff = Employee.objects.filter(is_active_employee=True).count()
    total_records = Attendance.objects.count()
    total_leaves = LeaveRequest.objects.count()
    total_payroll = PayrollRecord.objects.count()

    context = {
        'total_staff': total_staff,
        'total_records': total_records,
        'total_leaves': total_leaves,
        'total_payroll': total_payroll,
    }
    return render(request, 'reports/reports_index.html', context)

@login_required
@hr_or_admin_required
def attendance_report(request):
    start_date = request.GET.get('start_date', (date.today() - timedelta(days=30)).strftime('%Y-%m-%d'))
    end_date = request.GET.get('end_date', date.today().strftime('%Y-%m-%d'))
    dept_id = request.GET.get('department', '')
    export = request.GET.get('export', '')

    records = Attendance.objects.select_related('employee', 'employee__user', 'employee__department').filter(
        date__range=[start_date, end_date]
    )
    if dept_id:
        records = records.filter(employee__department_id=dept_id)

    if export == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="attendance_report_{start_date}_to_{end_date}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Employee Code', 'Name', 'Department', 'Date', 'In Time', 'Out Time', 'Duration', 'Source', 'Status'])
        for r in records:
            writer.writerow([
                r.employee.employee_code,
                r.employee.display_name(),
                r.employee.department.name if r.employee.department else 'N/A',
                r.date,
                r.in_time or '-',
                r.out_time or '-',
                r.total_work_time,
                r.update_source,
                r.status,
            ])
        return response

    context = {
        'records': records[:200],
        'start_date': start_date,
        'end_date': end_date,
        'dept_id': dept_id,
        'departments': Department.objects.all(),
        'total_count': records.count(),
    }
    return render(request, 'reports/attendance_report.html', context)

@login_required
@hr_or_admin_required
def leave_report(request):
    year = int(request.GET.get('year', date.today().year))
    leaves = LeaveRequest.objects.select_related('employee', 'employee__user', 'employee__department').filter(
        from_date__year=year
    )

    stats = leaves.values('status').annotate(count=Count('id'))
    type_stats = leaves.values('leave_type').annotate(count=Count('id'), days=Sum('total_days'))

    context = {
        'leaves': leaves[:150],
        'year': year,
        'stats': stats,
        'type_stats': type_stats,
        'total_leaves': leaves.count(),
    }
    return render(request, 'reports/leave_report.html', context)

@login_required
@hr_or_admin_required
def payroll_report(request):
    year = int(request.GET.get('year', date.today().year))
    records = PayrollRecord.objects.select_related('employee', 'employee__user', 'employee__department').filter(
        year=year
    )

    monthly_summary = records.values('month').annotate(
        total_payout=Sum('net_salary'),
        headcount=Count('id')
    ).order_by('month')

    context = {
        'year': year,
        'monthly_summary': monthly_summary,
        'records': records[:150],
        'total_year_payout': records.aggregate(total=Sum('net_salary'))['total'] or 0,
    }
    return render(request, 'reports/payroll_report.html', context)


class NumberedLandscapeCanvas(canvas.Canvas):
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
        self.setFillColor(colors.HexColor("#64748b"))
        if self._pageNumber > 1:
            self.drawString(40, 8.5 * inch - 26, "Netcom Computers Pvt Ltd • Comprehensive HR Operations & Attendance Report")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(40, 8.5 * inch - 30, 11 * inch - 40, 8.5 * inch - 30)

        footer_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(11 * inch - 40, 22, footer_text)
        self.drawString(40, 22, "Netcom Computers Pvt Ltd • Official Corporate Record • Confidential")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(40, 28, 11 * inch - 40, 28)
        self.restoreState()


@login_required
@hr_or_admin_required
def complete_hr_report_export(request):
    """
    Exports comprehensive HR data across employee details, attendance history,
    leave records, leave balances, and daily work updates in professional PDF and Excel formats.
    """
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable, Image as RLImage
    )
    from apps.attendance.models import DailyWork

    today = date.today()
    start_date_str = request.GET.get('from_date') or request.GET.get('start_date') or (today - timedelta(days=30)).strftime('%Y-%m-%d')
    end_date_str = request.GET.get('to_date') or request.GET.get('end_date') or today.strftime('%Y-%m-%d')
    export_format = (request.GET.get('format') or 'pdf').lower()

    try:
        from_d = datetime.strptime(start_date_str[:10], '%Y-%m-%d').date()
    except (ValueError, TypeError):
        from_d = today - timedelta(days=30)

    try:
        to_d = datetime.strptime(end_date_str[:10], '%Y-%m-%d').date()
    except (ValueError, TypeError):
        to_d = today

    if to_d < from_d:
        from_d, to_d = to_d, from_d

    # Fetch data collections
    employees = Employee.objects.select_related('user', 'department', 'designation').all().order_by('employee_code')
    attendances = Attendance.objects.select_related('employee', 'employee__user', 'employee__department').filter(
        date__range=[from_d, to_d]
    ).order_by('-date', 'employee__employee_code')
    leaves = LeaveRequest.objects.select_related('employee', 'employee__user', 'reviewed_by').filter(
        from_date__lte=to_d, to_date__gte=from_d
    ).order_by('-from_date')
    daily_works = DailyWork.objects.select_related('employee', 'employee__user').filter(
        date__range=[from_d, to_d]
    ).order_by('-date')

    # Metrics
    total_staff = employees.count()
    total_punches = attendances.count()
    total_presents = attendances.filter(status='Present').count()
    total_half_days = attendances.filter(status='Half Day').count()
    total_permissions = attendances.filter(is_permission=True).count()
    total_approved_leaves = leaves.filter(status='Approved').count()
    total_work_logs = daily_works.count()

    # 1. EXCEL EXPORT (.xlsx)
    if export_format in ('excel', 'xlsx'):
        wb = Workbook()
        # Default sheet -> Summary
        ws_sum = wb.active
        ws_sum.title = "HR Executive Summary"
        ws_sum.views.sheetView[0].showGridLines = True

        header_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='1E3A8A', end_color='1E3A8A', fill_type='solid')
        sub_header_fill = PatternFill(start_color='16A34A', end_color='16A34A', fill_type='solid')
        title_font = Font(name='Calibri', size=16, bold=True, color='1E3A8A')
        bold_font = Font(name='Calibri', size=11, bold=True)
        thin_border = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )

        ws_sum['A1'] = "NETCOM COMPUTERS PVT LTD - COMPREHENSIVE HR OPERATIONS REPORT"
        ws_sum['A1'].font = title_font
        ws_sum['A2'] = f"Report Date Range: {from_d.strftime('%b %d, %Y')} to {to_d.strftime('%b %d, %Y')}  |  Generated on: {today.strftime('%b %d, %Y')} by {request.user.username}"
        ws_sum['A2'].font = Font(name='Calibri', size=11, italic=True, color='475569')

        summary_metrics = [
            ("Total Registered Workforce", total_staff),
            ("Total Attendance Records (Date Range)", total_punches),
            ("Full-Day Attendance Logs (>=9h)", total_presents),
            ("Half-Day Attendance Logs (>=4.5h)", total_half_days),
            ("Approved 2-Hour Permissions", total_permissions),
            ("Approved Leave Records", total_approved_leaves),
            ("Daily Work Logs Submitted", total_work_logs),
        ]

        ws_sum['A4'] = "Key Performance Indicator (KPI)"
        ws_sum['B4'] = "Metric Value"
        ws_sum['A4'].font = header_font
        ws_sum['A4'].fill = sub_header_fill
        ws_sum['B4'].font = header_font
        ws_sum['B4'].fill = sub_header_fill

        row_idx = 5
        for kpi, val in summary_metrics:
            ws_sum.cell(row=row_idx, column=1, value=kpi).border = thin_border
            c = ws_sum.cell(row=row_idx, column=2, value=val)
            c.font = bold_font
            c.alignment = Alignment(horizontal='right')
            c.border = thin_border
            row_idx += 1

        ws_sum.column_dimensions['A'].width = 42
        ws_sum.column_dimensions['B'].width = 20

        # Sheet 2: Employee Directory & Leave Balances
        ws_emp = wb.create_sheet(title="Employees & Leave Balances")
        ws_emp.views.sheetView[0].showGridLines = True
        emp_cols = [
            "Employee Code", "Full Name", "Username", "Email", "Phone",
            "Department", "Designation", "Role", "Casual Leave Balance", "Account Status"
        ]
        for col_num, h_text in enumerate(emp_cols, 1):
            cell = ws_emp.cell(row=1, column=col_num, value=h_text)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')

        for r_idx, emp in enumerate(employees, 2):
            ws_emp.cell(row=r_idx, column=1, value=emp.employee_code).border = thin_border
            ws_emp.cell(row=r_idx, column=2, value=emp.display_name()).border = thin_border
            ws_emp.cell(row=r_idx, column=3, value=emp.user.username).border = thin_border
            ws_emp.cell(row=r_idx, column=4, value=emp.email or '').border = thin_border
            ws_emp.cell(row=r_idx, column=5, value=emp.phone or '').border = thin_border
            ws_emp.cell(row=r_idx, column=6, value=emp.department.name if emp.department else 'Unassigned').border = thin_border
            ws_emp.cell(row=r_idx, column=7, value=emp.designation.title if emp.designation else '-').border = thin_border
            ws_emp.cell(row=r_idx, column=8, value=emp.get_role_display()).border = thin_border
            c_bal = ws_emp.cell(row=r_idx, column=9, value=emp.casual_leave_balance)
            c_bal.border = thin_border
            c_bal.alignment = Alignment(horizontal='right')
            ws_emp.cell(row=r_idx, column=10, value="Active" if emp.is_active_employee else "Inactive").border = thin_border

        for col in ws_emp.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            ws_emp.column_dimensions[col_letter].width = max(max_len + 3, 12)

        # Sheet 3: Attendance Records
        ws_att = wb.create_sheet(title="Attendance History")
        ws_att.views.sheetView[0].showGridLines = True
        att_cols = [
            "Date", "Employee Code", "Employee Name", "Department",
            "Punch In", "Punch Out", "Total Work Duration", "Status",
            "2h Permission", "Leave Type", "Punch Location / GPS", "Update Source"
        ]
        for col_num, h_text in enumerate(att_cols, 1):
            cell = ws_att.cell(row=1, column=col_num, value=h_text)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')

        for r_idx, att in enumerate(attendances, 2):
            ws_att.cell(row=r_idx, column=1, value=str(att.date)).border = thin_border
            ws_att.cell(row=r_idx, column=2, value=att.employee.employee_code).border = thin_border
            ws_att.cell(row=r_idx, column=3, value=att.employee.display_name()).border = thin_border
            ws_att.cell(row=r_idx, column=4, value=att.employee.department.name if att.employee.department else '-').border = thin_border
            ws_att.cell(row=r_idx, column=5, value=str(att.in_time) if att.in_time else '--:--').border = thin_border
            ws_att.cell(row=r_idx, column=6, value=str(att.out_time) if att.out_time else '--:--').border = thin_border
            ws_att.cell(row=r_idx, column=7, value=att.total_work_time).border = thin_border
            ws_att.cell(row=r_idx, column=8, value=att.status).border = thin_border
            ws_att.cell(row=r_idx, column=9, value="Yes (2h)" if att.is_permission else "No").border = thin_border
            ws_att.cell(row=r_idx, column=10, value=att.leave_type or '-').border = thin_border
            ws_att.cell(row=r_idx, column=11, value=att.in_location or '-').border = thin_border
            ws_att.cell(row=r_idx, column=12, value=att.update_source or 'System').border = thin_border

        for col in ws_att.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            ws_att.column_dimensions[col_letter].width = max(max_len + 3, 12)

        # Sheet 4: Leave Requests
        ws_lv = wb.create_sheet(title="Leave Requests")
        ws_lv.views.sheetView[0].showGridLines = True
        lv_cols = [
            "Request ID", "Employee Code", "Employee Name", "Leave Type",
            "From Date", "To Date", "Total Days", "Status",
            "Classification", "Reason / Purpose", "Reviewer", "Rejection / Audit Notes"
        ]
        for col_num, h_text in enumerate(lv_cols, 1):
            cell = ws_lv.cell(row=1, column=col_num, value=h_text)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')

        for r_idx, lv in enumerate(leaves, 2):
            ws_lv.cell(row=r_idx, column=1, value=lv.id).border = thin_border
            ws_lv.cell(row=r_idx, column=2, value=lv.employee.employee_code).border = thin_border
            ws_lv.cell(row=r_idx, column=3, value=lv.employee.display_name()).border = thin_border
            ws_lv.cell(row=r_idx, column=4, value=lv.leave_type).border = thin_border
            ws_lv.cell(row=r_idx, column=5, value=str(lv.from_date)).border = thin_border
            ws_lv.cell(row=r_idx, column=6, value=str(lv.to_date)).border = thin_border
            c_days = ws_lv.cell(row=r_idx, column=7, value=lv.total_days)
            c_days.border = thin_border
            c_days.alignment = Alignment(horizontal='right')
            ws_lv.cell(row=r_idx, column=8, value=lv.status).border = thin_border
            ws_lv.cell(row=r_idx, column=9, value=lv.approval_type or ('Paid' if lv.is_paid else 'Unpaid')).border = thin_border
            ws_lv.cell(row=r_idx, column=10, value=lv.reason).border = thin_border
            ws_lv.cell(row=r_idx, column=11, value=lv.reviewed_by.username if lv.reviewed_by else '-').border = thin_border
            ws_lv.cell(row=r_idx, column=12, value=lv.rejection_reason or '-').border = thin_border

        for col in ws_lv.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            ws_lv.column_dimensions[col_letter].width = max(max_len + 3, 12)

        # Sheet 5: Daily Work Updates
        ws_wk = wb.create_sheet(title="Daily Work Updates")
        ws_wk.views.sheetView[0].showGridLines = True
        wk_cols = [
            "Date", "Employee Code", "Employee Name", "Project / Module",
            "Work Accomplishments", "Status", "Off-Site Activity", "Location Notes", "Has Image"
        ]
        for col_num, h_text in enumerate(wk_cols, 1):
            cell = ws_wk.cell(row=1, column=col_num, value=h_text)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')

        for r_idx, wk in enumerate(daily_works, 2):
            ws_wk.cell(row=r_idx, column=1, value=str(wk.date)).border = thin_border
            ws_wk.cell(row=r_idx, column=2, value=wk.employee.employee_code).border = thin_border
            ws_wk.cell(row=r_idx, column=3, value=wk.employee.display_name()).border = thin_border
            ws_wk.cell(row=r_idx, column=4, value=wk.project_name).border = thin_border
            ws_wk.cell(row=r_idx, column=5, value=wk.work_details).border = thin_border
            ws_wk.cell(row=r_idx, column=6, value=wk.status).border = thin_border
            ws_wk.cell(row=r_idx, column=7, value="Yes (Off-Site)" if wk.is_offsite else "No").border = thin_border
            ws_wk.cell(row=r_idx, column=8, value=wk.location_notes or '-').border = thin_border
            ws_wk.cell(row=r_idx, column=9, value="Yes" if bool(wk.work_image) else "No").border = thin_border

        for col in ws_wk.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            ws_wk.column_dimensions[col_letter].width = max(max_len + 3, 12)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        filename = f"NETCOM_HR_Complete_Report_{from_d.strftime('%Y%m%d')}_to_{to_d.strftime('%Y%m%d')}.xlsx"
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    # 2. PDF EXPORT (.pdf)
    else:
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=landscape(letter),
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        primary_color = colors.HexColor("#1e3a8a")
        secondary_color = colors.HexColor("#16a34a")
        dark_text = colors.HexColor("#0f172a")
        border_color = colors.HexColor("#cbd5e1")
        gray_bg = colors.HexColor("#f8fafc")

        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=16,
            leading=19,
            textColor=primary_color,
            spaceAfter=2
        )

        subtitle_style = ParagraphStyle(
            'ReportSubTitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#475569"),
            spaceAfter=6
        )

        h1_style = ParagraphStyle(
            'SecH1',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=11,
            leading=14,
            textColor=primary_color,
            spaceBefore=8,
            spaceAfter=4,
            keepWithNext=True
        )

        th_style = ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7.5, leading=9.5, textColor=colors.white)
        td_style = ParagraphStyle('TD', fontName='Helvetica', fontSize=7, leading=9, textColor=dark_text)
        td_bold = ParagraphStyle('TDB', fontName='Helvetica-Bold', fontSize=7, leading=9, textColor=dark_text)

        story = []

        # Header with Logo & Title
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'netcom_logo.png')
        if not os.path.exists(logo_path):
            logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png')

        header_cells = []
        if os.path.exists(logo_path):
            try:
                logo_img = RLImage(logo_path, width=1.1 * inch, height=0.65 * inch)
                header_cells.append(logo_img)
            except Exception:
                header_cells.append(Paragraph("<b>NETCOM</b>", title_style))
        else:
            header_cells.append(Paragraph("<b>NETCOM</b>", title_style))

        header_text = [
            Paragraph("NETCOM TECHNOLOGIES — HUMAN RESOURCES EXECUTIVE REPORT", title_style),
            Paragraph(
                f"<b>Selected Date Range:</b> {from_d.strftime('%B %d, %Y')} to {to_d.strftime('%B %d, %Y')} &nbsp;|&nbsp; "
                f"<b>Generated on:</b> {today.strftime('%B %d, %Y')} by <b>{request.user.username}</b> &nbsp;|&nbsp; "
                f"<b>Coverage:</b> Full Organization (Attendance, Leaves, Balances & Tasks)",
                subtitle_style
            )
        ]
        header_table = Table([[header_cells[0], header_text]], colWidths=[1.3 * inch, 9.2 * inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(header_table)
        story.append(HRFlowable(width="100%", thickness=1.5, color=primary_color, spaceBefore=4, spaceAfter=6))

        # KPI Metrics Table
        kpi_row = [
            [
                Paragraph("<b>Total Workforce:</b>", td_bold), Paragraph(str(total_staff), td_style),
                Paragraph("<b>Punches Logged:</b>", td_bold), Paragraph(str(total_punches), td_style),
                Paragraph("<b>Full Days (>=9h):</b>", td_bold), Paragraph(str(total_presents), td_style),
                Paragraph("<b>Half Days (>=4.5h):</b>", td_bold), Paragraph(str(total_half_days), td_style),
            ],
            [
                Paragraph("<b>Permissions (2h):</b>", td_bold), Paragraph(str(total_permissions), td_style),
                Paragraph("<b>Approved Leaves:</b>", td_bold), Paragraph(str(total_approved_leaves), td_style),
                Paragraph("<b>Daily Tasks Logged:</b>", td_bold), Paragraph(str(total_work_logs), td_style),
                Paragraph("<b>Report Status:</b>", td_bold), Paragraph("Verified Complete", td_style),
            ]
        ]
        kpi_table = Table(kpi_row, colWidths=[1.4 * inch, 1.2 * inch, 1.4 * inch, 1.2 * inch, 1.4 * inch, 1.2 * inch, 1.4 * inch, 1.3 * inch])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), gray_bg),
            ('BOX', (0, 0), (-1, -1), 0.5, border_color),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, border_color),
            ('PADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 4))

        # Section 1: Employee Directory & Leave Balances
        story.append(Paragraph("1. Employee Directory & Casual Leave Balances", h1_style))
        emp_table_data = [[
            Paragraph("Code", th_style),
            Paragraph("Employee Name", th_style),
            Paragraph("Department", th_style),
            Paragraph("Role", th_style),
            Paragraph("Email", th_style),
            Paragraph("Phone", th_style),
            Paragraph("Casual Leave Balance", th_style),
            Paragraph("Status", th_style),
        ]]
        for emp in employees[:60]:
            emp_table_data.append([
                Paragraph(emp.employee_code, td_bold),
                Paragraph(emp.display_name(), td_style),
                Paragraph(emp.department.name if emp.department else 'Unassigned', td_style),
                Paragraph(emp.get_role_display(), td_style),
                Paragraph(emp.email or '-', td_style),
                Paragraph(emp.phone or '-', td_style),
                Paragraph(f"<b>{emp.casual_leave_balance} Days</b>", td_style),
                Paragraph("Active" if emp.is_active_employee else "Inactive", td_style),
            ])
        emp_t = Table(emp_table_data, colWidths=[1.1 * inch, 1.8 * inch, 1.5 * inch, 1.1 * inch, 2.0 * inch, 1.2 * inch, 1.1 * inch, 0.7 * inch])
        emp_t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), primary_color),
            ('GRID', (0, 0), (-1, -1), 0.5, border_color),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, gray_bg]),
            ('PADDING', (0, 0), (-1, -1), 2.5),
        ]))
        story.append(emp_t)
        story.append(Spacer(1, 6))

        # PageBreak for Attendance Records
        story.append(PageBreak())

        # Section 2: Attendance Records
        story.append(Paragraph(f"2. Attendance Records ({from_d.strftime('%b %d')} to {to_d.strftime('%b %d, %Y')})", h1_style))
        att_table_data = [[
            Paragraph("Date", th_style),
            Paragraph("Staff Code", th_style),
            Paragraph("Employee Name", th_style),
            Paragraph("Department", th_style),
            Paragraph("Punch In", th_style),
            Paragraph("Punch Out", th_style),
            Paragraph("Duration", th_style),
            Paragraph("Status", th_style),
            Paragraph("Source / Notes", th_style),
        ]]
        for att in attendances[:100]:
            status_text = att.status
            if att.is_permission:
                status_text = "Permission – 2 Hours"
            att_table_data.append([
                Paragraph(str(att.date), td_style),
                Paragraph(att.employee.employee_code, td_bold),
                Paragraph(att.employee.display_name(), td_style),
                Paragraph(att.employee.department.name if att.employee.department else '-', td_style),
                Paragraph(str(att.in_time)[:5] if att.in_time else '--:--', td_style),
                Paragraph(str(att.out_time)[:5] if att.out_time else '--:--', td_style),
                Paragraph(att.total_work_time, td_style),
                Paragraph(status_text, td_bold),
                Paragraph(att.update_source or 'System', td_style),
            ])
        att_t = Table(att_table_data, colWidths=[1.0 * inch, 1.1 * inch, 1.8 * inch, 1.5 * inch, 0.9 * inch, 0.9 * inch, 1.1 * inch, 1.3 * inch, 0.9 * inch])
        att_t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), primary_color),
            ('GRID', (0, 0), (-1, -1), 0.5, border_color),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, gray_bg]),
            ('PADDING', (0, 0), (-1, -1), 2.5),
        ]))
        story.append(att_t)
        story.append(Spacer(1, 6))

        # Section 3: Leave Requests & Approvals
        story.append(Paragraph(f"3. Leave Requests & Classifications ({leaves.count()} records)", h1_style))
        lv_table_data = [[
            Paragraph("Staff", th_style),
            Paragraph("Type", th_style),
            Paragraph("Duration", th_style),
            Paragraph("Days", th_style),
            Paragraph("Status", th_style),
            Paragraph("Classification", th_style),
            Paragraph("Reason / Justification", th_style),
            Paragraph("Reviewer", th_style),
        ]]
        for lv in leaves[:50]:
            lv_table_data.append([
                Paragraph(f"<b>{lv.employee.employee_code}</b> - {lv.employee.display_name()}", td_style),
                Paragraph(lv.leave_type, td_bold),
                Paragraph(f"{lv.from_date.strftime('%b %d')} - {lv.to_date.strftime('%b %d')}", td_style),
                Paragraph(f"{lv.total_days}d", td_bold),
                Paragraph(lv.status, td_bold),
                Paragraph(lv.approval_type or ('Paid' if lv.is_paid else 'Unpaid'), td_style),
                Paragraph((lv.reason[:45] + '...') if len(lv.reason) > 45 else lv.reason, td_style),
                Paragraph(lv.reviewed_by.username if lv.reviewed_by else '-', td_style),
            ])
        if leaves.count() == 0:
            lv_table_data.append([Paragraph("No leave applications within selected date range.", td_style)] + [Paragraph("", td_style)] * 7)

        lv_t = Table(lv_table_data, colWidths=[2.0 * inch, 1.2 * inch, 1.4 * inch, 0.7 * inch, 1.0 * inch, 1.2 * inch, 2.1 * inch, 0.9 * inch])
        lv_t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), primary_color),
            ('GRID', (0, 0), (-1, -1), 0.5, border_color),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, gray_bg]),
            ('PADDING', (0, 0), (-1, -1), 2.5),
        ]))
        story.append(lv_t)
        story.append(Spacer(1, 6))

        # Section 4: Daily Work Accomplishments
        if daily_works.exists():
            story.append(Paragraph(f"4. Daily Work Updates ({daily_works.count()} records)", h1_style))
            wk_table_data = [[
                Paragraph("Date", th_style),
                Paragraph("Staff", th_style),
                Paragraph("Project", th_style),
                Paragraph("Work Accomplishments", th_style),
                Paragraph("Off-Site", th_style),
                Paragraph("Status", th_style),
            ]]
            for wk in daily_works[:40]:
                wk_table_data.append([
                    Paragraph(str(wk.date), td_style),
                    Paragraph(f"<b>{wk.employee.employee_code}</b> {wk.employee.display_name()}", td_style),
                    Paragraph(wk.project_name, td_bold),
                    Paragraph((wk.work_details[:60] + '...') if len(wk.work_details) > 60 else wk.work_details, td_style),
                    Paragraph("Yes" if wk.is_offsite else "No", td_style),
                    Paragraph(wk.status, td_style),
                ])
            wk_t = Table(wk_table_data, colWidths=[1.0 * inch, 2.0 * inch, 1.6 * inch, 3.9 * inch, 0.9 * inch, 1.1 * inch])
            wk_t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), primary_color),
                ('GRID', (0, 0), (-1, -1), 0.5, border_color),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, gray_bg]),
                ('PADDING', (0, 0), (-1, -1), 2.5),
            ]))
            story.append(wk_t)

        doc.build(story, canvasmaker=NumberedLandscapeCanvas)
        pdf_buffer.seek(0)

        filename = f"NETCOM_HR_Complete_Report_{from_d.strftime('%Y%m%d')}_to_{to_d.strftime('%Y%m%d')}.pdf"
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
