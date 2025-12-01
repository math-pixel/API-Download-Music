# API DJ Multi-Platform Complète 🎧

## Structure du projet

```
dj-api/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── interfaces/
│   │   ├── __init__.py
│   │   └── download_interface.py
│   ├── platforms/
│   │   ├── __init__.py
│   │   ├── soundcloud.py
│   │   ├── spotify.py
│   │   ├── deezer.py
│   │   └── youtube.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── search_service.py
│   │   └── download_service.py
│   └── models/
│       ├── __init__.py
│       └── track.py
├── downloads/
├── requirements.txt
├── .env
└── README.md
```

---

## 1. Fichiers de base

### `requirements.txt`

```txt
fastapi==0.104.1
uvicorn==0.24.0
python-dotenv==1.0.0
yt-dlp==2023.11.16
spotipy==2.23.0
httpx==0.25.2
pydantic==2.5.2
aiohttp==3.9.1
mutagen==1.47.0
```

---

### `.env`

```env
# SoundCloud
SOUNDCLOUD_CLIENT_ID=your_soundcloud_client_id

# Spotify
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret

# Deezer (pas besoin de clé pour recherche basique)

# YouTube (optionnel)
YOUTUBE_API_KEY=your_youtube_api_key

# Config
DOWNLOAD_PATH=./downloads
MAX_RESULTS=20
```

---

### `app/config.py`

```python
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # SoundCloud
    soundcloud_client_id: Optional[str] = None
    
    # Spotify
    spotify_client_id: Optional[str] = None
    spotify_client_secret: Optional[str] = None
    
    # YouTube
    youtube_api_key: Optional[str] = None
    
    # Config générale
    download_path: str = "./downloads"
    max_results: int = 20
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Créer le dossier de téléchargement s'il n'existe pas
os.makedirs(settings.download_path, exist_ok=True)
```

---

## 2. Models

### `app/models/track.py`

```python
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
```

---

## 3. Interface

### `app/interfaces/download_interface.py`

```python
from abc import ABC, abstractmethod
from typing import Optional
from app.models.track import Track, PlatformSource


class DownloadInterface(ABC):
    """
    Interface abstraite pour toutes les plateformes de musique.
    Chaque plateforme doit implémenter ces méthodes.
    """
    
    # ============================================
    # PROPRIÉTÉS ABSTRAITES
    # ============================================
    
    @property
    @abstractmethod
    def platform_name(self) -> PlatformSource:
        """Retourne le nom de la plateforme"""
        pass
    
    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Vérifie si la plateforme est configurée et disponible"""
        pass
    
    @property
    @abstractmethod
    def supports_download(self) -> bool:
        """Indique si la plateforme supporte le téléchargement direct"""
        pass
    
    @property
    @abstractmethod
    def supports_bpm(self) -> bool:
        """Indique si la plateforme fournit le BPM"""
        pass
    
    # ============================================
    # MÉTHODES ABSTRAITES
    # ============================================
    
    @abstractmethod
    async def search(self, query: str, limit: int = 20) -> list[Track]:
        """
        Recherche des tracks sur la plateforme.
        
        Args:
            query: Terme de recherche
            limit: Nombre maximum de résultats
            
        Returns:
            Liste de Track
        """
        pass
    
    @abstractmethod
    async def get_track(self, track_id: str) -> Optional[Track]:
        """
        Récupère les informations d'un track spécifique.
        
        Args:
            track_id: ID unique du track sur la plateforme
            
        Returns:
            Track ou None si non trouvé
        """
        pass
    
    @abstractmethod
    async def download(self, track: Track, output_path: str) -> str:
        """
        Télécharge un track.
        
        Args:
            track: Le track à télécharger
            output_path: Chemin du dossier de destination
            
        Returns:
            Chemin complet du fichier téléchargé
        """
        pass
    
    @abstractmethod
    async def get_bpm(self, track: Track) -> Optional[float]:
        """
        Récupère le BPM d'un track.
        Peut utiliser l'API ou analyser le fichier audio.
        
        Args:
            track: Le track dont on veut le BPM
            
        Returns:
            BPM ou None si non disponible
        """
        pass
    
    # ============================================
    # MÉTHODES UTILITAIRES (non abstraites)
    # ============================================
    
    def generate_track_id(self, platform_id: str) -> str:
        """Génère un ID unique préfixé par la plateforme"""
        prefix = self.platform_name.value[:2]
        return f"{prefix}_{platform_id}"
    
    def sanitize_filename(self, filename: str) -> str:
        """Nettoie un nom de fichier"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename.strip()
```

