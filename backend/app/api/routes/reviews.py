"""Multi-agent code review routes."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from ..deps import get_current_user
from ...core.container import get_repo_repo, get_graph_service, get_vector_store, get_activity_repo
from ...core.interfaces.metadata import IMetadataRepository
from ...core.models.user import User
from ...core.models.review import Review
from ...core.models.activity import ActivityEvent
from ...services.review_service import ReviewService
from ...infrastructure.mongodb.metadata_repo import MongoMetadataRepository
from functools import lru_cache

router = APIRouter(tags=["reviews"])


@lru_cache
def get_review_repo() -> IMetadataRepository[Review]:
    return MongoMetadataRepository("reviews", Review)


def get_review_service() -> ReviewService:
    return ReviewService(get_review_repo(), get_repo_repo(), get_graph_service(), get_vector_store())


@router.post("/repos/{repo_id}/reviews")
async def start_review(repo_id: str, bg: BackgroundTasks, user: User = Depends(get_current_user), svc: ReviewService = Depends(get_review_service)):
    repos = get_repo_repo()
    repo = await repos.get(repo_id)
    if not repo or repo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.status != "ready":
        raise HTTPException(status_code=400, detail=f"Repository must be 'ready' (current: {repo.status})")
    review = await svc.create(repo_id, user.id)
    await get_activity_repo().insert(ActivityEvent(user_id=user.id, repo_id=repo_id, type="review_started", message=f"Started multi-agent review for {repo.name}"))
    bg.add_task(svc.kickoff, review.id)
    return review.model_dump()


@router.get("/repos/{repo_id}/reviews")
async def list_reviews(repo_id: str, user: User = Depends(get_current_user)):
    repos = get_repo_repo()
    repo = await repos.get(repo_id)
    if not repo or repo.user_id != user.id:
        raise HTTPException(status_code=404, detail="Repository not found")
    items = await get_review_repo().list({"repo_id": repo_id, "user_id": user.id}, limit=50, sort=[("created_at", -1)])
    return [r.model_dump() for r in items]


@router.get("/reviews/{review_id}")
async def get_review(review_id: str, user: User = Depends(get_current_user)):
    rev = await get_review_repo().get(review_id)
    if not rev or rev.user_id != user.id:
        raise HTTPException(status_code=404, detail="Review not found")
    return rev.model_dump()
