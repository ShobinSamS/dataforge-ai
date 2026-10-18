from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.db import Job


def test_interrupted_cancellation_recovers_as_paused(tmp_path):
    """A crash while cancellation is pending must not leave a job permanently stuck."""
    url=f"sqlite:///{tmp_path/'recovery.db'}"
    initial=create_app(url,tmp_path,start_worker=False)
    with TestClient(initial) as client:
        template=client.post('/api/templates/demo').json()
        for region in template['regions']:
            region['confirmed']=True
        reviewed=client.put(f"/api/templates/{template['id']}/review",json={
            'regions':template['regions'],'privacy_confirmed':True,'revision':1})
        assert reviewed.status_code==200
        job=client.post('/api/jobs',json={'template_id':template['id'],'count':1}).json()
        with initial.state.sessions.begin() as db:
            db.get(Job,job['id']).status='cancelling'
    recovered=create_app(url,tmp_path,start_worker=True)
    with TestClient(recovered) as client:
        state=client.get(f"/api/jobs/{job['id']}").json()
        assert state['status']=='paused'
        assert 'interrupted' in state['error'].lower()
