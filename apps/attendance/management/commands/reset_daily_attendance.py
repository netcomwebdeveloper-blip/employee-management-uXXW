from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.attendance.services import reset_daily_missed_punch_in_status

class Command(BaseCommand):
    help = "Evaluates and resets daily punch-in status at 12:00 PM local time for all active employees, HR, and admins."

    def handle(self, *args, **options):
        now = timezone.localtime()
        reset_daily_missed_punch_in_status()
        self.stdout.write(self.style.SUCCESS(
            f"Successfully executed daily punch-in evaluation & reset for {now.strftime('%Y-%m-%d %H:%M:%S')}."
        ))
