import io

from PIL import Image

from tests.conftest import assign, new_customer


def _png(size=(40, 30)):
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 30, 30)).save(buf, format="PNG")
    return buf.getvalue()


def test_photo_upload_is_validated_recompressed_and_access_controlled(client, world, h):
    c = new_customer(client, h["a_manager"])
    assign(client, h["a_manager"], c["id"], world.a_sales1.id)
    r = client.post(f"/api/v1/customers/{c['id']}/photo", files={"file": ("../../evil.png", _png(), "image/png")}, headers=h["a_manager"])
    assert r.status_code == 200, r.text
    url = r.json()["business_photo_url"]
    assert url.startswith("/api/v1/files/customers/") and url.endswith(".jpg") and "evil" not in url  # server-generated name
    ok = client.get(url, headers=h["a_sales1"])
    assert ok.status_code == 200 and ok.headers["content-type"] == "image/jpeg"
    assert Image.open(io.BytesIO(ok.content)).format == "JPEG"
    assert client.get(url, headers=h["a_sales2"]).status_code == 404   # not assigned
    assert client.get(url, headers=h["b_admin"]).status_code == 404    # other company
    assert client.get(url).status_code == 401                          # anonymous


def test_non_image_and_oversized_uploads_rejected(client, world, h):
    c = new_customer(client, h["a_manager"])
    bad = client.post(f"/api/v1/customers/{c['id']}/photo", files={"file": ("shell.php", b"<?php echo 1; ?>", "image/jpeg")}, headers=h["a_manager"])
    assert bad.status_code == 400
    big = client.post(f"/api/v1/customers/{c['id']}/photo", files={"file": ("big.png", b"0" * (6 * 1024 * 1024), "image/png")}, headers=h["a_manager"])
    assert big.status_code == 400
    assert client.get(f"/api/v1/customers/{c['id']}", headers=h["a_manager"]).json()["business_photo_url"] is None


def test_missing_file_behind_db_reference_returns_404(client, world, h, db):
    c = new_customer(client, h["a_manager"])
    from app.models import Customer
    row = db.get(Customer, c["id"])
    row.business_photo_url = "/api/v1/files/customers/" + "a" * 32 + ".jpg"
    db.commit()
    assert client.get(row.business_photo_url, headers=h["a_manager"]).status_code == 404


def test_visit_photo_upload_by_recording_salesman_only(client, world, h):
    c = new_customer(client, h["a_manager"])
    assign(client, h["a_manager"], c["id"], world.a_sales1.id)
    v = client.post("/api/v1/visits", json={"customer_id": c["id"]}, headers=h["a_sales1"]).json()
    r = client.post(f"/api/v1/visits/{v['id']}/photo", files={"file": ("p.png", _png(), "image/png")}, headers=h["a_sales1"])
    assert r.status_code == 200 and r.json()["photo_url"].startswith("/api/v1/files/visits/")
    assert client.get(r.json()["photo_url"], headers=h["a_manager"]).status_code == 200
