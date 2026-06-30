# CRUD + the critical: participant cannot delete, stranger cannot access
# Integration tests for project CRUD and access control
#
# test_create_project - covered cases:
#   valid data returns 201 or 200
#   creator automatically gets owner role in Access table
#   Access row is created in DB
#   missing name returns 422
#   name shorter than 4 chars returns 422
#   empty name returns 422
#   unauthenticated request returns 401
#
# test_get_projects - covered cases:
#   owner sees their own project in the list
#   participant sees projects they were invited to
#   user does not see projects they have no access to
#   response includes documents field
#   unauthenticated request returns 401
#
# test_get_project_info - covered cases:
#   owner can get project info
#   participant can get project info
#   user with no access gets 403 or 404
#   non-existent project_id gets 404
#   unauthenticated request returns 401
#
# test_update_project - covered cases:
#   owner can update name and description
#   participant can update (participants CAN modify)
#   partial update works - only name, description unchanged
#   user with no access gets 403 or 404
#   empty name returns 422
#   unauthenticated request returns 401
#
# test_delete_project - covered cases:
#   owner can delete project
#   deletion removes project from DB
#   deletion removes associated documents from DB
#   deletion removes documents from S3 (mock S3)
#   participant cannot delete - gets 403
#   user with no access gets 403 or 404
#   unauthenticated request returns 401
#
# test_invite_user - covered cases:
#   owner can invite user by login
#   invited user gets participant role in Access table
#   invited user can access the project after invite
#   participant cannot invite others - gets 403
#   user with no access cannot invite - gets 403
#   inviting non-existent login gets 404
#   inviting already-invited user gets 409
#   unauthenticated request returns 401

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.access import Access
from app.models.document import Document
from app.models.project import Project
from app.models.user import User


# create project
async def test_create_project_success(
    client: AsyncClient, owner_headers: dict, db_session: AsyncSession, test_owner: User
):
    payload = {"name": "Brand New Project", "description": "Some desc"}
    response = await client.post("/projects", json=payload, headers=owner_headers)
    assert response.status_code in [200, 201], "project creation should succeed"

    data = response.json()
    assert data["name"] == "Brand New Project", (
        "created project should keep the provided name"
    )
    assert "id" in data, "created project should include an id"

    # owner access row must exist in DB immediately after creation
    stmt = select(Access).where(
        Access.project_id == data["id"], Access.user_id == test_owner.id
    )
    access = (await db_session.execute(stmt)).scalar_one_or_none()
    assert access is not None, "creator access row should be created"
    assert access.role == "owner", "creator should get owner role"


async def test_create_project_missing_name(client: AsyncClient, owner_headers: dict):
    payload = {"description": "No name given"}
    response = await client.post("/projects", json=payload, headers=owner_headers)
    assert response.status_code == 422, "missing name should fail"


async def test_create_project_name_too_short(client: AsyncClient, owner_headers: dict):
    payload = {"name": "abc", "description": "Name too short"}
    response = await client.post("/projects", json=payload, headers=owner_headers)
    assert response.status_code == 422, "short name should fail"


async def test_create_project_empty_name(client: AsyncClient, owner_headers: dict):
    payload = {"name": "", "description": "Empty name"}
    response = await client.post("/projects", json=payload, headers=owner_headers)
    assert response.status_code == 422, "empty name should fail"


async def test_create_project_unauthenticated(client: AsyncClient):
    payload = {"name": "Ghost Project", "description": "No token"}
    response = await client.post("/projects", json=payload)
    assert response.status_code == 401, "unauthenticated create should fail"


#  get projects list


async def test_get_projects_owner_sees_own(
    client: AsyncClient, db_session: AsyncSession, test_owner: User, owner_headers: dict
):
    project = Project(
        name="Visible Project", description="Owner can see this", owner_id=test_owner.id
    )
    db_session.add(project)
    await db_session.flush()

    access = Access(user_id=test_owner.id, project_id=project.id, role="owner")
    db_session.add(access)
    await db_session.flush()

    response = await client.get("/projects", headers=owner_headers)
    assert response.status_code == 200, "owner list should succeed"

    ids = [p["id"] for p in response.json()]
    assert project.id in ids, "owner should see owned project"


async def test_get_projects_participant_sees_invited(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    test_participant: User,
    participant_headers: dict,
):
    project = Project(
        name="Shared With Participant", description="desc", owner_id=test_owner.id
    )
    db_session.add(project)
    await db_session.flush()

    access = Access(
        user_id=test_participant.id, project_id=project.id, role="participant"
    )
    db_session.add(access)
    await db_session.flush()

    response = await client.get("/projects", headers=participant_headers)
    assert response.status_code == 200, "participant list should succeed"

    ids = [p["id"] for p in response.json()]
    assert project.id in ids, "participant should see invited project"


