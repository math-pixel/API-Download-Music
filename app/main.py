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