from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventory import services
from inventory.models import Department, Employee, Material
from kiosk.models import Device

# Public demo credentials, documented in the README. Never valid outside DEBUG (see handle()).
DEMO_PASSWORD = "kiosk-demo"
DEMO_PIN = "1234"
OWNER = "owner"
TECHNICIAN = ("aisha", "Aisha Rahman")  # signs in on her own phone
DEMO_STOCK = 20

DEPARTMENTS = ["CAD/CAM", "Ceramics", "Model Room", "Orthodontics"]

EMPLOYEES = [
    ("Aisha Rahman", "CAD/CAM"),
    ("Daniel Okafor", "CAD/CAM"),
    ("Mei Lin", "CAD/CAM"),
    ("Carlos Mendes", "Ceramics"),
    ("Priya Nair", "Ceramics"),
    ("Yusuf Haddad", "Ceramics"),
    ("Elena Petrova", "Model Room"),
    ("Tom Becker", "Model Room"),
    ("Fatima Zahra", "Orthodontics"),
    ("Kenji Sato", "Orthodontics"),
]

# (name, barcode, unit, category). One barcode starts with 0 on purpose: Excel drops it (Phase 3).
MATERIALS = [
    ("Zirconia disc 98 x 14 mm", "200000000011", "disc", "Milling blanks"),
    ("Zirconia disc 98 x 18 mm", "200000000028", "disc", "Milling blanks"),
    ("Zirconia disc 98 x 22 mm", "200000000035", "disc", "Milling blanks"),
    ("Multilayer zirconia disc 98 x 18 mm", "200000000042", "disc", "Milling blanks"),
    ("PMMA disc 98 x 20 mm", "200000000059", "disc", "Milling blanks"),
    ("Milling wax disc 98 x 20 mm", "200000000066", "disc", "Milling blanks"),
    ("Lithium disilicate block", "200000000073", "pcs", "Milling blanks"),
    ("Milling bur 2.0 mm", "200000000080", "pcs", "Burs and tools"),
    ("Milling bur 1.0 mm", "200000000097", "pcs", "Burs and tools"),
    ("Milling bur 0.6 mm", "200000000103", "pcs", "Burs and tools"),
    ("Diamond polishing bur", "200000000110", "pcs", "Burs and tools"),
    ("Sintering beads", "200000000127", "g", "Furnace"),
    ("Layering ceramic powder A2", "200000000134", "g", "Ceramics"),
    ("Layering ceramic powder A3", "200000000141", "g", "Ceramics"),
    ("Opaque paste A2", "200000000158", "g", "Ceramics"),
    ("Glaze paste", "200000000165", "g", "Ceramics"),
    ("Stain set", "200000000172", "pcs", "Ceramics"),
    ("Modelling liquid", "200000000189", "ml", "Ceramics"),
    ("Die stone type IV", "200000000196", "kg", "Models"),
    ("Model stone type III", "200000000202", "kg", "Models"),
    ("Die hardener", "200000000219", "ml", "Models"),
    ("Separating liquid", "200000000226", "ml", "Models"),
    ("Model resin for 3D printing", "200000000233", "ml", "Models"),
    ("Isopropyl alcohol 99%", "200000000240", "ml", "Models"),
    ("Thermoforming sheet 0.75 mm", "200000000257", "pcs", "Orthodontics"),
    ("Thermoforming sheet 1.0 mm", "200000000264", "pcs", "Orthodontics"),
    ("Orthodontic wire 0.8 mm", "200000000271", "m", "Orthodontics"),
    ("Cold-cure acrylic powder", "200000000288", "g", "Orthodontics"),
    ("Cold-cure acrylic liquid", "200000000295", "ml", "Orthodontics"),
    ("Aluminium oxide 50 micron", "012345678905", "kg", "Finishing"),
]


class Command(BaseCommand):
    help = "Create demo data and demo logins (DEBUG only). Safe to run more than once."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "seed_demo creates logins with public passwords; it only runs with DEBUG=True."
            )

        departments = {name: Department.objects.get_or_create(name=name)[0] for name in DEPARTMENTS}
        for name, dept in EMPLOYEES:
            Employee.objects.get_or_create(name=name, defaults={"department": departments[dept]})
        Employee.objects.filter(pin_hash="").update(pin_hash=make_password(DEMO_PIN))

        for i, (name, barcode, unit, category) in enumerate(MATERIALS):
            material, _ = Material.objects.get_or_create(
                barcode=barcode, defaults={"name": name, "unit": unit, "category": category}
            )
            if not material.moves.exists():
                cost = None if i % 5 == 4 else Decimal(5 + 3 * i)  # some unpriced, like real labs
                services.receive(material, DEMO_STOCK, cost, note="Demo opening stock")

        User = get_user_model()
        owner, _ = User.objects.get_or_create(username=OWNER)
        owner.is_staff = owner.is_superuser = True
        owner.set_password(DEMO_PASSWORD)
        owner.save()

        username, employee_name = TECHNICIAN
        tech, _ = User.objects.get_or_create(username=username)
        tech.set_password(DEMO_PASSWORD)
        tech.save()
        employee = Employee.objects.get(name=employee_name)
        if employee.user_id in (None, tech.pk):
            employee.user = tech
            employee.save(update_fields=["user"])
        else:
            self.stderr.write(f"{employee_name} is linked to another login; left as it is.")

        device, _ = Device.objects.get_or_create(
            name="Demo tablet", defaults={"registered_by": owner}
        )
        token = device.new_link_token(owner)  # fresh one-time link every run
        device.save()

        self.stdout.write(
            f"Demo data: {Department.objects.count()} departments, "
            f"{Employee.objects.count()} employees, {Material.objects.count()} materials.\n"
            f"Owner (admin, reports):  {OWNER} / {DEMO_PASSWORD}\n"
            f"Technician on a phone:   {username} / {DEMO_PASSWORD}\n"
            f"Shared tablet PIN:       {DEMO_PIN} for every demo employee\n"
            f"Register this browser as the tablet (one time, 24 h): /k/register/{token}/"
        )
