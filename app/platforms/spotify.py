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