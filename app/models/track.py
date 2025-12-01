from pydantic import BaseModel
from typing import Optional
from enum import Enum


class PlatformSource(str, Enum):
    SOUNDCLOUD = "soundcloud"
    SPOTIFY = "spotify"
    DEEZER = "deezer"
    YOUTUBE = "youtube"


class Track(BaseModel):
    id: str
    title: str
    artist: str
    source: PlatformSource
    url: str
    bpm: Optional[float] = None
    duration: Optional[int] = None  # en secondes
    artwork_url: Optional[str] = None
    genre: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "sc_123456",
                "title": "Summer Vibes",
                "artist": "DJ Example",
                "source": "soundcloud",
                "url": "https://soundcloud.com/example/summer-vibes",
                "bpm": 128.0,
                "duration": 240,
                "artwork_url": "https://i1.sndcdn.com/artworks-xxx.jpg",
                "genre": "House"
            }
        }


class DownloadRequest(BaseModel):
    url: str
    source: PlatformSource
    track_id: str


class DownloadResponse(BaseModel):
    status: str
    filepath: Optional[str] = None
    error: Optional[str] = None
    track: Optional[Track] = None


class SearchResponse(BaseModel):
    query: str
    total_results: int
    results: list[Track]