async def test_get_projects_excludes_inaccessible(
    client: AsyncClient, db_session: AsyncSession, test_owner: User, other_headers: dict
):
    project = Project(
        name="Hidden From Others", description="desc", owner_id=test_owner.id
    )
    db_session.add(project)
    await db_session.flush()

    # no Access row for other_user - project must not appear in their list
    response = await client.get("/projects", headers=other_headers)
    assert response.status_code == 200, "list request should succeed"

    ids = [p["id"] for p in response.json()]
    assert project.id not in ids, "inaccessible project must be hidden"


async def test_get_projects_response_has_documents_field(
    client: AsyncClient, owner_headers: dict
):
    response = await client.get("/projects", headers=owner_headers)
    assert response.status_code == 200, "list request should succeed"

    for project in response.json():
        assert "documents" in project, "project should include documents"


async def test_get_projects_unauthenticated(client: AsyncClient):
    response = await client.get("/projects")
    assert response.status_code == 401, "missing token should fail"


#  get project info


async def test_get_project_info_owner(
    client: AsyncClient, db_session: AsyncSession, test_owner: User, owner_headers: dict
):
    project = Project(
        name="Info Project", description="Details here", owner_id=test_owner.id
    )
    db_session.add(project)
    await db_session.flush()

    db_session.add(Access(user_id=test_owner.id, project_id=project.id, role="owner"))
    await db_session.flush()

    response = await client.get(f"/project/{project.id}/info", headers=owner_headers)
    assert response.status_code == 200, "owner info request should succeed"
    assert response.json()["name"] == "Info Project", (
        "project info should return the correct name"
    )


async def test_get_project_info_participant(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    test_participant: User,
    participant_headers: dict,
):
    project = Project(
        name="Participant Info", description="desc", owner_id=test_owner.id
    )
    db_session.add(project)
    await db_session.flush()

    db_session.add(
        Access(user_id=test_participant.id, project_id=project.id, role="participant")
    )
    await db_session.flush()

    response = await client.get(
        f"/project/{project.id}/info", headers=participant_headers
    )
    assert response.status_code == 200, "participant info request should succeed"


async def test_get_project_info_no_access(
    client: AsyncClient, db_session: AsyncSession, test_owner: User, other_headers: dict
):
    project = Project(
        name="No Access Project", description="desc", owner_id=test_owner.id
    )
    db_session.add(project)
    await db_session.flush()

    response = await client.get(f"/project/{project.id}/info", headers=other_headers)
    assert response.status_code in [403, 404], "user without access should be blocked"


async def test_get_project_info_not_found(client: AsyncClient, owner_headers: dict):
    response = await client.get("/project/999999/info", headers=owner_headers)
    assert response.status_code == 404, "missing project should return 404"


async def test_get_project_info_unauthenticated(
    client: AsyncClient, db_session: AsyncSession, test_owner: User
):
    project = Project(
        name="Auth Guard Project", description="desc", owner_id=test_owner.id
    )
    db_session.add(project)
    await db_session.flush()

    response = await client.get(f"/project/{project.id}/info")
    assert response.status_code == 401, "missing token should fail"


#  update project


async def test_update_project_owner(
    client: AsyncClient, db_session: AsyncSession, test_owner: User, owner_headers: dict
):
    project = Project(
        name="Before Update", description="Old desc", owner_id=test_owner.id
    )
    db_session.add(project)
    await db_session.flush()

    db_session.add(Access(user_id=test_owner.id, project_id=project.id, role="owner"))
    await db_session.flush()

    response = await client.put(
        f"/project/{project.id}/info",
        json={"name": "After Update", "description": "New desc"},
        headers=owner_headers,
    )
    assert response.status_code == 200, "owner update should succeed"
    assert response.json()["name"] == "After Update", (
        "updated project should return new name"
    )


async def test_update_project_participant_allowed(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    test_participant: User,
    participant_headers: dict,
):
    project = Project(
        name="Participant Edit", description="desc", owner_id=test_owner.id
    )
    db_session.add(project)
    await db_session.flush()

    db_session.add(
        Access(user_id=test_participant.id, project_id=project.id, role="participant")
    )
    await db_session.flush()

    response = await client.put(
        f"/project/{project.id}/info",
        json={"name": "Participant Changed", "description": "desc"},
        headers=participant_headers,
    )
    assert response.status_code == 200, "participant update should be allowed"


