from fastapi import FastAPI

app = FastAPI(title="Project Dashboard")

# Registering routers — prefix adds to all routes in that router
app.include_router(auth.router)
app.include_router(projects.router, prefix="/projects")
app.include_router(documents.router)
