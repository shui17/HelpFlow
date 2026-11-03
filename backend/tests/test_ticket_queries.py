from app.models import Activity, Comment
from tests.test_database import database_url
from tests.test_security import client, db_run
from tests.test_ticket_workflow import identities, create


def test_server_filters_and_summary_preserve_role_visibility(client, database_url):
    (owner, h), (_, other), (agent, ah), (agent2, bh), (_, adm) = identities(client, database_url)
    first, second = create(client, h), create(client, h)
    foreign = create(client, other)
    assert client.post(first + "/claim", headers=ah).status_code == 200
    assert client.post(first + "/status", headers=ah, json={"status": "in_progress"}).status_code == 200
    assert client.post(foreign + "/claim", headers=bh).status_code == 200
    first_id, second_id = int(first.rsplit("/", 1)[1]), int(second.rsplit("/", 1)[1])
    mine = client.get("/api/v1/tickets", headers=ah, params={"scope": "mine", "page_size": 1}).json()["data"]
    assert mine["total"] == 1 and mine["items"][0]["id"] == first_id
    pending = client.get("/api/v1/tickets", headers=h, params={"scope": "unassigned"}).json()["data"]
    assert pending["total"] == 1 and pending["items"][0]["id"] == second_id
    forbidden_filter = client.get("/api/v1/tickets", headers=h, params={"assignee_id": agent2}).json()["data"]
    assert forbidden_filter["total"] == 0
    assigned = client.get("/api/v1/tickets", headers=adm, params={"assignee_id": agent}).json()["data"]
    assert assigned["total"] == 1 and assigned["items"][0]["id"] == first_id
    summary = client.get("/api/v1/tickets/summary", headers=h)
    assert summary.status_code == 200, summary.text
    data = summary.json()["data"]
    assert data["counts"]["open"] == 1 and data["counts"]["in_progress"] == 1
    assert {row["id"] for row in data["recent"]} == {first_id, second_id}
    agent_summary = client.get("/api/v1/tickets/summary", headers=ah).json()["data"]
    assert agent_summary["counts"]["open"] == 0 and agent_summary["counts"]["in_progress"] == 1
    assert [row["id"] for row in agent_summary["recent"]] == [first_id]
    assert client.get("/api/v1/tickets/summary").status_code == 401


def test_record_cursors_are_bounded_stable_and_authorized(client, database_url):
    (owner, h), (_, other), *_ = identities(client, database_url)
    path = create(client, h)
    ticket_id = int(path.rsplit("/", 1)[1])
    async def seed(session):
        for i in range(105):
            session.add(Comment(ticket_id=ticket_id, author_id=owner, content=f"reply-{i}"))
            session.add(Activity(ticket_id=ticket_id, operator_id=owner, action="updated"))
    db_run(database_url, seed)
    for name, expected in [("comments", 105), ("activities", 106)]:
        response = client.get(path + "/" + name, headers=h)
        assert response.status_code == 200, response.text
        rows = response.json()["data"]
        assert len(rows) == 50
        assert client.get(path + "/" + name, headers=other).status_code == 403
        assert client.get(path + "/" + name, headers=h, params={"limit": 101}).status_code == 422
        # 新记录插入不会移动基于 ID 的旧记录游标。
        if name == "comments":
            assert client.post(path + "/comments", headers=h, json={"content": "new reply"}).status_code == 201
        while True:
            older = client.get(path + "/" + name, headers=h, params={"before_id": rows[0]["id"]}).json()["data"]
            if not older:
                break
            rows = older + rows
        ids = [row["id"] for row in rows]
        assert len(ids) == len(set(ids)) == expected
        assert ids == sorted(ids)
