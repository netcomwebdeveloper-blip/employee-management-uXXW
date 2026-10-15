from django import forms
from django.contrib.auth.models import User
from apps.departments.models import Department, Designation
from .models import Employee

class EmployeeCreateForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. john_doe'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Enter secure password'})
    )
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        max_length=150, required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Last Name'})
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'email@company.com'})
    )
    employee_code = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. EMP005'})
    )
    role = forms.ChoiceField(
        choices=Employee.ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(), required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    designation = forms.ModelChoiceField(
        queryset=Designation.objects.all(), required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    phone = forms.CharField(
        max_length=20, required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+91 9876543210'})
    )
    address = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Residential address...'}),
        required=False
    )
    basic_salary = forms.DecimalField(
        max_digits=12, decimal_places=2, initial=0.00,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'})
    )
    casual_leave_balance = forms.IntegerField(
        min_value=0, initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-input'})
    )
    profile_picture = forms.ImageField(required=False, widget=forms.FileInput(attrs={'class': 'form-input'}))
    document = forms.FileField(required=False, widget=forms.FileInput(attrs={'class': 'form-input'}))

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Username already exists. Please choose a different username.")
        return username

    def clean_employee_code(self):
        code = self.cleaned_data['employee_code'].strip().upper()
        if Employee.objects.filter(employee_code=code).exists():
            raise forms.ValidationError("Employee Code already registered.")
        return code

    def save(self):
        cd = self.cleaned_data
        is_admin = cd['role'] == 'ADMIN'
        user = User.objects.create_user(
            username=cd['username'],
            password=cd['password'],
            first_name=cd['first_name'],
            last_name=cd['last_name'],
            email=cd['email'],
            is_staff=is_admin,
            is_superuser=is_admin
        )
        employee = Employee.objects.create(
            user=user,
            employee_code=cd['employee_code'],
            role=cd['role'],
            department=cd['department'],
            designation=cd['designation'],
            phone=cd['phone'],
            address=cd['address'],
            basic_salary=cd['basic_salary'],
            casual_leave_balance=cd['casual_leave_balance'],
            profile_picture=cd['profile_picture'],
            document=cd['document'],
            raw_password=cd['password'],
        )
        return employee


class EmployeeUpdateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-input'}))
    last_name = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={'class': 'form-input'}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-input'}))
    new_password = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter new password to reset (or leave blank)'})
    )

    class Meta:
        model = Employee
        fields = [
            'role', 'department', 'designation', 'phone', 'address',
            'basic_salary', 'casual_leave_balance', 'is_active_employee',
            'profile_picture', 'document'
        ]
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'designation': forms.Select(attrs={'class': 'form-select'}),
            'phone': forms.TextInput(attrs={'class': 'form-input'}),
            'address': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
            'basic_salary': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'casual_leave_balance': forms.NumberInput(attrs={'class': 'form-input'}),
            'is_active_employee': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-input'}),
            'document': forms.FileInput(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
            if self.instance.raw_password:
                self.fields['new_password'].initial = self.instance.raw_password

    def save(self, commit=True):
        employee = super().save(commit=False)
        user = employee.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']

        new_pwd = self.cleaned_data.get('new_password', '').strip()
        if new_pwd:
            user.set_password(new_pwd)
            employee.raw_password = new_pwd

        if employee.role == 'ADMIN':
            user.is_staff = True
            user.is_superuser = True
        else:
            user.is_staff = False
            user.is_superuser = False
        user.save()
        if commit:
            employee.save()
        return employee
