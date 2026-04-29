import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import os

from app.main import app
from app.database import Base, get_db
from app.models import UrlMapping, ScanEvent
from app.url_validator import MAX_URL_LENGTH

# Test Database setup
from sqlalchemy.pool import StaticPool
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="function", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    # Clear the redirect cache in routes before each test
    from app.routes import redirect_cache
    redirect_cache.clear()
    yield
    Base.metadata.drop_all(bind=engine)

client = TestClient(app)

def test_create_qr_valid():
    response = client.post("/api/qr/create", json={"url": "https://valid.com"})
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert "short_url" in data
    assert "qr_code_url" in data
    assert data["original_url"] == "https://valid.com"

def test_create_qr_too_long():
    long_url = "https://a.com/" + "a" * 2048
    response = client.post("/api/qr/create", json={"url": long_url})
    assert response.status_code == 422

def test_create_qr_invalid_scheme():
    response = client.post("/api/qr/create", json={"url": "ftp://example.com"})
    assert response.status_code == 422

def test_create_qr_blocked_domain():
    response = client.post("/api/qr/create", json={"url": "https://evil.com"})
    assert response.status_code == 422

def test_redirect_active_and_scan_event(setup_db):
    res_create = client.post("/api/qr/create", json={"url": "https://example.com"})
    token = res_create.json()["token"]

    # Redirect 1st time
    res_redirect = client.get(f"/r/{token}", follow_redirects=False)
    assert res_redirect.status_code == 302
    assert res_redirect.headers["location"] == "https://example.com"
    
    # Check ScanEvent
    db = TestingSessionLocal()
    scan_count = db.query(ScanEvent).filter(ScanEvent.token == token).count()
    db.close()
    assert scan_count == 1

def test_redirect_soft_deleted():
    res_create = client.post("/api/qr/create", json={"url": "https://example.com"})
    token = res_create.json()["token"]
    
    # Delete
    res_del = client.delete(f"/api/qr/{token}")
    assert res_del.status_code == 200

    # Redirect
    res_redirect = client.get(f"/r/{token}", follow_redirects=False)
    assert res_redirect.status_code == 410

def test_redirect_expired():
    # create with expired time
    db = TestingSessionLocal()
    token = "expirTk"
    past_time = datetime.utcnow() - timedelta(seconds=1)
    mapping = UrlMapping(token=token, original_url="https://expired.com", expires_at=past_time)
    db.add(mapping)
    db.commit()
    db.close()

    res_redirect = client.get(f"/r/{token}", follow_redirects=False)
    assert res_redirect.status_code == 410

def test_redirect_never_existed():
    res_redirect = client.get("/r/notreal", follow_redirects=False)
    assert res_redirect.status_code == 404

def test_get_qr_info_active():
    res_create = client.post("/api/qr/create", json={"url": "https://example.com"})
    token = res_create.json()["token"]

    res_info = client.get(f"/api/qr/{token}")
    assert res_info.status_code == 200
    data = res_info.json()
    assert data["token"] == token
    assert data["original_url"] == "https://example.com"

def test_get_qr_info_soft_deleted():
    res_create = client.post("/api/qr/create", json={"url": "https://example.com"})
    token = res_create.json()["token"]
    client.delete(f"/api/qr/{token}")

    res_info = client.get(f"/api/qr/{token}")
    assert res_info.status_code == 404

def test_get_qr_info_never_existed():
    res_info = client.get("/api/qr/notreal")
    assert res_info.status_code == 404

def test_patch_update_url():
    res_create = client.post("/api/qr/create", json={"url": "https://example.com"})
    token = res_create.json()["token"]
    
    # Update URL
    res_patch = client.patch(f"/api/qr/{token}", json={"url": "https://new.com"})
    assert res_patch.status_code == 200

    # Redirect check
    res_redirect = client.get(f"/r/{token}", follow_redirects=False)
    assert res_redirect.status_code == 302
    assert res_redirect.headers["location"] == "https://new.com"

def test_patch_update_expires_at():
    res_create = client.post("/api/qr/create", json={"url": "https://example.com"})
    token = res_create.json()["token"]
    
    # Set expires_at in the past
    past_time = (datetime.utcnow() - timedelta(seconds=1)).isoformat()
    res_patch = client.patch(f"/api/qr/{token}", json={"expires_at": past_time})
    assert res_patch.status_code == 200

    # Redirect check -> should be 410
    res_redirect = client.get(f"/r/{token}", follow_redirects=False)
    assert res_redirect.status_code == 410

def test_patch_non_existent():
    res_patch = client.patch("/api/qr/notreal", json={"url": "https://new.com"})
    assert res_patch.status_code == 404

def test_delete_active():
    res_create = client.post("/api/qr/create", json={"url": "https://example.com"})
    token = res_create.json()["token"]
    
    res_del = client.delete(f"/api/qr/{token}")
    assert res_del.status_code == 200

    # Redirect check
    res_redirect = client.get(f"/r/{token}", follow_redirects=False)
    assert res_redirect.status_code == 410

def test_delete_non_existent():
    res_del = client.delete("/api/qr/notreal")
    assert res_del.status_code == 404

def test_get_qr_image_active():
    res_create = client.post("/api/qr/create", json={"url": "https://example.com"})
    token = res_create.json()["token"]

    res_img = client.get(f"/api/qr/{token}/image")
    assert res_img.status_code == 200
    assert res_img.headers["content-type"] == "image/png"

def test_get_qr_image_deleted_or_nonexistent():
    res_create = client.post("/api/qr/create", json={"url": "https://example.com"})
    token = res_create.json()["token"]
    client.delete(f"/api/qr/{token}")
    
    res_img = client.get(f"/api/qr/{token}/image")
    assert res_img.status_code == 404

    res_img2 = client.get("/api/qr/notreal/image")
    assert res_img2.status_code == 404

def test_get_analytics():
    res_create = client.post("/api/qr/create", json={"url": "https://example.com"})
    token = res_create.json()["token"]
    
    client.get(f"/r/{token}", follow_redirects=False)
    client.get(f"/r/{token}", follow_redirects=False)

    res_analytics = client.get(f"/api/qr/{token}/analytics")
    assert res_analytics.status_code == 200
    data = res_analytics.json()
    assert data["total_scans"] == 2
    assert "scans_by_day" in data

def test_get_analytics_non_existent():
    res = client.get("/api/qr/notreal/analytics")
    assert res.status_code == 404

def test_cache_invalidation_patch():
    res_create = client.post("/api/qr/create", json={"url": "https://example.com"})
    token = res_create.json()["token"]
    
    # Warm cache
    client.get(f"/r/{token}", follow_redirects=False)
    
    # Patch
    client.patch(f"/api/qr/{token}", json={"url": "https://new.com"})

    # Check redirect uses new URL (no stale cache)
    res_redirect = client.get(f"/r/{token}", follow_redirects=False)
    assert res_redirect.headers["location"] == "https://new.com"

def test_cache_invalidation_delete():
    res_create = client.post("/api/qr/create", json={"url": "https://example.com"})
    token = res_create.json()["token"]
    
    # Warm cache
    client.get(f"/r/{token}", follow_redirects=False)
    
    # Delete
    client.delete(f"/api/qr/{token}")

    # Check redirect is 410 (no stale cache)
    res_redirect = client.get(f"/r/{token}", follow_redirects=False)
    assert res_redirect.status_code == 410