---

## 4. Plateformes

### `app/platforms/soundcloud.py`

```python
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
```

---

### `app/platforms/spotify.py`

```python
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from typing import Optional
import asyncio

from app.interfaces.download_interface import DownloadInterface
from app.models.track import Track, PlatformSource
from app.config import settings


class SpotifyPlatform(DownloadInterface):
    
    def __init__(self):
        self._client: Optional[spotipy.Spotify] = None
        self._init_client()
    
    def _init_client(self):
        if settings.spotify_client_id and settings.spotify_client_secret:
            try:
                auth_manager = SpotifyClientCredentials(
                    client_id=settings.spotify_client_id,
                    client_secret=settings.spotify_client_secret
                )
                self._client = spotipy.Spotify(auth_manager=auth_manager)
            except Exception as e:
                print(f"[Spotify] Erreur initialisation: {e}")
    
    # ============================================
    # PROPRIÉTÉS
    # ============================================
    
    @property
    def platform_name(self) -> PlatformSource:
        return PlatformSource.SPOTIFY
    
    @property
    def is_available(self) -> bool:
        return self._client is not None
    
    @property
    def supports_download(self) -> bool:
        return False  # Spotify ne permet pas le téléchargement direct
    
    @property
    def supports_bpm(self) -> bool:
        return True  # Spotify fournit les audio features dont le BPM
    
    # ============================================
    # MÉTHODES PRINCIPALES
    # ============================================
    
    async def search(self, query: str, limit: int = 20) -> list[Track]:
        if not self.is_available:
            return []
        
        try:
            # spotipy est synchrone
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self._client.search(q=query, type='track', limit=limit)
            )
            
            tracks = []
            track_ids = []
            
            for item in results.get("tracks", {}).get("items", []):
                track = self._parse_track(item)
                if track:
                    tracks.append(track)
                    track_ids.append(item["id"])
            
            # Récupérer les BPM en batch
            if track_ids:
                bpm_map = await self._get_bpm_batch(track_ids)
                for track in tracks:
                    spotify_id = track.id.replace("sp_", "")
                    if spotify_id in bpm_map:
                        track.bpm = bpm_map[spotify_id]
            
            return tracks
            
        except Exception as e:
            print(f"[Spotify] Erreur recherche: {e}")
            return []
    
    async def get_track(self, track_id: str) -> Optional[Track]:
        if not self.is_available:
            return None
        
        # Enlever le préfixe si présent
        if track_id.startswith("sp_"):
            track_id = track_id[3:]
        
        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None,
                lambda: self._client.track(track_id)
            )
            
            track = self._parse_track(data)
            if track:
                track.bpm = await self.get_bpm(track)
            
            return track
            
        except Exception as e:
            print(f"[Spotify] Erreur get_track: {e}")
            return None
    
    async def download(self, track: Track, output_path: str) -> str:
        """
        Spotify ne permet pas le téléchargement direct.
        On peut chercher sur YouTube et télécharger depuis là.
        """
        raise NotImplementedError(
            "Spotify ne supporte pas le téléchargement direct. "
            "Utilisez la recherche YouTube avec le titre."
        )
    
    async def get_bpm(self, track: Track) -> Optional[float]:
        if not self.is_available:
            return None
        
        spotify_id = track.id.replace("sp_", "")
        
        try:
            loop = asyncio.get_event_loop()
            features = await loop.run_in_executor(
                None,
                lambda: self._client.audio_features([spotify_id])
            )
            
            if features and features[0]:
                return round(features[0].get("tempo", 0), 1)
            
            return None
            
        except Exception as e:
            print(f"[Spotify] Erreur get_bpm: {e}")
            return None
    
    # ============================================
    # MÉTHODES PRIVÉES
    # ============================================
    
    async def _get_bpm_batch(self, track_ids: list[str]) -> dict[str, float]:
        """Récupère les BPM pour plusieurs tracks en une seule requête"""
        try:
            loop = asyncio.get_event_loop()
            features = await loop.run_in_executor(
                None,
                lambda: self._client.audio_features(track_ids)
            )
            
            bpm_map = {}
            for i, feature in enumerate(features):
                if feature:
                    bpm_map[track_ids[i]] = round(feature.get("tempo", 0), 1)
            
            return bpm_map
            
        except Exception as e:
            print(f"[Spotify] Erreur batch BPM: {e}")
            return {}
    
    def _parse_track(self, data: dict) -> Optional[Track]:
        try:
            artists = ", ".join([a["name"] for a in data.get("artists", [])])
            images = data.get("album", {}).get("images", [])
            artwork = images[0]["url"] if images else None
            
            return Track(
                id=self.generate_track_id(data["id"]),
                title=data.get("name", "Unknown"),
                artist=artists or "Unknown Artist",
                source=self.platform_name,
                url=data.get("external_urls", {}).get("spotify", ""),
                bpm=None,  # Sera rempli après
                duration=data.get("duration_ms", 0) // 1000,
                artwork_url=artwork,
                genre=None  # Spotify ne donne pas le genre par track
            )
        except Exception as e:
            print(f"[Spotify] Erreur parsing: {e}")
            return None
```

