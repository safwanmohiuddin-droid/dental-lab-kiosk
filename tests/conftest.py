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


@pytest.fixture(autouse=True)
def _plain_http_admin(settings):
    # CI runs with DEBUG off (production defaults). The test client speaks plain HTTP and
    # admin_client has no authenticator; tests/test_deploy.py turns both back on (ADR 0026).
    settings.SECURE_SSL_REDIRECT = False
    settings.ADMIN_REQUIRE_2FA = False
