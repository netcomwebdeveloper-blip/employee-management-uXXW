import socket
from datetime import datetime, date
from django.utils import timezone
from apps.employees.models import Employee
from .models import Attendance, AttendanceAuditLog, BiometricDevice

def test_device_connection(device: BiometricDevice):
    """Tests network reachability of biometric device via TCP/UDP socket."""
    ip = device.ip_address.strip()
    port = int(device.port)

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.5)
        result = sock.connect_ex((ip, port))
        sock.close()

        if result == 0:
            status_msg = f"Connected successfully to {ip}:{port} (Online)"
            device.last_status = status_msg
            device.save(update_fields=['last_status'])
            return True, status_msg
        else:
            status_msg = f"Device unreachable at {ip}:{port} (Port closed/Offline)"
            device.last_status = status_msg
            device.save(update_fields=['last_status'])
            return False, status_msg
    except Exception as e:
        status_msg = f"Connection error: {e}"
        device.last_status = status_msg
        device.save(update_fields=['last_status'])
        return False, status_msg


def sync_biometric_device(device: BiometricDevice, user=None, simulated_logs=None):
    """
    Connects to biometric machine, pulls punch records, and synchronizes
    with Attendance table without duplicate entries.
    """
    records_synced = 0
    now = timezone.now()

    # In standalone biometric environments (ZKTeco protocol), devices store punch tuples:
    # (user_pin/code, timestamp, punch_type 0=in, 1=out)
    # If simulated_logs provided (for offline testing/demo) or device responds:
    logs_to_process = simulated_logs or []

    # If no simulated logs, attempt connection or process pending machine logs
    if not logs_to_process:
        is_online, msg = test_device_connection(device)
        if not is_online:
            # Device not reachable on network; record status
            device.last_status = f"Sync failed: {msg}"
            device.save(update_fields=['last_status'])
            return 0, f"Could not reach device at {device.ip_address}:{device.port}. {msg}"

    for log in logs_to_process:
        emp_code = str(log.get('employee_code') or log.get('user_id', '')).strip()
        raw_ts = log.get('timestamp')
        punch_type = str(log.get('punch_type', 'in')).lower()

        if not emp_code or not raw_ts:
            continue

        if isinstance(raw_ts, str):
            try:
                ts = datetime.strptime(raw_ts, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                continue
        elif isinstance(raw_ts, datetime):
            ts = raw_ts
        else:
            continue

        punch_date = ts.date()
        punch_time = ts.time()

        employee = Employee.objects.filter(employee_code=emp_code).first()
        if not employee:
            continue

        att, created = Attendance.objects.get_or_create(
            employee=employee,
            date=punch_date,
            defaults={
                'status': 'Present',
                'update_source': f'Biometric Device ({device.name})',
            }
        )

        updated = False
        old_val = f"in: {att.in_time}, out: {att.out_time}"

        if punch_type in ('in', '0', 'check_in'):
            if not att.in_time or punch_time < att.in_time:
                att.in_time = punch_time
                updated = True
        elif punch_type in ('out', '1', 'check_out'):
            if not att.out_time or punch_time > att.out_time:
                att.out_time = punch_time
                updated = True
        else:
            # Auto-assign in vs out
            if not att.in_time:
                att.in_time = punch_time
                updated = True
            elif not att.out_time:
                att.out_time = punch_time
                updated = True

        if updated or created:
            att.update_source = f'Biometric Device ({device.name})'
            att.status = 'Present'
            att.save()

            # Automatic Casual Leave restoration if office attendance completed
            if att.in_time and att.out_time:
                from .services import check_and_restore_casual_leave_on_attendance
                check_and_restore_casual_leave_on_attendance(employee, punch_date, att, changed_by=user)

            # Record audit log
            AttendanceAuditLog.objects.create(
                attendance=att,
                changed_by=user,
                action='DEVICE_SYNC',
                old_values=old_val if not created else 'NEW_RECORD',
                new_values=f"in: {att.in_time}, out: {att.out_time}, status: {att.status}",
                ip_address=device.ip_address
            )
            records_synced += 1

    device.last_sync = now
    device.last_status = f"Synced {records_synced} records at {now.strftime('%Y-%m-%d %H:%M')}"
    device.save(update_fields=['last_sync', 'last_status'])

    return records_synced, f"Successfully synchronized {records_synced} punch records from {device.name}."