---

### `app/platforms/deezer.py`

```python
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
```

---

### `app/platforms/youtube.py`

```python
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
                id=self.generate_track_id(video_id),
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
```

---

### `app/platforms/__init__.py`

```python
from app.platforms.soundcloud import SoundCloudPlatform
from app.platforms.spotify import SpotifyPlatform
from app.platforms.deezer import DeezerPlatform
from app.platforms.youtube import YouTubePlatform

__all__ = [
    "SoundCloudPlatform",
    "SpotifyPlatform", 
    "DeezerPlatform",
    "YouTubePlatform"
]
```

---

## 5. Services

### `app/services/search_service.py`

```python
import asyncio
from typing import Optional

from app.interfaces.download_interface import DownloadInterface
from app.models.track import Track, PlatformSource
from app.platforms import (
    SoundCloudPlatform,
    SpotifyPlatform,
    DeezerPlatform,
    YouTubePlatform
)


class SearchService:
    
    def __init__(self):
        self._platforms: dict[PlatformSource, DownloadInterface] = {
            PlatformSource.SOUNDCLOUD: SoundCloudPlatform(),
            PlatformSource.SPOTIFY: SpotifyPlatform(),
            PlatformSource.DEEZER: DeezerPlatform(),
            PlatformSource.YOUTUBE: YouTubePlatform(),
        }
    
    @property
    def available_platforms(self) -> list[PlatformSource]:
        return [
            name for name, platform in self._platforms.items()
            if platform.is_available
        ]
    
    def get_platform(self, source: PlatformSource) -> Optional[DownloadInterface]:
        return self._platforms.get(source)
    
    async def search_all(
        self,
        query: str,
        limit_per_platform: int = 10,
        platforms: Optional[list[PlatformSource]] = None
    ) -> list[Track]:
        """
        Recherche sur toutes les plateformes en parallèle.
        """
        if platforms is None:
            platforms = self.available_platforms
        
        tasks = []
        for platform_name in platforms:
            platform = self._platforms.get(platform_name)
            if platform and platform.is_available:
                tasks.append(
                    platform.search(query, limit_per_platform)
                )
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_tracks = []
        for result in results:
            if isinstance(result, list):
                all_tracks.extend(result)
            elif isinstance(result, Exception):
                print(f"Erreur recherche: {result}")
        
        return all_tracks
    
    async def search_platform(
        self,
        query: str,
        platform: PlatformSource,
        limit: int = 20
    ) -> list[Track]:
        """
        Recherche sur une plateforme spécifique.
        """
        platform_instance = self._platforms.get(platform)
        
        if not platform_instance or not platform_instance.is_available:
            return []
        
        return await platform_instance.search(query, limit)
    
    async def get_track(
        self,
        track_id: str,
        source: PlatformSource
    ) -> Optional[Track]:
        """
        Récupère un track spécifique.
        """
        platform = self._platforms.get(source)
        
        if not platform or not platform.is_available:
            return None
        
        return await platform.get_track(track_id)


# Singleton
search_service = SearchService()
```

