import httpx
from typing import Optional
import asyncio
from yt_dlp import YoutubeDL
import os
from urllib.parse import unquote
import traceback

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
        return True
    
    @property
    def supports_download(self) -> bool:
        return True
    
    @property
    def supports_bpm(self) -> bool:
        return True
    
    # ============================================
    # MÉTHODES PRINCIPALES
    # ============================================
    
    async def search(self, query: str, limit: int = 20) -> list[Track]:
        """Recherche avec gestion d'erreurs complète"""
        
        try:
            # Décoder et nettoyer la query
            decoded_query = unquote(query).strip()
            
            if not decoded_query:
                print("[Deezer] ⚠️ Query vide après décodage")
                return []
            
            # Limiter la taille de la query
            if len(decoded_query) > 500:
                print("[Deezer] ⚠️ Query trop longue, truncation à 500 caractères")
                decoded_query = decoded_query[:500]
            
            print(f"[Deezer] 🔍 Recherche: '{decoded_query}' (limit: {limit})")
            
            # Valider la limite
            limit = max(1, min(limit, 100))  # Entre 1 et 100
            
            async with httpx.AsyncClient() as client:
                try:
                    # Timeout de 15 secondes pour la requête API
                    response = await asyncio.wait_for(
                        client.get(
                            f"{self._base_url}/search",
                            params={
                                "q": decoded_query,
                                "limit": limit
                            },
                            timeout=10.0
                        ),
                        timeout=15.0
                    )
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    # Vérifier la structure de la réponse
                    if not isinstance(data, dict):
                        print(f"[Deezer] ⚠️ Réponse invalide (pas un dict): {type(data)}")
                        return []
                    
                    items = data.get("data", [])
                    
                    if not items:
                        print(f"[Deezer] ℹ️ Aucun résultat pour '{decoded_query}'")
                        return []
                    
                    print(f"[Deezer] 📦 {len(items)} résultats bruts")
                    
                    # Parser les tracks
                    tracks = []
                    for idx, item in enumerate(items):
                        if not item or not isinstance(item, dict):
                            print(f"[Deezer] ⚠️ Item {idx} invalide")
                            continue
                        
                        try:
                            track = self._parse_track(item)
                            
                            if not track:
                                print(f"[Deezer] ⚠️ Parsing échoué pour item {idx}")
                                continue
                            
                            # Récupérer le BPM (optionnel, non bloquant)
                            track_id = item.get("id")
                            if track_id:
                                try:
                                    bpm = await asyncio.wait_for(
                                        self._get_bpm_from_id(str(track_id)),
                                        timeout=3.0
                                    )
                                    track.bpm = bpm
                                except asyncio.TimeoutError:
                                    print(f"[Deezer] ⏱️ Timeout BPM pour track {track_id}")
                                except Exception as e:
                                    print(f"[Deezer] ⚠️ Erreur BPM pour track {track_id}: {e}")
                            
                            tracks.append(track)
                            
                        except Exception as e:
                            print(f"[Deezer] ⚠️ Erreur sur item {idx}: {type(e).__name__}: {e}")
                            continue
                    
                    print(f"[Deezer] ✅ {len(tracks)} tracks valides extraites")
                    return tracks
                    
                except asyncio.TimeoutError:
                    print(f"[Deezer] ⏱️ Timeout après 15s pour '{decoded_query}'")
                    return []
                    
                except httpx.HTTPStatusError as e:
                    print(f"[Deezer] ❌ Erreur HTTP {e.response.status_code}: {e}")
                    return []
                    
                except httpx.RequestError as e:
                    print(f"[Deezer] ❌ Erreur réseau: {e}")
                    return []
                    
        except Exception as e:
            print(f"[Deezer] ❌ ERREUR search: {type(e).__name__}: {e}")
            traceback.print_exc()
            return []
    
    async def get_track(self, track_id: str) -> Optional[Track]:
        """Récupère un track par ID avec validation"""
        
        try:
            print(f"[Deezer] 🔍 get_track: {track_id}")
            
            # Décoder et nettoyer
            track_id = unquote(track_id).strip()
            
            if not track_id:
                print("[Deezer] ❌ track_id vide")
                return None
            
            # Enlever le préfixe si présent
            if track_id.startswith("dz_"):
                track_id = track_id[3:]
            
            # Valider que c'est un ID numérique
            if not track_id.isdigit():
                print(f"[Deezer] ⚠️ ID non numérique: {track_id}")
                return None
            
            async with httpx.AsyncClient() as client:
                try:
                    response = await asyncio.wait_for(
                        client.get(
                            f"{self._base_url}/track/{track_id}",
                            timeout=10.0
                        ),
                        timeout=15.0
                    )
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    # Vérifier les erreurs Deezer
                    if isinstance(data, dict) and "error" in data:
                        error = data["error"]
                        print(f"[Deezer] ❌ API Error: {error.get('message', 'Unknown')}")
                        return None
                    
                    track = self._parse_track_full(data)
                    
                    if track:
                        print(f"[Deezer] ✅ Track trouvée: {track.artist} - {track.title}")
                    else:
                        print(f"[Deezer] ❌ Parsing échoué pour ID {track_id}")
                    
                    return track
                    
                except asyncio.TimeoutError:
                    print(f"[Deezer] ⏱️ Timeout get_track pour {track_id}")
                    return None
                    
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        print(f"[Deezer] ℹ️ Track {track_id} non trouvée (404)")
                    else:
                        print(f"[Deezer] ❌ HTTP {e.response.status_code}: {e}")
                    return None
                    
                except httpx.RequestError as e:
                    print(f"[Deezer] ❌ Erreur réseau: {e}")
                    return None
                    
        except Exception as e:
            print(f"[Deezer] ❌ ERREUR get_track: {type(e).__name__}: {e}")
            traceback.print_exc()
            return None
    
    async def download(self, track: Track, output_path: str) -> str:
        """Télécharge via yt-dlp (cherche sur YouTube) avec protection"""
        
        try:
            print(f"[Deezer] ⬇️ Téléchargement: {track.artist} - {track.title}")
            
            # Validation
            if not track.artist or not track.title:
                raise ValueError("Artiste ou titre manquant")
            
            # Créer le dossier si nécessaire
            os.makedirs(output_path, exist_ok=True)
            
            filename = self.sanitize_filename(f"{track.artist} - {track.title}")
            filepath = os.path.join(output_path, filename)
            
            # Vérifier si déjà téléchargé
            final_path = f"{filepath}.mp3"
            if os.path.exists(final_path):
                print(f"[Deezer] ℹ️ Fichier existe déjà: {final_path}")
                return final_path
            
            # Recherche sur YouTube avec le titre
            search_query = f"ytsearch1:{track.artist} {track.title}"
            print(f"[Deezer] 🎬 Recherche YouTube: {search_query}")
            
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f"{filepath}.%(ext)s",
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
                'quiet': False,
                'no_warnings': False,
                'ignoreerrors': False,  # Ne pas ignorer les erreurs pour le download
                'socket_timeout': 60,
                'retries': 3,
            }
            
            loop = asyncio.get_event_loop()
            
            # Timeout de 5 minutes pour le téléchargement
            await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self._download_sync(search_query, ydl_opts)
                ),
                timeout=300.0
            )
            
            # Vérifier que le fichier a été créé
            if os.path.exists(final_path):
                file_size = os.path.getsize(final_path)
                print(f"[Deezer] ✅ Téléchargé: {final_path} ({file_size / 1024 / 1024:.2f} MB)")
                return final_path
            else:
                raise FileNotFoundError(f"Fichier non créé: {final_path}")
                
        except asyncio.TimeoutError:
            print(f"[Deezer] ⏱️ Timeout téléchargement (>5min)")
            raise Exception("Timeout lors du téléchargement")
            
        except Exception as e:
            print(f"[Deezer] ❌ ERREUR download: {type(e).__name__}: {e}")
            traceback.print_exc()
            raise
    
    async def get_bpm(self, track: Track) -> Optional[float]:
        """Récupère le BPM avec gestion d'erreur"""
        
        try:
            if not track or not track.id:
                return None
            
            deezer_id = track.id.replace("dz_", "")
            
            if not deezer_id.isdigit():
                print(f"[Deezer] ⚠️ ID invalide pour BPM: {deezer_id}")
                return None
            
            return await asyncio.wait_for(
                self._get_bpm_from_id(deezer_id),
                timeout=5.0
            )
            
        except asyncio.TimeoutError:
            print(f"[Deezer] ⏱️ Timeout get_bpm")
            return None
            
        except Exception as e:
            print(f"[Deezer] ⚠️ Erreur get_bpm: {e}")
            return None
    
    # ============================================
    # MÉTHODES PRIVÉES
    # ============================================
    
    async def _get_bpm_from_id(self, track_id: str) -> Optional[float]:
        """Récupère le BPM depuis l'API Deezer"""
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._base_url}/track/{track_id}",
                    timeout=10.0
                )
                
                response.raise_for_status()
                data = response.json()
                
                # Vérifier les erreurs
                if isinstance(data, dict) and "error" in data:
                    return None
                
                bpm = data.get("bpm")
                
                if bpm is not None and bpm > 0:
                    return float(bpm)
                
                return None
                
        except Exception as e:
            print(f"[Deezer] ⚠️ Erreur _get_bpm_from_id: {e}")
            return None
    
    def _parse_track(self, data: dict) -> Optional[Track]:
        """Parse une track depuis les résultats de recherche"""
        
        try:
            # Validation des données essentielles
            track_id = data.get("id")
            title = data.get("title")
            
            if not track_id or not title:
                print(f"[Deezer] ⚠️ Données manquantes: id={track_id}, title={title}")
                return None
            
            # Extraire l'artiste
            artist_data = data.get("artist", {})
            
            if not isinstance(artist_data, dict):
                print(f"[Deezer] ⚠️ Format artist invalide: {type(artist_data)}")
                artist_name = "Unknown Artist"
            else:
                artist_name = artist_data.get("name", "Unknown Artist")
            
            # Extraire l'album
            album_data = data.get("album", {})
            
            if isinstance(album_data, dict):
                artwork_url = (
                    album_data.get("cover_xl") or 
                    album_data.get("cover_big") or 
                    album_data.get("cover_medium") or
                    None
                )
            else:
                artwork_url = None
            
            # Duration
            duration = data.get("duration", 0)
            if not isinstance(duration, (int, float)):
                duration = 0
            
            track = Track(
                id=f"dz_{track_id}",
                title=str(title),
                artist=str(artist_name),
                source=self.platform_name,
                url=data.get("link", ""),
                bpm=None,  # Sera rempli après si demandé
                duration=int(duration),
                artwork_url=artwork_url,
                genre=None
            )
            
            return track
            
        except Exception as e:
            print(f"[Deezer] ❌ Erreur _parse_track: {type(e).__name__}: {e}")
            traceback.print_exc()
            return None
    
    def _parse_track_full(self, data: dict) -> Optional[Track]:
        """Parse une track complète (endpoint /track/{id})"""
        
        try:
            # Vérifier si c'est une erreur
            if not isinstance(data, dict):
                print(f"[Deezer] ⚠️ Data invalide: {type(data)}")
                return None
            
            if "error" in data:
                print(f"[Deezer] ⚠️ Erreur API: {data['error']}")
                return None
            
            # Validation des données essentielles
            track_id = data.get("id")
            title = data.get("title")
            
            if not track_id or not title:
                print(f"[Deezer] ⚠️ Données manquantes: id={track_id}, title={title}")
                return None
            
            # Extraire l'artiste
            artist_data = data.get("artist", {})
            
            if isinstance(artist_data, dict):
                artist_name = artist_data.get("name", "Unknown Artist")
            else:
                artist_name = "Unknown Artist"
            
            # Extraire l'album
            album_data = data.get("album", {})
            
            if isinstance(album_data, dict):
                artwork_url = (
                    album_data.get("cover_xl") or 
                    album_data.get("cover_big") or 
                    album_data.get("cover_medium") or
                    None
                )
            else:
                artwork_url = None
            
            # BPM avec validation
            bpm = data.get("bpm")
            if bpm is not None and isinstance(bpm, (int, float)) and bpm > 0:
                bpm = float(bpm)
            else:
                bpm = None
            
            # Duration
            duration = data.get("duration", 0)
            if not isinstance(duration, (int, float)):
                duration = 0
            
            track = Track(
                id=f"dz_{track_id}",
                title=str(title),
                artist=str(artist_name),
                source=self.platform_name,
                url=data.get("link", ""),
                bpm=bpm,
                duration=int(duration),
                artwork_url=artwork_url,
                genre=None
            )
            
            return track
            
        except Exception as e:
            print(f"[Deezer] ❌ Erreur _parse_track_full: {type(e).__name__}: {e}")
            traceback.print_exc()
            return None
    
    def _download_sync(self, url: str, ydl_opts: dict):
        """Téléchargement synchrone avec yt-dlp"""
        
        try:
            print(f"[Deezer] 🎬 Lancement yt-dlp...")
            
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            print(f"[Deezer] ✅ yt-dlp terminé")
            
        except Exception as e:
            print(f"[Deezer] ❌ Erreur _download_sync: {type(e).__name__}: {e}")
            traceback.print_exc()
            raise