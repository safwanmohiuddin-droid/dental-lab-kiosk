from django.core.management.base import BaseCommand, CommandError
from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce

from inventory.models import Material


def drifted_materials():
    """Materials whose cached qty_on_hand differs from the sum of their moves (ADR 0004)."""
    ledger = Coalesce(Sum("moves__qty"), Value(0), output_field=DecimalField())
    return Material.objects.annotate(ledger_qty=ledger).exclude(qty_on_hand=F("ledger_qty"))


class Command(BaseCommand):
    help = "Verify every material's cached stock equals its ledger. Exits 1 on drift."

    def handle(self, *args, **options):
        bad = list(drifted_materials())
        for m in bad:
            self.stderr.write(f"{m.barcode} {m.name}: cached {m.qty_on_hand} ledger {m.ledger_qty}")
        if bad:
            raise CommandError(f"{len(bad)} material(s) drifted from the ledger.")
        self.stdout.write("Ledger OK: every cached balance matches its moves.")
