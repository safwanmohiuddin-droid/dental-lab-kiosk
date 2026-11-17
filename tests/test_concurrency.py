import threading
import time

import pytest
from django.db import connection

from inventory import services
from inventory.management.commands.check_ledger import drifted_materials
from inventory.models import StockMove
from inventory.services import InsufficientStock


@pytest.mark.django_db(transaction=True)  # threads need committed data and their own connections
def test_two_people_take_the_last_unit_at_once(material, employee, monkeypatch):
    services.receive(material, 1)

    # Hold each request between "check stock" and "save" so the two always overlap.
    original_save = StockMove.save

    def slow_save(self, *args, **kwargs):
        time.sleep(0.05)
        original_save(self, *args, **kwargs)

    monkeypatch.setattr(StockMove, "save", slow_save)

    start = threading.Barrier(2)
    results = []

    def take_one():
        try:
            start.wait()
            services.issue(material, 1, employee)
            results.append("ok")
        except InsufficientStock:
            results.append("refused")
        finally:
            connection.close()

    threads = [threading.Thread(target=take_one) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    material.refresh_from_db()
    assert sorted(results) == ["ok", "refused"]
    assert material.qty_on_hand == 0
    assert not drifted_materials().exists()
