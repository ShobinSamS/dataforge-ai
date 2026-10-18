from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.db import Template,Job,Sample,Export,TextJob,TextSample,TextExport,uid


def seed(app,root,text=False,status="completed"):
    id_,export_id,sample_id=uid(),uid(),uid()
    folder=root/("text" if text else "jobs")/id_;folder.mkdir(parents=True)
    sample_path=folder/("000000.json" if text else "image.png");sample_path.write_bytes(b"fixture")
    export_path=root/("text_exports" if text else "exports")/f"{export_id}.{'json' if text else 'zip'}"
    export_path.parent.mkdir(exist_ok=True);export_path.write_bytes(b"fixture export")
    with app.state.sessions.begin() as db:
        if text:
            db.add(TextJob(id=id_,name="Temporary dataset",status=status,config={},total=1))
        else:
            source=root/f"{id_}-source.png";source.write_bytes(b"keep source")
            db.add(Template(id=id_,name="Source",image_path=str(source),width=10,height=10,regions=[]));db.flush()
            db.add(Job(id=id_,template_id=id_,name="Temporary dataset",status=status,config={},template_snapshot={},total=1))
        db.flush()
        if text:db.add(TextSample(id=sample_id,job_id=id_,index=0,path=str(sample_path),summary={},validation={},sha256="fixture"))
        else:db.add(Sample(id=sample_id,job_id=id_,index=0,path=str(sample_path),annotations=[],validation={},sha256="fixture"))
        cls=TextExport if text else Export
        db.add(cls(id=export_id,job_id=id_,format="json" if text else "ocr",path=str(export_path)))
    return id_,folder,export_path,sample_id,export_id


@pytest.mark.parametrize("text",[False,True])
def test_delete_cleans_only_selected_dataset_and_exports(tmp_path,text):
    app=create_app(f"sqlite:///{tmp_path/'test.db'}",tmp_path,start_worker=False)
    target=seed(app,tmp_path,text);other=seed(app,tmp_path,text)
    id_,folder,export_path,sample_id,export_id=target
    prefix="/api/text" if text else "/api"
    with TestClient(app) as client:
        response=client.delete(f"{prefix}/jobs/{id_}")
        assert response.status_code==200,response.text
        assert response.json()["warnings"]==[]
        assert not folder.exists() and not export_path.exists()
        assert client.get(f"{prefix}/jobs/{id_}").status_code==404
        assert client.delete(f"{prefix}/jobs/{id_}").status_code==404
        assert other[1].exists() and other[2].exists()
        with app.state.sessions() as db:
            assert not db.get(TextSample if text else Sample,sample_id)
            assert not db.get(TextExport if text else Export,export_id)
            if not text:assert db.get(Template,id_) and (tmp_path/f"{id_}-source.png").exists()


@pytest.mark.parametrize("text",[False,True])
@pytest.mark.parametrize("status",["queued","running","cancelling"])
def test_active_datasets_cannot_be_deleted(tmp_path,text,status):
    app=create_app(f"sqlite:///{tmp_path/'test.db'}",tmp_path,start_worker=False)
    id_,folder,path,_,_=seed(app,tmp_path,text,status)
    # Do not enter lifespan: worker recovery would intentionally pause running jobs.
    client=TestClient(app)
    response=client.delete(f"/api{'/text' if text else ''}/jobs/{id_}")
    assert response.status_code==409
    assert folder.exists() and path.exists()


def test_delete_retains_export_with_unowned_path_and_reports_cleanup_failure(tmp_path,monkeypatch):
    app=create_app(f"sqlite:///{tmp_path/'test.db'}",tmp_path,start_worker=False)
    id_,folder,path,_,export_id=seed(app,tmp_path)
    outside=tmp_path/"unrelated.txt";outside.write_text("keep")
    with app.state.sessions.begin() as db:db.get(Export,export_id).path=str(outside)
    def fail(*args,**kwargs):raise PermissionError("locked")
    monkeypatch.setattr("backend.app.dataset_delete.shutil.rmtree",fail)
    with TestClient(app) as client:
        response=client.delete(f"/api/jobs/{id_}")
        assert response.status_code==200 and len(response.json()["warnings"])==2
        assert outside.read_text()=="keep" and folder.exists()
