from django import forms
from .models import LeaveRequest

class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'from_date', 'to_date', 'reason']
        widgets = {
            'leave_type': forms.Select(attrs={'class': 'form-select'}),
            'from_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'to_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'reason': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'State purpose of leave application...'}),
        }

    def clean(self):
        cleaned = super().clean()
        from_date = cleaned.get('from_date')
        to_date = cleaned.get('to_date')
        if from_date and to_date and to_date < from_date:
            raise forms.ValidationError("End date cannot be earlier than start date.")
        return cleaned
