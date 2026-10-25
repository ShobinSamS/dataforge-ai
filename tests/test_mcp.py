import asyncio
import base64
import hashlib
import io
import json
import zipfile
import sys
from pathlib import Path

import httpx
import pytest
from PIL import Image

pytest.importorskip("mcp", reason="Optional MCP tests require requirements-mcp.txt")
from jsonschema import Draft202012Validator
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.memory import create_connected_server_and_client_session

from backend.app import ingest
from backend.app import document_analysis
from backend.app.local_llm import LocalLLM
from backend.app.main import create_app
from backend.mcp_server import Bridge, create_server, decode_upload

ROOT = Path(__file__).resolve().parents[1]


def decoded(result):
    assert not result.isError, result
    assert result.structuredContent is not None
    return result.structuredContent


def test_tool_catalog_schemas_resources_and_hints():
    async def run():
        server = create_server()
        async with create_connected_server_and_client_session(server) as session:
            tools = (await session.list_tools()).tools
            names = {t.name for t in tools}
            assert len(names) == len(tools) == 64
            assert {"generate_signature", "generate_stamp", "generate_seal", "generate_qr", "generate_barcode",
                    "upload_template", "detect_visual_regions", "analyze_pii", "create_text_dataset", "export_dataset", "create_blank_template", "preview_canvas", "generate_address", "list_address_countries"} <= names
            for tool in tools:
                Draft202012Validator.check_schema(tool.inputSchema)
                if tool.outputSchema: Draft202012Validator.check_schema(tool.outputSchema)
            lookup = {t.name: t for t in tools}
            assert lookup["delete_dataset"].annotations.destructiveHint
            assert lookup["save_template_review"].annotations.readOnlyHint is False
            assert lookup["get_template"].annotations.readOnlyHint
            resources = (await session.list_resources()).resources
            assert {str(r.uri) for r in resources} == {"dataforge://guide", "dataforge://schemas", "dataforge://templates"}
            guide = await session.read_resource("dataforge://guide")
            assert "read_export_chunk" in guide.contents[0].text
            schemas = json.loads((await session.read_resource("dataforge://schemas")).contents[0].text)
            assert "RuleOptions" in schemas and "TextConfig" in schemas
            bad = await session.call_tool("get_template", {"template_id": "../../other"})
            assert bad.isError
            bad = await session.call_tool("generate_signature", {"seed": -1})
            assert bad.isError
    asyncio.run(run())


