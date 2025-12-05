import httpx
import asyncio
from typing import Optional
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, ExtractorError
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
                print("[SoundCloud] ⚠️ Query vide après décodage")
                return []
            
            print(f"[SoundCloud] 🔍 Recherche: '{decoded_query}'")
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'ignoreerrors': True,
                'socket_timeout': 30,
                'extractor_retries': 3,
            }
            
            search_url = f"scsearch{limit}:{decoded_query}"
            
            try:
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: self._search_sync(search_url, ydl_opts)
                    ),
                    timeout=45.0
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
            print(f"[SoundCloud] 📡 URL: {search_url}")
            
            with YoutubeDL(ydl_opts) as ydl:
                try:
                    data = ydl.extract_info(search_url, download=False)
                except (DownloadError, ExtractorError) as e:
                    print(f"[SoundCloud] ❌ Erreur yt-dlp: {e}")
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
                        print(f"data raw : {entry}")
                        track_id = entry.get('id')
                        title = entry.get("title")
                        
                        if not track_id or not title:
                            continue
                        
                        # ⚠️ IMPORTANT: Stocker l'URL complète !
                        track_url = (
                            entry.get("webpage_url") or 
                            entry.get("url") or 
                            entry.get("original_url") or 
                            ""
                        )
                        
                        track = Track(
                            id=f"sc_{track_id}",
                            title=title,
                            artist=entry.get("uploader") or entry.get("channel") or "Unknown",
                            source=PlatformSource.SOUNDCLOUD,
                            url=track_url,
                            duration=int(entry.get("duration") or 0),
                            artwork_url= self._get_best_thumbnail(entry),
                            genre=entry.get("genre"),
                            bpm=None
                        )                    
                        
                        if not track.url:
                            print(f"[SoundCloud] ⚠️ Pas d'URL pour '{title}'")
                            continue
                        
                        tracks.append(track)
                        
                    except Exception as e:
                        print(f"[SoundCloud] ⚠️ Erreur sur entrée {idx}: {e}")
                        continue
            
            print(f"[SoundCloud] ✅ {len(tracks)} tracks valides")
            
        except Exception as e:
            print(f"[SoundCloud] ❌ ERREUR _search_sync: {type(e).__name__}: {e}")
            traceback.print_exc()
        
        return tracks
    
    async def get_track(self, track_id: str) -> Optional[Track]:
        """
        Récupère un track par son ID ou URL.
        
        Accepte:
        - "sc_123456789" (ID avec préfixe)
        - "123456789" (ID seul)  
        - "https://soundcloud.com/artist/track" (URL complète)
        """
        
        try:
            print(f"[SoundCloud] 🔍 get_track: {track_id}")
            
            # Décoder
            track_id = unquote(track_id).strip()
            
            if not track_id:
                print("[SoundCloud] ❌ track_id vide")
                return None
            
            # Déterminer l'URL à utiliser
            if track_id.startswith("http"):
                # URL complète fournie directement
                url = track_id
                print(f"[SoundCloud] 🔗 URL directe: {url}")
                
            elif track_id.startswith("sc_"):
                # ID avec préfixe → extraire l'ID numérique
                numeric_id = track_id[3:]
                
                if not numeric_id:
                    print("[SoundCloud] ❌ ID vide après préfixe sc_")
                    return None
                
                # Utiliser l'URL API SoundCloud (yt-dlp sait la gérer)
                url = f"https://api.soundcloud.com/tracks/{numeric_id}"
                print(f"[SoundCloud] 🔗 URL construite depuis ID: {url}")
                
            else:
                # ID seul (sans préfixe)
                url = f"https://api.soundcloud.com/tracks/{track_id}"
                print(f"[SoundCloud] 🔗 URL construite: {url}")
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': False,
                'socket_timeout': 30,
            }
            
            loop = asyncio.get_event_loop()
            
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: self._get_track_sync(url, ydl_opts)
                    ),
                    timeout=30.0
                )
                
                if result:
                    print(f"[SoundCloud] ✅ Track trouvée: {result.artist} - {result.title}")
                else:
                    print(f"[SoundCloud] ❌ Track non trouvée")
                
                return result
                
            except asyncio.TimeoutError:
                print(f"[SoundCloud] ⏱️ Timeout get_track")
                return None
                
        except Exception as e:
            print(f"[SoundCloud] ❌ ERREUR get_track: {type(e).__name__}: {e}")
            traceback.print_exc()
            return None

    def _get_track_sync(self, url: str, ydl_opts: dict) -> Optional[Track]:
        """Récupération synchrone"""
        try:
            print(f"[SoundCloud] 📡 Extraction depuis: {url}")
            
            with YoutubeDL(ydl_opts) as ydl:
                data = ydl.extract_info(url, download=False)
                
                if not data:
                    print("[SoundCloud] ⚠️ Aucune donnée retournée par yt-dlp")
                    return None
                
                track_id = data.get('id', '')
                
                if not track_id:
                    print("[SoundCloud] ⚠️ Pas d'ID dans les données")
                    return None
                
                # Construire l'URL finale (préférer webpage_url)
                final_url = data.get("webpage_url") or data.get("url") or url
                
                track = Track(
                    id=self.generate_track_id(str(track_id)),
                    title=data.get("title", "Unknown"),
                    artist=data.get("uploader") or data.get("channel") or "Unknown",
                    source=self.platform_name,
                    url=final_url,
                    duration=int(data.get("duration") or 0),
                    artwork_url= self._get_best_thumbnail(entry),
                    genre=data.get("genre"),
                    bpm=None
                )
                
                print(f"[SoundCloud] ✅ Track parsée: {track.title} (URL: {track.url[:50]}...)")
                return track
                
        except (DownloadError, ExtractorError) as e:
            print(f"[SoundCloud] ❌ Erreur yt-dlp: {e}")
            return None
            
        except Exception as e:
            print(f"[SoundCloud] ❌ Erreur _get_track_sync: {type(e).__name__}: {e}")
            traceback.print_exc()
            return None

    async def download(self, track: Track, output_path: str) -> str:
        """Télécharge une track"""
        
        try:
            print(f"[SoundCloud] ⬇️ Téléchargement: {track.artist} - {track.title}")
            print(f"[SoundCloud] 🔗 URL: {track.url}")
            
            # Validation
            if not track.url:
                raise ValueError("URL de track manquante")
            
            # Créer le dossier si nécessaire
            os.makedirs(output_path, exist_ok=True)
            
            filename = self.sanitize_filename(f"{track.artist} - {track.title}")
            filepath = os.path.join(output_path, filename)
            
            # Vérifier si déjà téléchargé
            final_path = f"{filepath}.mp3"
            if os.path.exists(final_path):
                file_size = os.path.getsize(final_path)
                print(f"[SoundCloud] ℹ️ Fichier existe déjà ({file_size / 1024 / 1024:.2f} MB)")
                return final_path
            
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
                'ignoreerrors': False,
                'socket_timeout': 60,
                'retries': 3,
            }
            
            loop = asyncio.get_event_loop()
            
            await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self._download_sync(track.url, ydl_opts)
                ),
                timeout=300.0  # 5 minutes max
            )
            
            # Vérifier que le fichier a été créé
            if os.path.exists(final_path):
                file_size = os.path.getsize(final_path)
                print(f"[SoundCloud] ✅ Téléchargé: {final_path} ({file_size / 1024 / 1024:.2f} MB)")
                return final_path
            else:
                # Chercher d'autres extensions
                for ext in ['.opus', '.m4a', '.webm', '.ogg']:
                    alt_path = f"{filepath}{ext}"
                    if os.path.exists(alt_path):
                        print(f"[SoundCloud] ⚠️ Extension différente: {alt_path}")
                        return alt_path
                
                raise FileNotFoundError(f"Fichier non créé: {final_path}")
                
        except asyncio.TimeoutError:
            print(f"[SoundCloud] ⏱️ Timeout téléchargement (>5min)")
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
            print(f"[SoundCloud] 🎬 Lancement yt-dlp...")
            
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            print(f"[SoundCloud] ✅ yt-dlp terminé")
            
        except (DownloadError, ExtractorError) as e:
            print(f"[SoundCloud] ❌ Erreur yt-dlp: {e}")
            raise
            
        except Exception as e:
            print(f"[SoundCloud] ❌ Erreur _download_sync: {e}")
            raise

    def _get_best_thumbnail(self, data: dict) -> Optional[str]:
        """
        Extrait la meilleure thumbnail depuis les données SoundCloud.
        
        Priorité:
        1. t300x300 (medium - 300x300)
        2. large (100x100)
        3. crop (400x400)
        4. t500x500 (500x500)
        5. Première disponible
        """
        
        try:
            thumbnails = data.get("thumbnails", [])
            
            if not thumbnails:
                # Fallback sur "thumbnail" simple si pas de liste
                return data.get("thumbnail")
            
            if not isinstance(thumbnails, list):
                return data.get("thumbnail")
            
            # Ordre de préférence des tailles
            preferred_sizes = ['t300x300', 'large', 'crop', 't500x500', 't67x67', 'small']
            
            # Créer un dictionnaire id -> url pour accès rapide
            thumb_map = {}
            for thumb in thumbnails:
                if isinstance(thumb, dict) and thumb.get('id') and thumb.get('url'):
                    thumb_map[thumb['id']] = thumb['url']
            
            # Chercher dans l'ordre de préférence
            for size in preferred_sizes:
                if size in thumb_map:
                    print(f"[SoundCloud] 🖼️ Thumbnail trouvée: {size}")
                    return thumb_map[size]
            
            # Fallback: prendre la première avec une URL
            for thumb in thumbnails:
                if isinstance(thumb, dict) and thumb.get('url'):
                    print(f"[SoundCloud] 🖼️ Thumbnail fallback: {thumb.get('id', 'unknown')}")
                    return thumb['url']
            
            return None
            
        except Exception as e:
            print(f"[SoundCloud] ⚠️ Erreur extraction thumbnail: {e}")
            return data.get("thumbnail")