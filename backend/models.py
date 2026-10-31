#!/usr/bin/env python3
"""
SoundVector Pydantic Data Models & Request Schemas
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class RecommendRequest(BaseModel):
    query: str = "Starboy"
    mode: str = "flow"
    user: str = "default"
    search_type: str = "auto"
    seed_track: Optional[dict] = None
    limit: int = Field(default=15, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=1000)


class AIIntelRequest(BaseModel):
    facts: dict = {}
    recs: list = []


class PlaylistGenRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=500)
    user: str = "default"
    count: int = Field(default=15, ge=1, le=50)


class FeedbackRequest(BaseModel):
    user: str = "default"
    row: Optional[int] = -1
    signal: Literal["like", "dislike", "skip", "none", "remove_like", "remove_dislike"] = "like"
    mode: str = "similar"
    name: Optional[str] = None
    artist: Optional[str] = None
    deezer_album_art: Optional[str] = None
    deezer_preview_url: Optional[str] = None
    base_genres: Optional[list] = None
    genres: Optional[list] = None
    recording_genres: Optional[list] = None
    metadata_source: Optional[str] = None
    language: Optional[str] = None
    language_source: Optional[str] = None
    album: Optional[str] = None
    album_id: Optional[str] = None
    album_source: Optional[str] = None
    source: Optional[str] = None
    deezer_link: Optional[str] = None
    artists: Optional[list] = None
    duration_seconds: Optional[float] = None
    provider_id: Optional[str] = None
    deezer_id: Optional[str] = None
    itunes_id: Optional[str] = None
    release_date: Optional[str] = None
    track_number: Optional[int] = None
    disc_number: Optional[int] = None
    explicit: Optional[bool] = None
    label: Optional[str] = None
    isrc: Optional[str] = None


class BatchEnrichRequest(BaseModel):
    """Request body for /api/batch_enrich endpoint."""
    tracks: List[dict] = []


class PreferencesRequest(BaseModel):
    user: str = "default"
    artists: List[str] = Field(default_factory=list, max_length=10)
    languages: List[str] = Field(default_factory=list, max_length=10)


class ListeningRequest(BaseModel):
    user: str
    track: dict
    seconds: float = Field(ge=0, le=3600)
    duration: float = Field(ge=0, le=3600)
    event_id: str = Field(min_length=1, max_length=100)
