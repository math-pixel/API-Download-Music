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