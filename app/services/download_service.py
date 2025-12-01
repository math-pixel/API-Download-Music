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