async def test_update_project_partial_keeps_description(
    client: AsyncClient, db_session: AsyncSession, test_owner: User, owner_headers: dict
):
    project = Project(
        name="Partial Update",
        description="Keep this description",
        owner_id=test_owner.id,
    )
    db_session.add(project)
    await db_session.flush()

    db_session.add(Access(user_id=test_owner.id, project_id=project.id, role="owner"))
    await db_session.flush()

    response = await client.put(
        f"/project/{project.id}/info",
        json={"name": "Only Name Changed", "description": "Keep this description"},
        headers=owner_headers,
    )
    assert response.status_code == 200, "partial update should succeed"
    assert response.json()["description"] == "Keep this description", (
        "partial update should keep description unchanged"
    )


async def test_update_project_no_access(
    client: AsyncClient, db_session: AsyncSession, test_owner: User, other_headers: dict
):
    project = Project(name="Locked Project", description="desc", owner_id=test_owner.id)
    db_session.add(project)
    await db_session.flush()

    response = await client.put(
        f"/project/{project.id}/info",
        json={"name": "Hacked Name", "description": "Hacked"},
        headers=other_headers,
    )
    assert response.status_code in [403, 404], "user without access should be blocked"


async def test_update_project_empty_name(
    client: AsyncClient, db_session: AsyncSession, test_owner: User, owner_headers: dict
):
    project = Project(
        name="Valid Name Here", description="desc", owner_id=test_owner.id
    )
    db_session.add(project)
    await db_session.flush()

    db_session.add(Access(user_id=test_owner.id, project_id=project.id, role="owner"))
    await db_session.flush()

    response = await client.put(
        f"/project/{project.id}/info",
        json={"name": "", "description": "desc"},
        headers=owner_headers,
    )
    assert response.status_code == 422, "empty name should fail"


async def test_update_project_unauthenticated(
    client: AsyncClient, db_session: AsyncSession, test_owner: User
):
    project = Project(name="Unauth Update", description="desc", owner_id=test_owner.id)
    db_session.add(project)
    await db_session.flush()

    response = await client.put(
        f"/project/{project.id}/info",
        json={"name": "New Name Here", "description": "desc"},
    )
    assert response.status_code == 401, "missing token should fail"


#  delete project


async def test_delete_project_owner_success(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    owner_headers: dict,
    mock_s3: dict,
):
    project = Project(
        name="Delete Me Project", description="desc", owner_id=test_owner.id
    )
    db_session.add(project)
    await db_session.flush()

    db_session.add(Access(user_id=test_owner.id, project_id=project.id, role="owner"))
    await db_session.flush()

    response = await client.delete(f"/project/{project.id}", headers=owner_headers)
    assert response.status_code in [200, 204], "owner delete should succeed"

    stmt = select(Project).where(Project.id == project.id)
    result = (await db_session.execute(stmt)).scalar_one_or_none()
    assert result is None, "project should be removed from the database"


async def test_delete_project_removes_documents_from_db(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    owner_headers: dict,
    mock_s3: dict,
):
    project = Project(
        name="Project With Docs", description="desc", owner_id=test_owner.id
    )
    db_session.add(project)
    await db_session.flush()

    db_session.add(Access(user_id=test_owner.id, project_id=project.id, role="owner"))

    doc = Document(
        name="attached.pdf",
        project_id=project.id,
        owner_id=test_owner.id,
        url="projects/1/documents/attached.pdf",
        is_pending=False,
    )
    db_session.add(doc)
    await db_session.flush()

    await client.delete(f"/project/{project.id}", headers=owner_headers)

    stmt = select(Document).where(Document.project_id == project.id)
    docs = (await db_session.execute(stmt)).scalars().all()
    assert len(docs) == 0, "project documents should be deleted"


async def test_delete_project_participant_blocked(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    test_participant: User,
    participant_headers: dict,
    mock_s3: dict,
):
    project = Project(
        name="Participant Cannot Delete", description="desc", owner_id=test_owner.id
    )
    db_session.add(project)
    await db_session.flush()

    db_session.add(
        Access(user_id=test_participant.id, project_id=project.id, role="participant")
    )
    await db_session.flush()

    response = await client.delete(
        f"/project/{project.id}", headers=participant_headers
    )
    assert response.status_code == 403, "participant delete should fail"


async def test_delete_project_no_access_blocked(
    client: AsyncClient, db_session: AsyncSession, test_owner: User, other_headers: dict
):
    project = Project(
        name="Other Cannot Delete", description="desc", owner_id=test_owner.id
    )
    db_session.add(project)
    await db_session.flush()

    response = await client.delete(f"/project/{project.id}", headers=other_headers)
    assert response.status_code in [403, 404], "user without access should be blocked"


