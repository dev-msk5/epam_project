from fastapi import FastAPI
from .routes import auth, projects, documents

# App entry, router registration, startup events

app = FastAPI(title="Project Dashboard")

# Registering routers — prefix adds to all routes in that router
app.include_router(auth.router)
app.include_router(projects.router, prefix="/projects")
app.include_router(documents.router)


@app.get("/")
async def root():
    return {"message": "Welcome to the Project Dashboard API"}

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