---

### `app/services/download_service.py`

```python
import os
from typing import Optional

from app.models.track import Track, PlatformSource, DownloadResponse
from app.services.search_service import search_service
from app.config import settings


class DownloadService:
    
    def __init__(self):
        self._download_path = settings.download_path
    
    async def download_track(
        self,
        track_id: str,
        source: PlatformSource,
        url: Optional[str] = None
    ) -> DownloadResponse:
        """
        Télécharge un track.
        """
        platform = search_service.get_platform(source)
        
        if not platform:
            return DownloadResponse(
                status="error",
                error=f"Plateforme {source} non disponible"
            )
        
        if not platform.supports_download:
            # Fallback sur YouTube si la plateforme ne supporte pas le téléchargement
            return await self._download_via_youtube(track_id, source)
        
        try:
            # Récupérer les infos du track
            track = await platform.get_track(track_id)
            
            if not track:
                return DownloadResponse(
                    status="error",
                    error="Track non trouvé"
                )
            
            # Télécharger
            filepath = await platform.download(track, self._download_path)
            
            # Vérifier que le fichier existe
            if os.path.exists(filepath):
                return DownloadResponse(
                    status="ready",
                    filepath=filepath,
                    track=track
                )
            else:
                return DownloadResponse(
                    status="error",
                    error="Fichier non créé"
                )
                
        except Exception as e:
            return DownloadResponse(
                status="error",
                error=str(e)
            )
    
    async def _download_via_youtube(
        self,
        track_id: str,
        source: PlatformSource
    ) -> DownloadResponse:
        """
        Télécharge un track en cherchant sur YouTube.
        Utilisé pour les plateformes qui ne supportent pas le téléchargement direct.
        """
        try:
            # Récupérer les infos du track original
            platform = search_service.get_platform(source)
            track = await platform.get_track(track_id)
            
            if not track:
                return DownloadResponse(
                    status="error",
                    error="Track non trouvé"
                )
            
            # Utiliser YouTube pour télécharger
            youtube = search_service.get_platform(PlatformSource.YOUTUBE)
            
            # Créer un track temporaire pour YouTube
            youtube_track = Track(
                id=track.id,
                title=track.title,
                artist=track.artist,
                source=PlatformSource.YOUTUBE,
                url=f"ytsearch1:{track.artist} {track.title}",
                bpm=track.bpm
            )
            
            filepath = await youtube.download(youtube_track, self._download_path)
            
            if os.path.exists(filepath):
                return DownloadResponse(
                    status="ready",
                    filepath=filepath,
                    track=track
                )
            else:
                return DownloadResponse(
                    status="error",
                    error="Fichier non créé"
                )
                
        except Exception as e:
            return DownloadResponse(
                status="error",
                error=str(e)
            )


# Singleton
download_service = DownloadService()
```

---

## 6. API Principal

### `app/main.py`

