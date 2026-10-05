from fastapi import APIRouter
from app.api.routes import auth, users, projects, reviews, history, learning, webhooks

api_router = APIRouter(prefix="/api")

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(projects.router)
api_router.include_router(reviews.router)
api_router.include_router(history.router)
api_router.include_router(learning.router)
api_router.include_router(webhooks.router)

