import httpx
import asyncio
from typing import Optional
from yt_dlp import YoutubeDL
import os
from urllib.parse import unquote
import traceback

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
        return False

    
    # ============================================
    # MÉTHODES PRINCIPALES
    # ============================================
    
    async def search(self, query: str, limit: int = 20) -> list[Track]:
        """Recherche via yt-dlp avec gestion d'erreurs complète"""
        
        try:
            # Décoder et nettoyer la query
            decoded_query = unquote(query).strip()
            
            if not decoded_query:
                print("[SoundCloud] Query vide après décodage")
                return []
            
            print(f"[SoundCloud] 🔍 Recherche: '{decoded_query}'")
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'ignoreerrors': True,
                'socket_timeout': 30,  # Timeout socket
                'extractor_retries': 3,  # Retry automatique
            }
            
            search_url = f"scsearch{limit}:{decoded_query}"
            
            # Exécuter dans un thread avec timeout
            loop = asyncio.get_event_loop()
            
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: self._search_sync(search_url, ydl_opts)
                    ),
                    timeout=45.0  # Timeout total de 45 secondes
                )
                
                print(f"[SoundCloud] ✅ {len(result)} résultats trouvés")
                return result
                
            except asyncio.TimeoutError:
                print(f"[SoundCloud] ⏱️ Timeout après 45s pour '{decoded_query}'")
                return []
            
        except Exception as e:
            print(f"[SoundCloud] ❌ ERREUR search: {type(e).__name__}: {e}")
            traceback.print_exc()
            return []
    
    def _search_sync(self, search_url: str, ydl_opts: dict) -> list[Track]:
        """Recherche synchrone avec gestion d'erreurs"""
        tracks = []
        
        try:
            print(f"[SoundCloud] URL: {search_url}")
            
            with YoutubeDL(ydl_opts) as ydl:
                try:
                    data = ydl.extract_info(search_url, download=False)
                except Exception as e:
                    print(f"[SoundCloud] ❌ Erreur yt-dlp extract_info: {e}")
                    return []
                
                if not data:
                    print("[SoundCloud] ⚠️ Aucune donnée retournée")
                    return []
                
                entries = data.get("entries", [])
                
                if not entries:
                    print("[SoundCloud] ⚠️ Aucune entrée trouvée")
                    return []
                
                print(f"[SoundCloud] 📦 {len(entries)} entrées brutes")
                
                for idx, entry in enumerate(entries):
                    if not entry:
                        continue
                    
                    try:
                        # Validation des données
                        track_id = entry.get('id')
                        title = entry.get("title")
                        
                        if not track_id or not title:
                            print(f"[SoundCloud] ⚠️ Entrée {idx} invalide (pas d'ID ou titre)")
                            continue
                        
                        track = Track(
                            id=f"sc_{track_id}",
                            title=title,
                            artist=entry.get("uploader") or entry.get("channel") or "Unknown",
                            source=PlatformSource.SOUNDCLOUD,
                            url=entry.get("url") or entry.get("webpage_url") or entry.get("original_url") or "",
                            duration=int(entry.get("duration") or 0),
                        )
                        
                        # Validation finale
                        if not track.url:
                            print(f"[SoundCloud] ⚠️ Pas d'URL pour '{title}'")
                            continue
                        
                        tracks.append(track)
                        
                    except Exception as e:
                        print(f"[SoundCloud] ⚠️ Erreur sur entrée {idx}: {e}")
                        continue
            
            print(f"[SoundCloud] ✅ {len(tracks)} tracks valides extraites")
            
        except Exception as e:
            print(f"[SoundCloud] ❌ ERREUR _search_sync: {type(e).__name__}: {e}")
            traceback.print_exc()
        
        return tracks
    
    async def get_track(self, track_id: str) -> Optional[Track]:
        """Récupère un track par ID ou URL"""
        
        try:
            print(f"[SoundCloud] 🔍 get_track: {track_id}")
            
            # Décoder
            track_id = unquote(track_id).strip()
            
            if not track_id:
                print("[SoundCloud] ❌ track_id vide")
                return None
            
            # Déterminer l'URL
            if track_id.startswith("http"):
                url = track_id
            elif track_id.startswith("sc_"):
                # Pour SoundCloud, on ne peut pas construire l'URL directement
                # Il faut chercher par ID ou avoir l'URL complète
                print(f"[SoundCloud] ⚠️ ID avec préfixe '{track_id}' - besoin de l'URL complète")
                return None
            else:
                print(f"[SoundCloud] ⚠️ Format d'ID non reconnu: {track_id}")
                return None
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': False,
                'socket_timeout': 30,
            }
            
            loop = asyncio.get_event_loop()
            
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self._get_track_sync(url, ydl_opts)
                ),
                timeout=30.0
            )
            
            if result:
                print(f"[SoundCloud] ✅ Track trouvée: {result.title}")
            else:
                print(f"[SoundCloud] ❌ Track non trouvée")
            
            return result
            
        except asyncio.TimeoutError:
            print(f"[SoundCloud] ⏱️ Timeout get_track pour {track_id}")
            return None
        except Exception as e:
            print(f"[SoundCloud] ❌ ERREUR get_track: {type(e).__name__}: {e}")
            traceback.print_exc()
            return None

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
                    artist=data.get("uploader") or data.get("channel") or "Unknown",
                    source=self.platform_name,
                    url=data.get("webpage_url") or url,
                    duration=int(data.get("duration") or 0),
                    artwork_url=data.get("thumbnail"),
                    genre=data.get("genre"),
                    bpm=None
                )
                
        except Exception as e:
            print(f"[SoundCloud] ❌ Erreur _get_track_sync: {e}")
            return None

    async def download(self, track: Track, output_path: str) -> str:
        """Télécharge une track"""
        
        try:
            print(f"[SoundCloud] ⬇️ Téléchargement: {track.artist} - {track.title}")
            
            if not track.url:
                raise ValueError("URL de track manquante")
            
            filename = self.sanitize_filename(f"{track.artist} - {track.title}")
            filepath = os.path.join(output_path, filename)
            
            # Créer le dossier si nécessaire
            os.makedirs(output_path, exist_ok=True)
            
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
                'socket_timeout': 60,
            }
            
            loop = asyncio.get_event_loop()
            
            await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self._download_sync(track.url, ydl_opts)
                ),
                timeout=300.0  # 5 minutes max
            )
            
            output_file = f"{filepath}.mp3"
            
            if os.path.exists(output_file):
                print(f"[SoundCloud] ✅ Téléchargé: {output_file}")
                return output_file
            else:
                raise FileNotFoundError(f"Fichier non créé: {output_file}")
                
        except asyncio.TimeoutError:
            print(f"[SoundCloud] ⏱️ Timeout téléchargement")
            raise Exception("Timeout lors du téléchargement")
        except Exception as e:
            print(f"[SoundCloud] ❌ ERREUR download: {type(e).__name__}: {e}")
            traceback.print_exc()
            raise
    
    async def get_bpm(self, track: Track) -> Optional[float]:
        return None

    def _download_sync(self, url: str, ydl_opts: dict):
        """Téléchargement synchrone"""
        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            print(f"[SoundCloud] ❌ Erreur _download_sync: {e}")
            raise