def test_real_mcp_assets_upload_review_document_and_text_exports(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest, "ocr", lambda image: ([], "manual", []))
    monkeypatch.setattr(LocalLLM, "status", lambda self: {"installed": False, "model": "test-local"})
    app = create_app(f"sqlite:///{tmp_path/'mcp.db'}", tmp_path, start_worker=False)
    async def run():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as api:
                server = create_server(client=api)
                async with create_connected_server_and_client_session(server) as session:
                    async def call(name, arguments=None): return decoded(await session.call_tool(name, arguments or {}))
                    capabilities = await call("get_capabilities")
                    assert capabilities["system"]["capabilities"]["mcp"]
                    assert capabilities["text"]["llm"]["installed"] is False
                    countries=await call("list_address_countries")
                    assert any(c['code']=='IN' for c in countries['result'])
                    canvas=await call("create_blank_template",{"request":{"paper":"custom","unit":"px","width":400,"height":200,"orientation":"landscape","background":"transparent","starter":"signature"}})
                    preview=await session.call_tool("preview_canvas",{"template_id":canvas["id"],"request":{"regions":canvas["regions"]}})
                    assert not preview.isError and preview.content[0].type=="image"
                    picture=Image.open(io.BytesIO(base64.b64decode(preview.content[0].data)))
                    assert picture.mode=="RGBA" and picture.getpixel((0,0))[3]==0
                    for name, arguments in [
                        ("generate_signature", {"name": "Mira Dev", "options": {"signature_style": "interwoven"}}),
                        ("generate_stamp", {"caption": "HERITAGE HALL"}), ("generate_rubber_stamp", {"text": "APPROVED"}), ("generate_seal", {}),
                        ("generate_qr", {"payload": "TEST-1234"}), ("generate_barcode", {"payload": "TEST-1234"}),
                        ("generate_asset", {"request": {"kind": "text", "value": "/api/this-is-text"}}),
                        ("generate_address", {"options":{"address_country":"IN","address_format":"{street}\n{city}, {state}\n{country} {postal_code}"}}),
                    ]:
                        result = await session.call_tool(name, arguments)
                        content = decoded(result)
                        assert content["image_order"] == ["asset_png", "mask_png"]
                        images = [c for c in result.content if c.type == "image"]
                        assert len(images) == 2 and all(i.mimeType == "image/png" for i in images)
                        for image in images: assert Image.open(io.BytesIO(base64.b64decode(image.data))).format == "PNG"
                        if name == "generate_asset": assert content["metadata"]["value"] == "/api/this-is-text"
                    image = io.BytesIO(); Image.new("RGB", (180, 120), "white").save(image, format="PNG")
                    encoded = base64.b64encode(image.getvalue()).decode()
                    upload = await call("upload_template", {"file_name": "blank.png", "content_base64": encoded})
                    assert upload["revision"] == 1 and not upload["privacy_confirmed"]
                    picture = await session.call_tool("get_image", {"image_type": "template", "image_id": upload["id"]})
                    assert not picture.isError and picture.content[0].type == "image"
                    missing_rights = await session.call_tool("import_portrait", {"content_base64": encoded})
                    assert missing_rights.isError
                    portrait = await call("import_portrait", {"content_base64": encoded, "rights_confirmed": True})
                    assert portrait["preview_url"].startswith("http://127.0.0.1:8000/api/")
                    archive=io.BytesIO()
                    with zipfile.ZipFile(archive,"w") as zip_:
                        zip_.writestr("a.png",image.getvalue());zip_.writestr("b.png",image.getvalue())
                    uploads=[{"file_name":"photos.zip","content_base64":base64.b64encode(archive.getvalue()).decode()}]
                    assert (await session.call_tool("import_portrait_batch",{"uploads":uploads})).isError
                    batch=await call("import_portrait_batch",{"uploads":uploads,"rights_confirmed":True,"max_count":19})
                    assert batch["count"]==2 and all(p["preview_url"].startswith("http://127.0.0.1:8000/api/") for p in batch["portraits"])
                    assert (await call("detect_visual_regions", {"template_id": upload["id"]}))["candidates"] == []
                    assert (await call("get_template", {"template_id": upload["id"]}))["revision"] == 1
                    assert (await session.call_tool("delete_template", {"template_id": upload["id"], "revision": 1})).isError
                    await call("delete_template", {"template_id": upload["id"], "revision": 1, "confirm_delete": True})

                    demo = await call("create_demo_template")
                    assert (await call("list_templates"))["result"]
                    assert (await call("list_fonts"))["result"]
                    pii = await call("analyze_pii", {"template_id": demo["id"], "request": {"regions": demo["regions"], "engine": "regex"}})
                    assert pii["candidates"]
                    remove = {**demo["regions"][0], "rule": "remove this completely"}
                    assert (await call("interpret_rule", {"request": {"region": remove, "engine": "auto"}}))["region"]["action"] == "erase"
                    matching = next(r for r in demo["regions"] if r["text"] == "Alex Example")
                    assert (await call("match_font", {"template_id": demo["id"], "region": matching}))["match"]
                    monkeypatch.setattr(document_analysis, "qwen_json", lambda *a, **kw: document_analysis.TableLayout(cells=[
                        document_analysis.TableCell(source_id="c1", row=0, column=0)]))
                    table = await call("structure_table", {"source": {"cells": [{"id": "c1", "text": "Original", "row": 1, "column": 1}]}})
                    assert table["cells"][0] == {"id": "c1", "text": "Original", "row": 0, "column": 0}
                    config = {"template_id": demo["id"], "count": 2, "seed": 42,
                              "blur_probability": 0, "rotation_probability": 0}
                    assert (await session.call_tool("create_document_dataset", {"config": config})).isError
                    for r in demo["regions"]: r["confirmed"] = True
                    reviewed = await call("save_template_review", {"template_id": demo["id"], "review": {
                        "revision": 1, "regions": demo["regions"], "privacy_confirmed": True}})
                    assert reviewed["revision"] == 2
                    assert (await session.call_tool("save_template_review", {"template_id": demo["id"], "review": {
                        "revision": 1, "regions": demo["regions"], "privacy_confirmed": True}})).isError
                    await call("preflight_document_dataset", {"config": config})
                    job = await call("create_document_dataset", {"config": config})
                    await asyncio.to_thread(app.state.worker.run, job["id"])
                    assert (await call("get_job", {"job_id": job["id"]}))["status"] == "completed"
                    assert len((await call("get_samples", {"job_id": job["id"]}))["items"]) == 2
                    assert (await call("get_quality", {"job_id": job["id"]}))["accepted"] == 2
                    assert (await session.call_tool("export_dataset", {"job_id": job["id"], "format": "coco"})).isError
                    export = await call("export_dataset", {"job_id": job["id"], "format": "coco", "review_confirmed": True})
                    direct = (await api.get(export["download_url"].replace("http://127.0.0.1:8000", ""))).content
                    buffer = bytearray(); offset = 0
                    while True:
                        chunk = await call("read_export_chunk", {"export_id": export["id"], "offset": offset, "max_bytes": 32768})
                        raw = base64.b64decode(chunk["data_base64"])
                        assert hashlib.sha256(raw).hexdigest() == chunk["chunk_sha256"]
                        assert chunk["offset"] == offset
                        buffer.extend(raw); offset = chunk["next_offset"]
                        if chunk["eof"]: break
                    assert bytes(buffer) == direct and bytes(buffer).startswith(b"PK")

                    text = await call("create_text_dataset", {"config": {"count": 4, "task": "classification"}})
                    await asyncio.to_thread(app.state.worker.run_text, text["id"])
                    assert len((await call("get_samples", {"job_id": text["id"], "dataset": "text"}))["items"]) == 4
                    await call("validate_text_dataset", {"job_id": text["id"]})
                    assert (await call("get_text_manifest", {"job_id": text["id"]}))["version"] == text["id"]
                    for format_ in ("csv", "json", "jsonl"):
                        result = await call("export_dataset", {"job_id": text["id"], "dataset": "text", "format": format_, "review_confirmed": True})
                        chunk = await call("read_export_chunk", {"export_id": result["id"], "dataset": "text"})
                        assert base64.b64decode(chunk["data_base64"])
                    assert (await session.call_tool("export_dataset", {"job_id": text["id"], "dataset": "text", "format": "yolo", "review_confirmed": True})).isError
                    assert (await session.call_tool("delete_dataset", {"job_id": text["id"], "dataset": "text"})).isError
                    await call("delete_dataset", {"job_id": text["id"], "dataset": "text", "confirm_delete": True})
                    assert (await session.call_tool("get_job", {"job_id": text["id"], "dataset": "text"})).isError
                    queued = await call("create_text_dataset", {"config": {"count": 1}})
                    await call("cancel_job", {"job_id": queued["id"], "dataset": "text"})
                    resumed = await call("resume_job", {"job_id": queued["id"], "dataset": "text"})
                    assert resumed["status"] == "queued"
    asyncio.run(run())


