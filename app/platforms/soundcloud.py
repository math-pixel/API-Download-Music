import httpx
import asyncio
from typing import Optional
from yt_dlp import YoutubeDL
import os

from app.interfaces.download_interface import DownloadInterface
from app.models.track import Track, PlatformSource
from app.config import settings


class SoundCloudPlatform(DownloadInterface):
    
    # ============================================
    # PROPRIÉTÉS
    # ============================================
    
    @property
    def platform_name(self) -> PlatformSource:
        return PlatformSource.SOUNDCLOUD
    
    @property
    def is_available(self) -> bool:
        return True
    
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
        """Recherche via yt-dlp (pas besoin de client_id)"""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        
        search_url = f"scsearch{limit}:{query}"
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._search_sync(search_url, ydl_opts)
        )
        
        return result
    
    def _search_sync(self, search_url: str, ydl_opts: dict) -> list[Track]:
        tracks = []
        with YoutubeDL(ydl_opts) as ydl:
            data = ydl.extract_info(search_url, download=False)
            
            for entry in data.get("entries", []):
                track = Track(
                    id=f"sc_{entry.get('id', '')}",
                    title=entry.get("title", "Unknown"),
                    artist=entry.get("uploader", "Unknown"),
                    source=PlatformSource.SOUNDCLOUD,
                    url=entry.get("url", entry.get("webpage_url", "")),
                    duration=entry.get("duration", 0),
                )
                tracks.append(track)
        
        return tracks
    
    async def get_track(self, track_id: str) -> Optional[Track]:
        """
        Récupère un track par son ID ou URL.
        
        Accepte:
        - "sc_123456789" (ID avec préfixe)
        - "123456789" (ID seul)
        - "https://soundcloud.com/artist/track" (URL complète)
        """
        
        # Déterminer si c'est une URL ou un ID
        if track_id.startswith("http"):
            url = track_id
        elif track_id.startswith("sc_"):
            # ID avec préfixe → essayer l'URL API
            numeric_id = track_id[3:]
            url = f"https://api.soundcloud.com/tracks/{numeric_id}"
        else:
            # ID seul
            url = f"https://api.soundcloud.com/tracks/{track_id}"
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._get_track_sync(url, ydl_opts)
        )

    def _get_track_sync(self, url: str, ydl_opts: dict) -> Optional[Track]:
        """Récupération synchrone"""
        try:
            with YoutubeDL(ydl_opts) as ydl:
                data = ydl.extract_info(url, download=False)
                
                if not data:
                    return None
                
                return Track(
                    id=self.generate_track_id(str(data.get('id', ''))),
                    title=data.get("title", "Unknown"),
                    artist=data.get("uploader", "Unknown"),
                    source=self.platform_name,
                    url=data.get("webpage_url") or url,
                    duration=data.get("duration") or 0,
                    artwork_url=data.get("thumbnail"),
                    genre=data.get("genre"),
                    bpm=None
                )
                
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

    def _download_sync(self, url: str, ydl_opts: dict):
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])