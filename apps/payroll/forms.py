from django import forms
from datetime import date
from .models import SalaryStructure, PayrollRecord

class SalaryStructureForm(forms.ModelForm):
    class Meta:
        model = SalaryStructure
        fields = ['basic_salary', 'hra', 'allowances', 'pf_deduction', 'tax_deduction']
        widgets = {
            'basic_salary': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'hra': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'allowances': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'pf_deduction': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'tax_deduction': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
        }


class GeneratePayrollForm(forms.Form):
    current_year = date.today().year
    current_month = date.today().month

    year = forms.IntegerField(
        initial=current_year,
        widget=forms.NumberInput(attrs={'class': 'form-input'})
    )
    month = forms.ChoiceField(
        choices=[(i, f"{i:02d} - {date(2000, i, 1).strftime('%B')}") for i in range(1, 13)],
        initial=current_month,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
