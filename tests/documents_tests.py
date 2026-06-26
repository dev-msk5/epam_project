# upload, download, delete, access control

# test_upload_document()
#  owner can upload a PDF
#  owner can upload a DOCX
#  owner can upload multiple files at once
#  document is saved in DB with correct project_id
#  document is uploaded to S3 (mock S3)
#  participant can upload (participants CAN modify)
#  user with no access gets 403
#  unsupported file type (e.g. .exe) gets 422
#  unauthenticated request returns 401

# test_get_documents()
#  owne can list project documents
#  participant can list project documents
#  user with no access gets 403
#  non-existent project_id gets 404
#  unauthenticated request returns 401

# test_download_document()
#  owner can download document
#  participant can download document
#  response is the actual file bytes (not JSON)
#  user with no access gets 403
#  non-existent document_id gets 404
#  unauthenticated request returns 401

# test_update_document()
#  owner can replace document file
#  participant can replace document file
#  old S3 file is deleted, new one uploaded (mock S3)
#  DB record is updated (url, updated_at)
#  user with no access gets 403
#  non-existent document_id gets 404
#  unauthenticated request returns 401

# test_delete_document()
#  owner can delete document
#  document removed from DB
#  document removed from S3 (mock S3)
#  participant CANNOT delete document — gets 403
#  user with no access gets 403
#  non-existent document_id gets 404
#  unauthenticated request returns 401

# access_control
#  user A cannot see user B's projects
#  user A cannot update user B's project
#  user A cannot delete user B's project
#  user A cannot download user B's documents
#  participant cannot delete project
#  participant cannot delete document
#  participant cannot invite other users
#  participant CAN read project info
#  participant CAN update project info
#  participant CAN upload documents
#  participant CAN download documents