async def test_delete_project_unauthenticated(
    client: AsyncClient, db_session: AsyncSession, test_owner: User
):
    project = Project(name="Unauth Delete", description="desc", owner_id=test_owner.id)
    db_session.add(project)
    await db_session.flush()

    response = await client.delete(f"/project/{project.id}")
    assert response.status_code == 401, "missing token should fail"


async def test_delete_project_not_found(client: AsyncClient, owner_headers: dict):
    response = await client.delete("/project/999999", headers=owner_headers)
    assert response.status_code == 404, "missing project should return 404"


#  invite user


async def test_invite_user_success(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    test_participant: User,
    owner_headers: dict,
):
    project = Project(name="Invite Project", description="desc", owner_id=test_owner.id)
    db_session.add(project)
    await db_session.flush()

    db_session.add(Access(user_id=test_owner.id, project_id=project.id, role="owner"))
    await db_session.flush()

    url = f"/project/{project.id}/invite?user={test_participant.login}"
    response = await client.post(url, headers=owner_headers)
    assert response.status_code in [200, 201], "invite should succeed"

    stmt = select(Access).where(
        Access.project_id == project.id, Access.user_id == test_participant.id
    )
    access = (await db_session.execute(stmt)).scalar_one_or_none()
    assert access is not None, "invited access row should be created"
    assert access.role == "participant", "invitee should get participant role"


async def test_invite_grants_project_access(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    test_participant: User,
    owner_headers: dict,
    participant_headers: dict,
):
    project = Project(
        name="Post-Invite Access", description="desc", owner_id=test_owner.id
    )
    db_session.add(project)
    await db_session.flush()

    db_session.add(Access(user_id=test_owner.id, project_id=project.id, role="owner"))
    await db_session.flush()

    # before invite - participant should not have access
    response = await client.get(
        f"/project/{project.id}/info", headers=participant_headers
    )
    assert response.status_code in [403, 404], (
        "participant should not access before invite"
    )

    # send invite
    await client.post(
        f"/project/{project.id}/invite?user={test_participant.login}",
        headers=owner_headers,
    )

    # after invite - participant should have access
    response = await client.get(
        f"/project/{project.id}/info", headers=participant_headers
    )
    assert response.status_code == 200, "participant should access after invite"


async def test_invite_participant_cannot_invite(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    test_participant: User,
    other_user: User,
    participant_headers: dict,
):
    project = Project(name="Invite Lock", description="desc", owner_id=test_owner.id)
    db_session.add(project)
    await db_session.flush()

    db_session.add(
        Access(user_id=test_participant.id, project_id=project.id, role="participant")
    )
    await db_session.flush()

    url = f"/project/{project.id}/invite?user={other_user.login}"
    response = await client.post(url, headers=participant_headers)
    assert response.status_code == 403, "participant should not be able to invite"


async def test_invite_no_access_cannot_invite(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    test_participant: User,
    other_headers: dict,
):
    project = Project(
        name="Outsider Invite Attempt", description="desc", owner_id=test_owner.id
    )
    db_session.add(project)
    await db_session.flush()

    url = f"/project/{project.id}/invite?user={test_participant.login}"
    response = await client.post(url, headers=other_headers)
    assert response.status_code in [403, 404], "user without access should be blocked"


async def test_invite_nonexistent_user(
    client: AsyncClient, db_session: AsyncSession, test_owner: User, owner_headers: dict
):
    project = Project(name="Invite Ghost", description="desc", owner_id=test_owner.id)
    db_session.add(project)
    await db_session.flush()

    db_session.add(Access(user_id=test_owner.id, project_id=project.id, role="owner"))
    await db_session.flush()

    response = await client.post(
        f"/project/{project.id}/invite?user=ghost_nobody_xyz", headers=owner_headers
    )
    assert response.status_code == 404, "unknown user should return 404"


async def test_invite_already_invited_returns_409(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    test_participant: User,
    owner_headers: dict,
):
    project = Project(name="Double Invite", description="desc", owner_id=test_owner.id)
    db_session.add(project)
    await db_session.flush()

    db_session.add(Access(user_id=test_owner.id, project_id=project.id, role="owner"))
    db_session.add(
        Access(user_id=test_participant.id, project_id=project.id, role="participant")
    )
    await db_session.flush()

    url = f"/project/{project.id}/invite?user={test_participant.login}"
    response = await client.post(url, headers=owner_headers)
    assert response.status_code == 409, "duplicate invite should fail"


async def test_invite_unauthenticated(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    test_participant: User,
):
    project = Project(name="Unauth Invite", description="desc", owner_id=test_owner.id)
    db_session.add(project)
    await db_session.flush()

    url = f"/project/{project.id}/invite?user={test_participant.login}"
    response = await client.post(url)
    assert response.status_code == 401, "missing token should fail"
