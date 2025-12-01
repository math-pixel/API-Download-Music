import httpx
from typing import Optional
import asyncio
from yt_dlp import YoutubeDL
import os

from app.interfaces.download_interface import DownloadInterface
from app.models.track import Track, PlatformSource
from app.config import settings


class DeezerPlatform(DownloadInterface):
    
    def __init__(self):
        self._base_url = "https://api.deezer.com"
    
    # ============================================
    # PROPRIÉTÉS
    # ============================================
    
    @property
    def platform_name(self) -> PlatformSource:
        return PlatformSource.DEEZER
    
    @property
    def is_available(self) -> bool:
        return True  # Deezer API est publique pour la recherche
    
    @property
    def supports_download(self) -> bool:
        return True  # Via yt-dlp
    
    @property
    def supports_bpm(self) -> bool:
        return True  # Deezer fournit le BPM
    
    # ============================================
    # MÉTHODES PRINCIPALES
    # ============================================
    
    async def search(self, query: str, limit: int = 20) -> list[Track]:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self._base_url}/search",
                    params={
                        "q": query,
                        "limit": limit
                    },
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                
                tracks = []
                for item in data.get("data", []):
                    track = self._parse_track(item)
                    if track:
                        # Récupérer le BPM pour chaque track
                        track.bpm = await self._get_bpm_from_id(item["id"])
                        tracks.append(track)
                
                return tracks
                
            except Exception as e:
                print(f"[Deezer] Erreur recherche: {e}")
                return []
    
    async def get_track(self, track_id: str) -> Optional[Track]:
        # Enlever le préfixe si présent
        if track_id.startswith("dz_"):
            track_id = track_id[3:]
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self._base_url}/track/{track_id}",
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                
                track = self._parse_track_full(data)
                return track
                
            except Exception as e:
                print(f"[Deezer] Erreur get_track: {e}")
                return None
    
    async def download(self, track: Track, output_path: str) -> str:
        """
        Télécharge via yt-dlp (cherche sur YouTube le même titre)
        """
        filename = self.sanitize_filename(f"{track.artist} - {track.title}")
        filepath = os.path.join(output_path, filename)
        
        # Recherche sur YouTube avec le titre
        search_query = f"ytsearch1:{track.artist} {track.title}"
        
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
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._download_sync(search_query, ydl_opts)
        )
        
        return f"{filepath}.mp3"
    
    async def get_bpm(self, track: Track) -> Optional[float]:
        deezer_id = track.id.replace("dz_", "")
        return await self._get_bpm_from_id(deezer_id)
    
    # ============================================
    # MÉTHODES PRIVÉES
    # ============================================
    
    async def _get_bpm_from_id(self, track_id: str) -> Optional[float]:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self._base_url}/track/{track_id}",
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                
                bpm = data.get("bpm")
                if bpm and bpm > 0:
                    return float(bpm)
                return None
                
            except Exception as e:
                return None
    
    def _parse_track(self, data: dict) -> Optional[Track]:
        try:
            artist = data.get("artist", {})
            album = data.get("album", {})
            
            return Track(
                id=self.generate_track_id(str(data["id"])),
                title=data.get("title", "Unknown"),
                artist=artist.get("name", "Unknown Artist"),
                source=self.platform_name,
                url=data.get("link", ""),
                bpm=None,  # Sera rempli après
                duration=data.get("duration", 0),
                artwork_url=album.get("cover_xl") or album.get("cover_big"),
                genre=None
            )
        except Exception as e:
            print(f"[Deezer] Erreur parsing: {e}")
            return None
    
    def _parse_track_full(self, data: dict) -> Optional[Track]:
        try:
            artist = data.get("artist", {})
            album = data.get("album", {})
            
            bpm = data.get("bpm")
            
            return Track(
                id=self.generate_track_id(str(data["id"])),
                title=data.get("title", "Unknown"),
                artist=artist.get("name", "Unknown Artist"),
                source=self.platform_name,
                url=data.get("link", ""),
                bpm=float(bpm) if bpm and bpm > 0 else None,
                duration=data.get("duration", 0),
                artwork_url=album.get("cover_xl") or album.get("cover_big"),
                genre=None
            )
        except Exception as e:
            print(f"[Deezer] Erreur parsing full: {e}")
            return None
    
    def _download_sync(self, url: str, ydl_opts: dict):
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])