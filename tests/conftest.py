import pytest

from inventory.models import Department, Employee, Material, StockMove


@pytest.fixture
def department(db):
    return Department.objects.create(name="CAD/CAM")


@pytest.fixture
def employee(department):
    return Employee.objects.create(name="Aisha Rahman", department=department)


@pytest.fixture
def material(db):
    return Material.objects.create(name="Zirconia disc", barcode="200000000011", unit="disc")


@pytest.fixture
def issue(material, employee, department):
    return StockMove.objects.create(
        kind="issue", material=material, qty=-2, employee=employee, department=department
    )
