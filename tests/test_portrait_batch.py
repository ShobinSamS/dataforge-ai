import io
import stat
import zipfile

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.main import create_app
from backend.app import portraits


def photo(color="red",format="PNG"):
    buffer=io.BytesIO()
    Image.new("RGB",(60,80),color).save(buffer,format=format)
    return buffer.getvalue()


def zipped(entries):
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,"w",compression=zipfile.ZIP_DEFLATED) as archive:
        for name,content in entries: archive.writestr(name,content)
    return buffer.getvalue()


def test_batch_api_zip_and_images_preserves_single_upload_and_metadata(tmp_path):
    app=create_app(f"sqlite:///{tmp_path/'db.sqlite'}",tmp_path,start_worker=False)
    with TestClient(app) as client:
        original=client.post("/api/portraits",files={"file":("one.png",photo(),"image/png")},data={"rights_confirmed":"true"})
        assert original.status_code==201
        original=original.json()
        archive=zipped([("folder/a.png",photo("green")),("folder/b.jpg",photo("blue","JPEG")),("__MACOSX/._a.png",b"metadata")])
        files=[("files",("photos.zip",archive,"application/zip")),("files",("extra.webp",photo("yellow","WEBP"),"image/webp"))]
        assert client.post("/api/portraits/batch",files=files).status_code==422
        assert len(list((tmp_path/"portraits").iterdir()))==1
        result=client.post("/api/portraits/batch",files=files,data={"rights_confirmed":"true","license_note":"Approved fictional assets","attribution":"Test source","max_count":"19"})
        assert result.status_code==201,result.text
        assert result.json()["count"]==3
        for record in result.json()["portraits"]:
            assert record["license_note"]=="Approved fictional assets" and record["attribution"]=="Test source"
            assert portraits.portrait_metadata(tmp_path,record["id"])==record
            response=client.get(record["preview_url"])
            assert response.status_code==200
            with Image.open(io.BytesIO(response.content)) as image:
                assert image.mode=="RGB" and image.size==(60,80)
        assert client.get(original["preview_url"]).status_code==200
        caps=client.get("/api/portraits/capabilities").json()
        assert caps["zip_upload"] and caps["batch_upload"]


@pytest.mark.parametrize("entries,limit,reason",[
    ([("a.png",photo()),("b.png",photo())],1,"remaining image slots"),
    ([("a.png",photo()),("b.png",b"broken")],20,"invalid image"),
    ([("../a.png",photo())],20,"unsafe path"),
    ([("C:/a.png",photo())],20,"unsafe path"),
    ([("/a.png",photo())],20,"unsafe path"),
    ([("a.txt",b"not an image")],20,"PNG, JPEG and WebP"),
    ([("a.png",b"0"*(8*1024**2+1))],20,"exceeds 8 MB"),
    ([],20,"No supported images"),
    ([(f"folder{i}/",b"") for i in range(101)],20,"100 entries"),
])
def test_invalid_archives_are_atomic(tmp_path,entries,limit,reason):
    with pytest.raises(ValueError,match=reason):
        portraits.save_portrait_batch([("photos.zip",zipped(entries))],tmp_path,max_count=limit,license_note="test")
    assert not (tmp_path/"portraits").exists()


def test_symlinks_corrupt_archives_and_expansion_limit(tmp_path,monkeypatch):
    symlink=zipfile.ZipInfo("linked.png")
    symlink.create_system=3;symlink.external_attr=(stat.S_IFLNK|0o777)<<16
    for payload,reason in [(zipped([(symlink,b"target")]),"symbolic link"),(b"broken zip","Cannot read ZIP")]:
        with pytest.raises(ValueError,match=reason):
            portraits.save_portrait_batch([("photos.zip",payload)],tmp_path,license_note="test")
    # Archive bytes fit, but its declared expanded image bytes exceed the limit.
    payload=zipped([("large.png",b"a"*5000)])
    monkeypatch.setattr(portraits,"MAX_BATCH_BYTES",1000)
    with pytest.raises(ValueError,match="Uncompressed images exceed"):
        portraits.save_portrait_batch([("photos.zip",payload)],tmp_path,license_note="test")
    assert not (tmp_path/"portraits").exists()


def test_failed_write_rolls_back_new_assets_only(tmp_path,monkeypatch):
    saved=portraits.save_portrait(photo(),tmp_path,source="user_uploaded",license_note="existing")
    payload=photo()
    original=Image.Image.save;calls=[]
    def fail_second(image,path,*args,**kwargs):
        calls.append(path)
        if len(calls)==2: raise OSError("Disk full")
        return original(image,path,*args,**kwargs)
    monkeypatch.setattr(Image.Image,"save",fail_second)
    with pytest.raises(OSError,match="Disk full"):
        portraits.save_portrait_batch([("a.png",payload),("b.png",payload)],tmp_path,license_note="test")
    assert [p.name for p in (tmp_path/"portraits").iterdir()]==[saved["id"]]
    assert portraits.portrait_metadata(tmp_path,saved["id"])==saved
