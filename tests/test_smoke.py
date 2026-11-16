def test_admin_login_page_loads(client):
    response = client.get("/admin/login/")
    assert response.status_code == 200


def test_database_is_postgres(db):
    from django.db import connection

    assert connection.vendor == "postgresql"
