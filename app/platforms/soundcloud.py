import httpx
import asyncio
from typing import Optional
from yt_dlp import YoutubeDL
import os

from app.interfaces.download_interface import DownloadInterface
from app.models.track import Track, PlatformSource
from app.config import settings


class SoundCloudPlatform(DownloadInterface):
    
    def __init__(self):
        self._client_id = settings.soundcloud_client_id
        self._base_url = "https://api-v2.soundcloud.com"
    
    # ============================================
    # PROPRIÉTÉS
    # ============================================
    
    @property
    def platform_name(self) -> PlatformSource:
        return PlatformSource.SOUNDCLOUD
    
    @property
    def is_available(self) -> bool:
        return self._client_id is not None
    
    @property
    def supports_download(self) -> bool:
        return True
    
    @property
    def supports_bpm(self) -> bool:
        return False  # SoundCloud ne fournit pas le BPM via API
    
    # ============================================
    # MÉTHODES PRINCIPALES
    # ============================================
    
    async def search(self, query: str, limit: int = 20) -> list[Track]:
        if not self.is_available:
            return []
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self._base_url}/search/tracks",
                    params={
                        "q": query,
                        "client_id": self._client_id,
                        "limit": limit,
                        "linked_partitioning": 1
                    },
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                
                tracks = []
                for item in data.get("collection", []):
                    track = self._parse_track(item)
                    if track:
                        tracks.append(track)
                
                return tracks
                
            except Exception as e:
                print(f"[SoundCloud] Erreur recherche: {e}")
                return []
    
    async def get_track(self, track_id: str) -> Optional[Track]:
        if not self.is_available:
            return None
        
        # Enlever le préfixe si présent
        if track_id.startswith("sc_"):
            track_id = track_id[3:]
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self._base_url}/tracks/{track_id}",
                    params={"client_id": self._client_id},
                    timeout=10.0
                )
                response.raise_for_status()
                return self._parse_track(response.json())
                
            except Exception as e:
                print(f"[SoundCloud] Erreur get_track: {e}")
                return None
    
    async def download(self, track: Track, output_path: str) -> str:
        filename = self.sanitize_filename(f"{track.artist} - {track.title}")
        filepath = os.path.join(output_path, filename)
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f"{filepath}.%(ext)s",
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'quiet': True,
            'no_warnings': True,
        }
        
        # yt-dlp est synchrone, on l'exécute dans un thread
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._download_sync(track.url, ydl_opts)
        )
        
        return f"{filepath}.mp3"
    
    async def get_bpm(self, track: Track) -> Optional[float]:
        # SoundCloud ne fournit pas le BPM
        # On pourrait analyser le fichier audio après téléchargement
        return None
    
    # ============================================
    # MÉTHODES PRIVÉES
    # ============================================
    
    def _parse_track(self, data: dict) -> Optional[Track]:
        try:
            user = data.get("user", {})
            
            return Track(
                id=self.generate_track_id(str(data["id"])),
                title=data.get("title", "Unknown"),
                artist=user.get("username", "Unknown Artist"),
                source=self.platform_name,
                url=data.get("permalink_url", ""),
                bpm=data.get("bpm"),  # Rarement disponible
                duration=data.get("duration", 0) // 1000,  # ms to seconds
                artwork_url=data.get("artwork_url", "").replace("-large", "-t500x500") if data.get("artwork_url") else None,
                genre=data.get("genre")
            )
        except Exception as e:
            print(f"[SoundCloud] Erreur parsing: {e}")
            return None
    
    def _download_sync(self, url: str, ydl_opts: dict):
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])