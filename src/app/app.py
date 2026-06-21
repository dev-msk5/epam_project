from fastapi import FastAPI

"""API:
POST /auth - Create user (login, password, repeat password) 
POST /login - Login into service (login, password) 
POST /projects - Create project from details (name, description). Automatically gives access to created project to user, making him the owner (admin of the project).
GET /projects - Get all projects, accessible for a user. Returns list of projects full info(details + documents).
GET /project/<project_id>/info - Return project’s details, if user has access
PUT /project/<project_id>/info - Update projects details - name, description. Returns the updated project’s info
DELETE /project/<project_id>- Delete project, can only be performed by the projects’ owner. Deletes the corresponding  documents
GET /project/<project_id>/documents- Return all of the project's documents
POST /project/<project_id>/documents - Upload document/documents for a specific project
GET /document/<document_id> - Download document, if the user has access to the corresponding project
PUT /document/<document_id> - Update document
DELETE /document/<document_id> - Delete document and remove it from the corresponding project
POST /project/<project_id>/invite?user=<login> - Grant access to the project for a specific user. If the request is not coming from the owner of the project, results in error. Granting access gives participant permissions to receiving user
"""

app = FastAPI()


# project class idea
class Project:
    owner: str
    name: str
    description: str
    documents: list


class User:
    login: str
    password: str
    projects: list


@app.get("/works")
def hello():
    return {"message": "Hello, World!"}


@app.get("/projects")
async def get_projects():
    return {"message": "List of projects"}


@app.get("/project/{project_id}/documents")
def get_project_docs(project_id: int):
    # TODO better return
    return {"message": f"Documents for project {project_id}"}


@app.post("/project/{project_id}/documents")
def post_project_docs(project_id: int):
    return {"message": f"Documents uploaded for project {project_id}"}


@app.get("/document/{document_is}")
def get_document(document_id: int):
    # only if user has access to the corresponding project
    return {"message": f"Document {document_id} downloaded"}


@app.put("/document/{document_id}")
def put_document(document_id: int):
    return {"message": f"Document {document_id} updated"}


@app.delete("/document/{document_id}")
def delete_document(document_id: int):
    return {"message": f"Document {document_id} deleted"}


@app.post("/project/{project_id}/invite?user={login}")
def invite_user(project_id: int, login: str):
    # if project_owner != current_user:
    #    return {"error": "Only project owner can invite users"}
    return {"message": f"User {login} invited to project {project_id}"}
