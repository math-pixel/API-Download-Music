import asyncio
from typing import Optional
from yt_dlp import YoutubeDL
import os

from app.interfaces.download_interface import DownloadInterface
from app.models.track import Track, PlatformSource
from app.config import settings


class YouTubePlatform(DownloadInterface):
    
    def __init__(self):
        self._api_key = settings.youtube_api_key
    
    # ============================================
    # PROPRIÉTÉS
    # ============================================
    
    @property
    def platform_name(self) -> PlatformSource:
        return PlatformSource.YOUTUBE
    
    @property
    def is_available(self) -> bool:
        return True  # yt-dlp fonctionne sans clé API
    
    @property
    def supports_download(self) -> bool:
        return True
    
    @property
    def supports_bpm(self) -> bool:
        return False  # YouTube ne fournit pas le BPM
    
    # ============================================
    # MÉTHODES PRINCIPALES
    # ============================================
    
    async def search(self, query: str, limit: int = 20) -> list[Track]:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'force_generic_extractor': False,
        }
        
        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self._search_sync(query, limit, ydl_opts)
            )
            return results
            
        except Exception as e:
            print(f"[YouTube] Erreur recherche: {e}")
            return []
    
    async def get_track(self, track_id: str) -> Optional[Track]:
        if track_id.startswith("yt_"):
            track_id = track_id[3:]
        
        url = f"https://www.youtube.com/watch?v={track_id}"
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None,
                lambda: self._get_info_sync(url, ydl_opts)
            )
            
            if info:
                return self._parse_track(info)
            return None
            
        except Exception as e:
            print(f"[YouTube] Erreur get_track: {e}")
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
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._download_sync(track.url, ydl_opts)
        )
        
        return f"{filepath}.mp3"
    
    async def get_bpm(self, track: Track) -> Optional[float]:
        # YouTube ne fournit pas le BPM
        # Il faudrait analyser le fichier audio
        return None
    
    # ============================================
    # MÉTHODES PRIVÉES
    # ============================================
    
    def _search_sync(self, query: str, limit: int, ydl_opts: dict) -> list[Track]:
        search_url = f"ytsearch{limit}:{query}"
        
        with YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(search_url, download=False)
            
            tracks = []
            for entry in result.get("entries", []):
                track = self._parse_track(entry)
                if track:
                    tracks.append(track)
            
            return tracks
    
    def _get_info_sync(self, url: str, ydl_opts: dict) -> Optional[dict]:
        with YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    
    def _download_sync(self, url: str, ydl_opts: dict):
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    
    def _parse_track(self, data: dict) -> Optional[Track]:
        try:
            video_id = data.get("id", "")
            title = data.get("title", "Unknown")
            uploader = data.get("uploader", "Unknown Artist")
            
            # Essayer de séparer artiste - titre si le format est "Artiste - Titre"
            if " - " in title:
                parts = title.split(" - ", 1)
                artist = parts[0].strip()
                title = parts[1].strip()
            else:
                artist = uploader
            
            return Track(
                id=f"yt_{video_id}",
                title=title,
                artist=artist,
                source=self.platform_name,
                url=f"https://www.youtube.com/watch?v={video_id}",
                bpm=None,
                duration=data.get("duration", 0),
                artwork_url=data.get("thumbnail"),
                genre=None
            )
        except Exception as e:
            print(f"[YouTube] Erreur parsing: {e}")
            return None