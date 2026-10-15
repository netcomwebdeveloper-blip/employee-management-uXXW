from django import forms
from apps.employees.models import Employee
from .models import Attendance, DailyWork

class ManualAttendanceForm(forms.ModelForm):
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.select_related('user').filter(is_active_employee=True),
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Attendance
        fields = ['employee', 'date', 'in_time', 'out_time', 'status', 'leave_type', 'leave_reason']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'in_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-input'}),
            'out_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-input'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'leave_type': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Leave/Permission Type (e.g. Permission – 2 Hours)'}),
            'leave_reason': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Reason or approval notes...'}),
        }




class DailyWorkForm(forms.ModelForm):
    class Meta:
        model = DailyWork
        fields = ['project_name', 'work_details', 'status', 'is_offsite', 'location_notes', 'work_image']
        widgets = {
            'project_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Project or module name'}),
            'work_details': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Completed tasks and progress today...'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'is_offsite': forms.CheckboxInput(attrs={'class': 'form-checkbox', 'id': 'isOffsiteCheckbox'}),
            'location_notes': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Client Site, Branch Office, Field Visit'}),
            'work_image': forms.FileInput(attrs={'class': 'form-input', 'accept': 'image/*', 'id': 'workImageInput'}),
        }



class BiometricDeviceForm(forms.ModelForm):
    class Meta:
        from .models import BiometricDevice
        model = BiometricDevice
        fields = ['name', 'device_model', 'ip_address', 'port', 'protocol', 'communication_key', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Head Office Main Biometric'}),
            'device_model': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. ZKTeco K40 / iClock / Standalone'}),
            'ip_address': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '192.168.1.201'}),
            'port': forms.NumberInput(attrs={'class': 'form-input'}),
            'protocol': forms.Select(attrs={'class': 'form-select'}),
            'communication_key': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '0'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }


class DailyWorkPlanForm(forms.ModelForm):
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.select_related('user').filter(is_active_employee=True),
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        from .models import DailyWorkPlan
        model = DailyWorkPlan
        fields = ['employee', 'work_date', 'title', 'tasks', 'status']
        widgets = {
            'work_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Next-Day Client Deliverables / Operations'}),
            'tasks': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Enter detailed tasks, responsibilities, and expected deliverables for the employee...'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