def test_streamable_http_is_real_mcp_with_host_protection():
    async def run():
        server = create_server()
        app = server.streamable_http_app()
        def factory(**kwargs): return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), **kwargs)
        async with server.session_manager.run():
            async with factory() as http_client:
                async with streamable_http_client("http://127.0.0.1:8001/mcp", http_client=http_client) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        result = await session.initialize()
                        assert result.serverInfo.name == "DataForge AI"
                        assert len((await session.list_tools()).tools) == 64
            async with factory() as client:
                response = await client.post("http://untrusted.invalid:8001/mcp", json={})
                assert response.status_code == 421
    asyncio.run(run())


def test_stdio_from_unrelated_directory_has_clean_protocol(tmp_path):
    async def run():
        params = StdioServerParameters(command=sys.executable,
            args=["-X", "utf8", str(ROOT/"scripts/run_mcp.py")], cwd=str(tmp_path))
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                assert (await session.initialize()).serverInfo.name == "DataForge AI"
                assert len((await session.list_tools()).tools) == 64
                assert (await session.read_resource("dataforge://guide")).contents
    asyncio.run(run())


def test_bridge_bounds_api_failures_and_does_not_retry():
    for url in ("https://example.com", "http://127.0.0.1:8000/api", "http://localhost@evil.invalid", "file:///tmp"):
        with pytest.raises(ValueError): Bridge(url)
    for encoded in ("", "bad", "@@@@", "data:image/png;base64,YQ=="):
        with pytest.raises(ValueError): decode_upload(encoded)
    with pytest.raises(ValueError): decode_upload(base64.b64encode(b"abc").decode(), limit=2)
    async def run():
        calls = []
        def failed(request):
            calls.append(request)
            return httpx.Response(409, json={"detail": "Changed revision"})
        async with httpx.AsyncClient(transport=httpx.MockTransport(failed), base_url="http://localhost") as client:
            bridge = Bridge("http://localhost:8000", client)
            with pytest.raises(ValueError, match="409.*Changed revision"):
                await bridge.json("PUT", "/api/templates/id/review", {})
            assert len(calls) == 1
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"x"*30)), base_url="http://localhost") as client:
            with pytest.raises(ValueError, match="transfer limit"):
                await Bridge("http://localhost", client).request("GET", "/api/test", limit=10)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(302, headers={"location": "https://example.com"})), base_url="http://localhost") as client:
            with pytest.raises(ValueError, match="redirect"):
                await Bridge("http://localhost", client).request("GET", "/api/test")
    asyncio.run(run())
