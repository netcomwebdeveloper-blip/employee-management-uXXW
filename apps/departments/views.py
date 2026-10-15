from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from apps.users.decorators import hr_or_admin_required
from .models import Department, Designation
from .forms import DepartmentForm, DesignationForm

@login_required
@hr_or_admin_required
def department_list(request):
    departments = Department.objects.prefetch_related('designations', 'employees').all()
    dept_form = DepartmentForm()
    desig_form = DesignationForm()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_department':
            dept_form = DepartmentForm(request.POST)
            if dept_form.is_valid():
                dept_form.save()
                messages.success(request, f"Department '{dept_form.cleaned_data['name']}' created successfully.")
                return redirect('departments:list')
            else:
                for err_list in dept_form.errors.values():
                    for err in err_list:
                        messages.error(request, err)
        elif action == 'add_designation':
            desig_form = DesignationForm(request.POST)
            if desig_form.is_valid():
                desig_form.save()
                messages.success(request, f"Designation '{desig_form.cleaned_data['title']}' created successfully.")
                return redirect('departments:list')
            else:
                for err_list in desig_form.errors.values():
                    for err in err_list:
                        messages.error(request, err)

    context = {
        'departments': departments,
        'dept_form': dept_form,
        'desig_form': desig_form,
        'total_departments': departments.count(),
        'total_designations': Designation.objects.count(),
    }
    return render(request, 'departments/department_list.html', context)

@login_required
@hr_or_admin_required
def department_update(request, pk):
    department = get_object_or_404(Department, pk=pk)
    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            form.save()
            messages.success(request, f"Department '{department.name}' updated successfully.")
            return redirect('departments:list')
    else:
        form = DepartmentForm(instance=department)
    return render(request, 'departments/department_form.html', {'form': form, 'department': department})

@login_required
@hr_or_admin_required
def department_delete(request, pk):
    department = get_object_or_404(Department, pk=pk)
    if department.employees.exists():
        messages.error(request, f"Cannot delete '{department.name}' because active employees are assigned to it.")
    else:
        name = department.name
        department.delete()
        messages.success(request, f"Department '{name}' removed successfully.")
    return redirect('departments:list')

@login_required
@hr_or_admin_required
def designation_delete(request, pk):
    designation = get_object_or_404(Designation, pk=pk)
    title = designation.title
    designation.delete()
    messages.success(request, f"Designation '{title}' removed successfully.")
    return redirect('departments:list')
