# CRUD + the critical: participant cannot delete, stranger cannot access
# test_create_project
# valid data returns 201 + project details
# creator automatically gets "owner" role in Access table
# Access row is created in DB
# missing name returns 422
# empty name("") returns 422
# unauthenticated request returns 401

# test_get_project
# owner sees their own project
# participant sees project they were invited to
# response includes documents list
# user does NOT see projects they have no access to
# unauthenticated request returns 401

# test_get_project_info
# owner can get project info
# participant can get project info
# user with no access gets 403
# non-existent project_id gets 404
# unauthenticated request returns 401

# test_update_project
# owner can update name
# owner can update description
# participant can update name(participant CAN modify)
# partial update works(only name, description stays same)
# user with no access gets 403
# non-existent project_id gets 404
# empty name("") returns 422
# unauthenticated request returns 401

# test_delete_project
# owner can delete project
# deleting project removes it from DB
# deleting project removes associated documents from DB
# deleting project removes documents from S3(mock S3)
# participant CANNOT delete — gets 403 (critical auth gate)
# unauthenticated request returns 401
# user with no access gets 403
# non-existent project_id gets 404

# test_invite_user
# owner can invite user by login
# invited user gets "participant" role in Access table
# invited user can now access the project
# participant CANNOT invite others — gets 403
# user with no access CANNOT invite — gets 403
# inviting non-existent login gets 404
# inviting already-invited user gets 409
# unauthenticated request returns 401

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.user import User
from app.models.project import Project
from app.models.access import Access


async def test_project_crud_owner_flow(
    client: AsyncClient,
    owner_headers: dict,
    db_session: AsyncSession
):
    """Verify that an owner can fully manage projects"""
    # Create Project (ProjectCreate schema requires name length >= 4)
    create_payload = {
        "name": "Test Dashboard",
        "description": "High level dashboard",
    }
    response = await client.post(
        "/projects", json=create_payload, headers=owner_headers
    )
    assert response.status_code in [200, 201], (
        "Project creation should succeed with 200 or 201"
    )

    project_data = response.json()
    project_id = project_data["id"]
    assert project_data["name"] == "Test Dashboard", (
        "Project name should match the creation payload"
    )
    assert project_data["invited_users"] == [], (
        "Invited users should be empty by default"
    )
    assert project_data["documents"] == [], (
        "Documents should be empty by default"
    )

    # Read details
    response = await client.get(f"/project/{project_id}/info", headers=owner_headers)
    assert response.status_code == 200, (
        "Project info retrieval should succeed with 200"
    )
    assert response.json()["name"] == "Test Dashboard", (
        "Project name should match the creation payload"
    )

    # Update details
    update_payload = {
        "name": "Updated Dashboard",
        "description": "Updated Desc",
    }
    response = await client.put(
        f"/project/{project_id}/info",
        json=update_payload,
        headers=owner_headers,
    )
    assert response.status_code == 200, (
        "Project update should succeed with 200"
    )
    assert response.json()["name"] == "Updated Dashboard", (
        "Project name should match the update payload"
    )


async def test_project_validation_rules(client: AsyncClient, owner_headers: dict):
    """Verify schema rules (like min_length=4 on project name) trigger 422 errors"""
    bad_payload = {"name": "abc", "description": "Short name"}  # Under 4 chars
    response = await client.post("/projects", json=bad_payload, headers=owner_headers)
    assert response.status_code == 422, (
        "Project creation should fail with 422 for invalid name"
    )


async def test_project_sharing_and_participant_restrictions(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    test_participant: User,
    owner_headers: dict,
    participant_headers: dict
):
    """Verify invited participants can modify but cannot delete projects."""
    project = Project(
        name="Shared Project",
        description="Shared",
        owner_id=test_owner.id,
    )
    db_session.add(project)
    await db_session.flush()

    # Invite participant (owner action)
    invite_url = f"/project/{project.id}/invite?user={test_participant.login}"
    response = await client.post(invite_url, headers=owner_headers)
    assert response.status_code in [200, 201], (
        "Inviting participant should succeed with 200 or 201"
    )

    # Verify participant role mapping in DB
    stmt = select(Access).where(
        Access.project_id == project.id,
        Access.user_id == test_participant.id,
    )
    access = (await db_session.execute(stmt)).scalar_one_or_none()
    assert access is not None, "Participant should have an Access entry in the database"
    assert access.role == "participant", (
        "Participant role should be correctly assigned in the Access table"
    )

    # Participant reads project info (Succeeds)
    response = await client.get(
        f"/project/{project.id}/info", headers=participant_headers
    )
    assert response.status_code == 200, (
        "Participant should be able to read project info with 200"
    )

    # Participant deletes project (Blocked with 403)
    response = await client.delete(
        f"/project/{project.id}", headers=participant_headers
    )
    assert response.status_code == 403, (
        "Participant should be blocked from deleting the project with 403"
    )


async def test_unauthorized_user_blocked_completely(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    other_headers: dict
):
    """Verify unauthorized users are blocked from reading or writing info."""
    project = Project(
        name="Secret Project",
        description="Hidden",
        owner_id=test_owner.id,
    )
    db_session.add(project)
    await db_session.flush()

    # Unrelated user attempts read
    response = await client.get(f"/project/{project.id}/info", headers=other_headers)
    assert response.status_code in [403, 404], (
        "Unrelated user should be blocked from reading project info"
    )

    # Unrelated user attempts write
    update_payload = {"name": "Hacked!", "description": "Hacked!"}
    response = await client.put(
        f"/project/{project.id}/info", json=update_payload, headers=other_headers
    )
    assert response.status_code in [403, 404], (
        "Unrelated user should be blocked from writing project info"
    )


async def test_invite_permission_restricted_to_owner(
    client: AsyncClient,
    db_session: AsyncSession,
    test_owner: User,
    test_participant: User,
    participant_headers: dict
):
    """Verify only the owner can invite users to a project."""
    # Create and flush project first to generate project.id
    project = Project(
        name="Core Project",
        description="Core desc",
        owner_id=test_owner.id,
    )
    db_session.add(project)
    await db_session.flush()

    # Assign the participant to the project using the generated ID
    access = Access(
        user_id=test_participant.id,
        project_id=project.id,
        role="participant",
    )
    db_session.add(access)
    await db_session.flush()

    # Participant attempts to invite an external user (Should fail with 403)
    invite_url = f"/project/{project.id}/invite?user=unrelated_user_test"
    response = await client.post(invite_url, headers=participant_headers)
    assert response.status_code == 403, (
        "Participant should be blocked from inviting users to the project with 403"
    )
