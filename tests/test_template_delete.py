from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from backend.app.main import create_app
from backend.app.db import Template,TemplateVersion,Job,DeletedTemplate,Sample,Export


def seed(client,review=False):
    t=client.post("/api/templates/demo").json()
    if review:
        for r in t["regions"]:r["confirmed"]=True
        response=client.put(f"/api/templates/{t['id']}/review",json={"regions":t["regions"],"privacy_confirmed":True,"revision":1})
        assert response.status_code==200,response.text
        return response.json()
    return t


def test_delete_unused_template_and_review_source_only(tmp_path):
    app=create_app(f"sqlite:///{tmp_path/'test.db'}",tmp_path,start_worker=False)
    with TestClient(app) as client:
        t=seed(client,review=True);other=seed(client)
        source=tmp_path/"templates"/t["id"]/"page.png"
        assert source.is_file()
        assert client.delete(f"/api/templates/{t['id']}?revision=1").status_code==409
        assert source.is_file()
        response=client.delete(f"/api/templates/{t['id']}?revision={t['revision']}")
        assert response.status_code==200,response.text
        assert response.json()["source_removed"] and not response.json()["retained_for_jobs"]
        assert not source.exists()
        assert [v["id"] for v in client.get("/api/templates").json()]==[other["id"]]
        assert client.get(f"/api/templates/{t['id']}").status_code==404
        assert client.get(f"/api/templates/{t['id']}/image").status_code==404
        assert client.delete(f"/api/templates/{t['id']}?revision={t['revision']}").status_code==404
        assert (tmp_path/"templates"/other["id"]/"page.png").is_file()
        with app.state.sessions() as db:
            assert not db.get(Template,t["id"])
            assert not db.scalar(select(func.count()).select_from(TemplateVersion).where(TemplateVersion.template_id==t["id"]))


@pytest.mark.parametrize("status",["queued","running","paused","completed"])
def test_remove_used_template_preserves_job_history_and_blocks_new_use(tmp_path,status):
    url=f"sqlite:///{tmp_path/'test.db'}"
    app=create_app(url,tmp_path,start_worker=False)
    with TestClient(app) as client:
        t=seed(client,review=True)
        response=client.post("/api/jobs",json={"template_id":t["id"],"count":1})
        assert response.status_code==201,response.text
        job=response.json();source=tmp_path/"templates"/t["id"]/"page.png"
        with app.state.sessions.begin() as db:
            db.get(Job,job["id"]).status=status
            db.add(Sample(id="sample",job_id=job["id"],index=0,path=str(source),annotations=[],validation={"passed":True},sha256="test"))
            db.add(Export(id="export",job_id=job["id"],format="ocr",path=str(source)))
        response=client.delete(f"/api/templates/{t['id']}?revision={t['revision']}")
        assert response.status_code==200,response.text
        assert response.json()["retained_for_jobs"] and response.json()["job_count"]==1
        assert source.is_file() and client.get("/api/templates").json()==[]
        assert client.get(f"/api/jobs/{job['id']}").json()["status"]==status
        assert len(client.get(f"/api/jobs/{job['id']}/samples").json())==1
        assert client.get("/api/samples/sample/image").status_code==200
        assert client.get("/api/exports/export/download").status_code==200
        assert client.post("/api/jobs",json={"template_id":t["id"],"count":1}).status_code==404
        assert client.put(f"/api/templates/{t['id']}/review",json={"regions":t["regions"],"revision":t["revision"],"privacy_confirmed":True}).status_code==404
        assert client.post(f"/api/templates/{t['id']}/analyze-pii",json={}).status_code==404
        with app.state.sessions() as db:
            assert db.get(DeletedTemplate,t["id"]) and db.get(Template,t["id"])
    # Creating the new table is backward-compatible with an existing database;
    # library deletion stays effective after the app is reopened.
    reopened=create_app(url,tmp_path,start_worker=False)
    with TestClient(reopened) as client:assert client.get("/api/templates").json()==[]


def test_delete_never_removes_arbitrary_stored_path(tmp_path):
    app=create_app(f"sqlite:///{tmp_path/'test.db'}",tmp_path,start_worker=False)
    outside=tmp_path/"unrelated.png";outside.write_bytes(b"keep")
    with app.state.sessions.begin() as db:
        db.add(Template(id="fixture",name="Fixture",image_path=str(outside),width=10,height=10,regions=[]))
    with TestClient(app) as client:
        response=client.delete("/api/templates/fixture?revision=1")
        assert response.status_code==200
        assert response.json()["warnings"] and not response.json()["source_removed"]
        assert outside.read_bytes()==b"keep"
