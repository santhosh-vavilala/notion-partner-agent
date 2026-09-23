from app.models.schemas import ChatRequest

def test_request():
    r=ChatRequest(message="Find the architecture doc",thread_id="t1",user_id="u1")
    assert not r.approve_write
