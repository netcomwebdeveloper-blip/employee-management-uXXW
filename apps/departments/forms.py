from django import forms
from .models import Department, Designation

class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'code', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Information Technology'}),
            'code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. IT'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Optional department description...'}),
        }

class DesignationForm(forms.ModelForm):
    class Meta:
        model = Designation
        fields = ['department', 'title', 'description']
        widgets = {
            'department': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Senior Software Engineer'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Role responsibilities...'}),
        }
