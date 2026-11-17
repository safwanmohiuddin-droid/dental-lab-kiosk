from django.core.management.base import BaseCommand
from django.db import transaction

from inventory.models import Department, Employee, Material

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
    help = "Create demo departments, employees and materials. Safe to run more than once."

    @transaction.atomic
    def handle(self, *args, **options):
        departments = {name: Department.objects.get_or_create(name=name)[0] for name in DEPARTMENTS}
        for name, dept in EMPLOYEES:
            Employee.objects.get_or_create(name=name, defaults={"department": departments[dept]})
        for name, barcode, unit, category in MATERIALS:
            Material.objects.get_or_create(
                barcode=barcode, defaults={"name": name, "unit": unit, "category": category}
            )
        self.stdout.write(
            f"Demo data: {Department.objects.count()} departments, "
            f"{Employee.objects.count()} employees, {Material.objects.count()} materials."
        )
