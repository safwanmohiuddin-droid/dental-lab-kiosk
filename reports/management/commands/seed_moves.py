import random
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.db.models import Sum

from inventory.models import Employee, Material, StockMove

SEED_NOTE = "seed_moves"


class Command(BaseCommand):
    help = (
        "Performance dataset: N issues spread over the last year, plus returns and covering "
        "receipts. Demo databases only. Keeps the ledger invariant (check_ledger passes)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=10_000)
        parser.add_argument("--seed", type=int, default=1)

    @transaction.atomic
    def handle(self, *args, count, seed, **options):
        # shortcut: bulk_create bypasses inventory.services for speed; the cached balances are
        # recomputed from the ledger below, so this must never run against a real lab's data.
        call_command("seed_demo")
        rng = random.Random(seed)
        employees = list(Employee.objects.filter(active=True))
        materials = list(Material.objects.filter(active=True))
        price = {m.pk: Decimal(rng.randint(100, 50_000)) / 100 for m in materials}

        def issue(_):
            e, m = rng.choice(employees), rng.choice(materials)
            return StockMove(
                kind=StockMove.Kind.ISSUE,
                material=m,
                qty=-rng.randint(1, 5),
                unit_cost=price[m.pk] if rng.random() < 0.8 else None,  # 80% priced (ADR 0005)
                employee=e,
                department_id=e.department_id,
                note=SEED_NOTE,
            )

        issues = StockMove.objects.bulk_create(map(issue, range(count)), batch_size=5000)
        returns = [
            StockMove(
                kind=StockMove.Kind.RETURN,
                material_id=i.material_id,
                qty=1,
                unit_cost=i.unit_cost,
                employee_id=i.employee_id,
                department_id=i.department_id,
                returns_move=i,
                note=SEED_NOTE,
            )
            for i in rng.sample(issues, count // 20)
        ]
        StockMove.objects.bulk_create(returns, batch_size=5000)

        # One receipt per material so stock never ends negative.
        net = dict(StockMove.objects.values_list("material_id").annotate(s=Sum("qty")).order_by())
        StockMove.objects.bulk_create(
            StockMove(
                kind=StockMove.Kind.RECEIPT,
                material=m,
                qty=-net.get(m.pk, 0) + 50,
                unit_cost=price[m.pk],
                note=SEED_NOTE,
            )
            for m in materials
        )

        with connection.cursor() as cur:
            # auto_now_add stamped everything "now"; spread seeded moves over the past year.
            cur.execute(
                "UPDATE inventory_stockmove "
                "SET created_at = now() - random() * interval '365 days' WHERE note = %s",
                [SEED_NOTE],
            )
            cur.execute(  # a return happens after its issue
                "UPDATE inventory_stockmove r SET created_at = i.created_at + interval '1 hour' "
                "FROM inventory_stockmove i WHERE r.returns_move_id = i.id AND r.note = %s",
                [SEED_NOTE],
            )
            cur.execute(
                "UPDATE inventory_material m SET qty_on_hand = COALESCE("
                "(SELECT SUM(qty) FROM inventory_stockmove s WHERE s.material_id = m.id), 0)"
            )
        for m in materials:
            Material.objects.filter(pk=m.pk).update(avg_cost=price[m.pk])
        total = StockMove.objects.filter(note=SEED_NOTE).count()
        self.stdout.write(f"Seeded {total} moves ({count} issues).")
