import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

import main as app_module


def test_servers_index_route():
    client = app_module.app.test_client()
    response = client.get("/servers")
    assert response.status_code == 200


def test_server_detail_route():
    data = app_module.get_data("servers.json")
    if not data:
        return

    first_job_id = next(iter(data))
    client = app_module.app.test_client()
    response = client.get(f"/servers/{first_job_id}")
    assert response.status_code == 200
