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
