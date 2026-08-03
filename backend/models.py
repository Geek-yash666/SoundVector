#!/usr/bin/env python3
"""
SoundVector Pydantic Data Models & Request Schemas
"""

from typing import List, Optional
from pydantic import BaseModel


class RecommendRequest(BaseModel):
    query: str = "Starboy"
    mode: str = "similar"
    user: str = "default"
    search_type: str = "auto"
    seed_track: Optional[dict] = None
    limit: int = 15
    offset: int = 0


class AIIntelRequest(BaseModel):
    facts: dict = {}
    recs: list = []


class PlaylistGenRequest(BaseModel):
    prompt: str
    user: str = "default"
    count: int = 15


class FeedbackRequest(BaseModel):
    user: str = "default"
    row: Optional[int] = -1
    signal: str = "like"
    mode: str = "similar"
    name: Optional[str] = None
    artist: Optional[str] = None
    deezer_album_art: Optional[str] = None
    deezer_preview_url: Optional[str] = None
    base_genres: Optional[list] = None


class BatchEnrichRequest(BaseModel):
    """Request body for /api/batch_enrich endpoint."""
    tracks: List[dict] = []