```python
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from app.models.track import (
    Track,
    PlatformSource,
    SearchResponse,
    DownloadRequest,
    DownloadResponse
)
from app.services.search_service import search_service
from app.services.download_service import download_service
from app.config import settings


app = FastAPI(
    title="DJ API",
    description="API multi-plateforme pour rechercher et télécharger de la musique",
    version="1.0.0"
)

# CORS pour Mixxx
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# ROUTES INFO
# ============================================

@app.get("/")
async def root():
    return {
        "name": "DJ API",
        "version": "1.0.0",
        "platforms": search_service.available_platforms
    }


@app.get("/platforms")
async def get_platforms():
    """Liste des plateformes disponibles"""
    platforms_info = []
    
    for source in PlatformSource:
        platform = search_service.get_platform(source)
        if platform:
            platforms_info.append({
                "name": source.value,
                "available": platform.is_available,
                "supports_download": platform.supports_download,
                "supports_bpm": platform.supports_bpm
            })
    
    return {"platforms": platforms_info}


# ============================================
# ROUTES RECHERCHE
# ============================================

@app.get("/search", response_model=SearchResponse)
async def search_all(
    q: str = Query(..., description="Terme de recherche"),
    limit: int = Query(10, ge=1, le=50, description="Limite par plateforme"),
    platforms: Optional[str] = Query(None, description="Plateformes séparées par virgule")
):
    """
    Recherche sur toutes les plateformes.
    
    Exemple: /search?q=daft punk&limit=5&platforms=spotify,deezer
    """
    platform_list = None
    if platforms:
        try:
            platform_list = [PlatformSource(p.strip()) for p in platforms.split(",")]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Plateforme invalide: {e}")
    
    results = await search_service.search_all(q, limit, platform_list)
    
    return SearchResponse(
        query=q,
        total_results=len(results),
        results=results
    )


@app.get("/search/{platform}", response_model=SearchResponse)
async def search_platform(
    platform: PlatformSource,
    q: str = Query(..., description="Terme de recherche"),
    limit: int = Query(20, ge=1, le=50)
):
    """
    Recherche sur une plateforme spécifique.
    
    Exemple: /search/spotify?q=daft punk
    """
    results = await search_service.search_platform(q, platform, limit)
    
    return SearchResponse(
        query=q,
        total_results=len(results),
        results=results
    )


# ============================================
# ROUTES TRACK
# ============================================

@app.get("/track/{source}/{track_id}", response_model=Track)
async def get_track(source: PlatformSource, track_id: str):
    """
    Récupère les informations d'un track.
    
    Exemple: /track/spotify/4uLU6hMCjMI75M1A2tKUQC
    """
    track = await search_service.get_track(track_id, source)
    
    if not track:
        raise HTTPException(status_code=404, detail="Track non trouvé")
    
    return track


# ============================================
# ROUTES TÉLÉCHARGEMENT
# ============================================

@app.post("/download", response_model=DownloadResponse)
async def download_track(request: DownloadRequest):
    """
    Télécharge un track.
    
    Body:
    {
        "url": "https://...",
        "source": "soundcloud",
        "track_id": "sc_123456"
    }
    """
    result = await download_service.download_track(
        track_id=request.track_id,
        source=request.source,
        url=request.url
    )
    
    if result.status == "error":
        raise HTTPException(status_code=500, detail=result.error)
    
    return result


@app.get("/download/{source}/{track_id}", response_model=DownloadResponse)
async def download_track_get(source: PlatformSource, track_id: str):
    """
    Télécharge un track (méthode GET pour faciliter l'intégration).
    
    Exemple: /download/soundcloud/sc_123456
    """
    result = await download_service.download_track(
        track_id=track_id,
        source=source
    )
    
    if result.status == "error":
        raise HTTPException(status_code=500, detail=result.error)
    
    return result


# ============================================
# DÉMARRAGE
# ============================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## 7. Lancer l'API

### Installation

```bash
# Créer l'environnement
cd dj-api
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements.txt

# Configurer le .env
cp .env.example .env
# Éditer .env avec tes clés API
```

### Démarrage

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Tester

```bash
# Voir les plateformes
curl http://localhost:8000/platforms

# Rechercher sur toutes les plateformes
curl "http://localhost:8000/search?q=daft%20punk&limit=5"

# Rechercher sur Deezer uniquement
curl "http://localhost:8000/search/deezer?q=daft%20punk"

# Télécharger
curl "http://localhost:8000/download/deezer/dz_3135556"
```

---

## 8. Documentation API

Une fois lancée, accède à :
- **Swagger UI** : http://localhost:8000/docs
- **ReDoc** : http://localhost:8000/redoc

---

## Prochaine étape : Intégration Mixxx

Tu veux que je t'aide maintenant à créer le **script Mixxx** qui va communiquer avec cette API ? 🎧