import asyncio
from typing import Optional
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, ExtractorError
import os
from urllib.parse import unquote
import traceback
import re

from app.interfaces.download_interface import DownloadInterface
from app.models.track import Track, PlatformSource
from app.config import settings


class YouTubePlatform(DownloadInterface):
    
    def __init__(self):
        self._api_key = getattr(settings, 'youtube_api_key', None)
    
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
        return False
    
    # ============================================
    # MÉTHODES PRINCIPALES
    # ============================================
    
    async def search(self, query: str, limit: int = 20) -> list[Track]:
        """Recherche YouTube avec gestion d'erreurs complète"""
        
        try:
            # Décoder et nettoyer la query
            decoded_query = unquote(query).strip()
            
            if not decoded_query:
                print("[YouTube] ⚠️ Query vide après décodage")
                return []
            
            # Limiter la taille de la query
            if len(decoded_query) > 500:
                print("[YouTube] ⚠️ Query trop longue, truncation à 500 caractères")
                decoded_query = decoded_query[:500]
            
            # Nettoyer les caractères problématiques
            decoded_query = self._sanitize_query(decoded_query)
            
            # Valider la limite
            limit = max(1, min(limit, 50))
            
            print(f"[YouTube] 🔍 Recherche: '{decoded_query}' (limit: {limit})")
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'force_generic_extractor': False,
                'ignoreerrors': True,
                'no_playlist': True,
                'socket_timeout': 30,
                'extractor_retries': 3,
            }
            
            # Exécuter la recherche avec timeout
            loop = asyncio.get_event_loop()
            
            try:
                results = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: self._search_sync(decoded_query, limit, ydl_opts)
                    ),
                    timeout=45.0
                )
                
                print(f"[YouTube] ✅ {len(results)} tracks trouvées")
                return results
                
            except asyncio.TimeoutError:
                print(f"[YouTube] ⏱️ Timeout après 45s pour '{decoded_query}'")
                return []
            
        except Exception as e:
            print(f"[YouTube] ❌ ERREUR search: {type(e).__name__}: {e}")
            traceback.print_exc()
            return []
    
    def _search_sync(self, query: str, limit: int, ydl_opts: dict) -> list[Track]:
        """Recherche synchrone avec gestion d'erreurs"""
        
        tracks = []
        search_url = f"ytsearch{limit}:{query}"
        
        try:
            print(f"[YouTube] 📡 URL: {search_url}")
            
            with YoutubeDL(ydl_opts) as ydl:
                try:
                    result = ydl.extract_info(search_url, download=False)
                except (DownloadError, ExtractorError) as e:
                    print(f"[YouTube] ❌ Erreur yt-dlp: {e}")
                    return []
                except Exception as e:
                    print(f"[YouTube] ❌ Erreur extraction: {e}")
                    return []
                
                if not result:
                    print("[YouTube] ⚠️ Aucun résultat retourné")
                    return []
                
                entries = result.get("entries", [])
                
                if not entries:
                    print("[YouTube] ⚠️ Aucune entrée trouvée")
                    return []
                
                print(f"[YouTube] 📦 {len(entries)} entrées brutes")
                
                for idx, entry in enumerate(entries):
                    if not entry:
                        continue
                    
                    try:
                        track = self._parse_track(entry)
                        
                        if track:
                            tracks.append(track)
                        
                    except Exception as e:
                        print(f"[YouTube] ⚠️ Erreur parsing entrée {idx}: {e}")
                        continue
            
            print(f"[YouTube] ✅ {len(tracks)} tracks valides extraites")
            
        except Exception as e:
            print(f"[YouTube] ❌ ERREUR _search_sync: {type(e).__name__}: {e}")
            traceback.print_exc()
        
        return tracks
    
    async def get_track(self, track_id: str) -> Optional[Track]:
        """Récupère un track par ID avec validation"""
        
        try:
            print(f"[YouTube] 🔍 get_track: {track_id}")
            
            # Décoder et nettoyer
            track_id = unquote(track_id).strip()
            
            if not track_id:
                print("[YouTube] ❌ track_id vide")
                return None
            
            # Enlever le préfixe si présent
            if track_id.startswith("yt_"):
                track_id = track_id[3:]
            
            # Extraire l'ID si c'est une URL complète
            if track_id.startswith("http"):
                extracted_id = self._extract_video_id(track_id)
                if extracted_id:
                    track_id = extracted_id
                else:
                    print(f"[YouTube] ⚠️ Impossible d'extraire l'ID de l'URL: {track_id}")
                    return None
            
            # Valider le format de l'ID YouTube (11 caractères)
            if not self._is_valid_youtube_id(track_id):
                print(f"[YouTube] ⚠️ ID invalide: {track_id}")
                return None
            
            url = f"https://www.youtube.com/watch?v={track_id}"
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': False,
                'socket_timeout': 30,
            }
            
            loop = asyncio.get_event_loop()
            
            try:
                info = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: self._get_info_sync(url, ydl_opts)
                    ),
                    timeout=30.0
                )
                
                if info:
                    track = self._parse_track(info)
                    if track:
                        print(f"[YouTube] ✅ Track trouvée: {track.artist} - {track.title}")
                    return track
                else:
                    print(f"[YouTube] ❌ Aucune info pour: {track_id}")
                    return None
                    
            except asyncio.TimeoutError:
                print(f"[YouTube] ⏱️ Timeout get_track pour {track_id}")
                return None
                
        except Exception as e:
            print(f"[YouTube] ❌ ERREUR get_track: {type(e).__name__}: {e}")
            traceback.print_exc()
            return None
    
    def _get_info_sync(self, url: str, ydl_opts: dict) -> Optional[dict]:
        """Récupération synchrone des infos vidéo"""
        
        try:
            with YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
                
        except (DownloadError, ExtractorError) as e:
            print(f"[YouTube] ❌ Erreur yt-dlp: {e}")
            return None
            
        except Exception as e:
            print(f"[YouTube] ❌ Erreur _get_info_sync: {e}")
            return None
    
    async def download(self, track: Track, output_path: str) -> str:
        """Télécharge une vidéo YouTube en MP3 avec protection"""
        
        try:
            print(f"[YouTube] ⬇️ Téléchargement: {track.artist} - {track.title}")
            
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
                print(f"[YouTube] ℹ️ Fichier existe déjà: {final_path} ({file_size / 1024 / 1024:.2f} MB)")
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
                'fragment_retries': 3,
                'file_access_retries': 3,
            }
            
            loop = asyncio.get_event_loop()
            
            # Timeout de 10 minutes pour le téléchargement
            await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self._download_sync(track.url, ydl_opts)
                ),
                timeout=600.0
            )
            
            # Vérifier que le fichier a été créé
            if os.path.exists(final_path):
                file_size = os.path.getsize(final_path)
                
                # Vérifier que le fichier n'est pas vide
                if file_size < 1024:  # Moins de 1KB = probablement une erreur
                    os.remove(final_path)
                    raise Exception(f"Fichier téléchargé trop petit ({file_size} bytes)")
                
                print(f"[YouTube] ✅ Téléchargé: {final_path} ({file_size / 1024 / 1024:.2f} MB)")
                return final_path
            else:
                # Chercher d'autres extensions possibles
                for ext in ['.webm', '.m4a', '.opus', '.ogg']:
                    alt_path = f"{filepath}{ext}"
                    if os.path.exists(alt_path):
                        print(f"[YouTube] ⚠️ Fichier trouvé avec extension différente: {alt_path}")
                        return alt_path
                
                raise FileNotFoundError(f"Fichier non créé: {final_path}")
                
        except asyncio.TimeoutError:
            print(f"[YouTube] ⏱️ Timeout téléchargement (>10min)")
            raise Exception("Timeout lors du téléchargement")
            
        except Exception as e:
            print(f"[YouTube] ❌ ERREUR download: {type(e).__name__}: {e}")
            traceback.print_exc()
            raise
    
    def _download_sync(self, url: str, ydl_opts: dict):
        """Téléchargement synchrone avec yt-dlp"""
        
        try:
            print(f"[YouTube] 🎬 Lancement yt-dlp pour: {url}")
            
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            print(f"[YouTube] ✅ yt-dlp terminé")
            
        except (DownloadError, ExtractorError) as e:
            print(f"[YouTube] ❌ Erreur yt-dlp download: {e}")
            raise
            
        except Exception as e:
            print(f"[YouTube] ❌ Erreur _download_sync: {type(e).__name__}: {e}")
            raise
    
    async def get_bpm(self, track: Track) -> Optional[float]:
        """YouTube ne fournit pas le BPM"""
        return None
    
    # ============================================
    # MÉTHODES PRIVÉES
    # ============================================
    
    def _parse_track(self, data: dict) -> Optional[Track]:
        """Parse une track YouTube avec validation complète"""
        
        try:
            # Validation des données
            if not isinstance(data, dict):
                print(f"[YouTube] ⚠️ Data invalide: {type(data)}")
                return None
            
            video_id = data.get("id")
            title = data.get("title")
            
            if not video_id:
                print("[YouTube] ⚠️ Pas d'ID vidéo")
                return None
            
            if not title or title == "[Deleted video]" or title == "[Private video]":
                print(f"[YouTube] ⚠️ Vidéo supprimée ou privée: {video_id}")
                return None
            
            # Extraire l'artiste et le titre
            artist, parsed_title = self._parse_artist_title(
                title,
                data.get("uploader") or data.get("channel") or "Unknown Artist"
            )
            
            # Duration
            duration = data.get("duration")
            if duration is None:
                duration = 0
            elif not isinstance(duration, (int, float)):
                try:
                    duration = int(duration)
                except:
                    duration = 0
            
            # Artwork (thumbnail)
            artwork_url = None
            thumbnails = data.get("thumbnails", [])
            
            if isinstance(thumbnails, list) and thumbnails:
                # Prendre le thumbnail de meilleure qualité
                for thumb in reversed(thumbnails):
                    if isinstance(thumb, dict) and thumb.get("url"):
                        artwork_url = thumb["url"]
                        break
            
            if not artwork_url:
                artwork_url = data.get("thumbnail")
            
            # Construire l'URL
            if video_id.startswith("http"):
                url = video_id
            else:
                url = f"https://www.youtube.com/watch?v={video_id}"
            
            track = Track(
                id=f"yt_{video_id}",
                title=str(parsed_title),
                artist=str(artist),
                source=self.platform_name,
                url=url,
                bpm=None,
                duration=int(duration),
                artwork_url=artwork_url,
                genre=None
            )
            
            return track
            
        except Exception as e:
            print(f"[YouTube] ❌ Erreur _parse_track: {type(e).__name__}: {e}")
            traceback.print_exc()
            return None
    
    def _parse_artist_title(self, title: str, uploader: str) -> tuple[str, str]:
        """
        Parse le titre pour extraire artiste et titre.
        
        Formats supportés:
        - "Artiste - Titre"
        - "Artiste | Titre"
        - "Artiste — Titre" (tiret long)
        - "Titre (by Artiste)"
        - "Titre" (utilise uploader comme artiste)
        """
        
        try:
            title = title.strip()
            
            # Nettoyer le titre des suffixes courants
            suffixes_to_remove = [
                "(Official Video)", "(Official Music Video)", "(Official Audio)",
                "(Lyric Video)", "(Lyrics)", "(Audio)", "(Visualizer)",
                "[Official Video]", "[Official Music Video]", "[Official Audio]",
                "(HD)", "(HQ)", "(4K)", "(Clip officiel)", "(Official)",
                "| Official Video", "| Official Audio",
            ]
            
            for suffix in suffixes_to_remove:
                title = title.replace(suffix, "").strip()
            
            # Patterns de séparation
            separators = [" - ", " — ", " | ", " – "]
            
            for sep in separators:
                if sep in title:
                    parts = title.split(sep, 1)
                    if len(parts) == 2:
                        artist = parts[0].strip()
                        parsed_title = parts[1].strip()
                        
                        # Vérifier que les deux parties sont valides
                        if artist and parsed_title:
                            return (artist, parsed_title)
            
            # Pattern "Titre (by Artiste)" ou "Titre (feat. Artiste)"
            match = re.search(r'^(.+?)\s*[\(\[](by|feat\.?|ft\.?)\s*(.+?)[\)\]]', title, re.IGNORECASE)
            if match:
                return (match.group(3).strip(), match.group(1).strip())
            
            # Fallback: utiliser uploader comme artiste
            return (uploader, title)
            
        except Exception as e:
            print(f"[YouTube] ⚠️ Erreur _parse_artist_title: {e}")
            return (uploader, title)
    
    def _is_valid_youtube_id(self, video_id: str) -> bool:
        """Vérifie si l'ID est un ID YouTube valide"""
        
        if not video_id:
            return False
        
        # Les IDs YouTube font 11 caractères
        if len(video_id) != 11:
            return False
        
        # Caractères autorisés: a-z, A-Z, 0-9, -, _
        pattern = r'^[a-zA-Z0-9_-]{11}$'
        return bool(re.match(pattern, video_id))
    
    def _extract_video_id(self, url: str) -> Optional[str]:
        """Extrait l'ID vidéo d'une URL YouTube"""
        
        patterns = [
            # Standard: youtube.com/watch?v=ID
            r'(?:youtube\.com/watch\?v=|youtube\.com/watch\?.+&v=)([a-zA-Z0-9_-]{11})',
            # Court: youtu.be/ID
            r'youtu\.be/([a-zA-Z0-9_-]{11})',
            # Embed: youtube.com/embed/ID
            r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
            # Shorts: youtube.com/shorts/ID
            r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
            # Music: music.youtube.com/watch?v=ID
            r'music\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def _sanitize_query(self, query: str) -> str:
        """Nettoie la query pour éviter les problèmes avec yt-dlp"""
        
        # Remplacer les caractères problématiques
        replacements = {
            '\n': ' ',
            '\r': ' ',
            '\t': ' ',
            '"': '',
            "'": '',
        }
        
        for old, new in replacements.items():
            query = query.replace(old, new)
        
        # Supprimer les espaces multiples
        query = ' '.join(query.split())
        
        return query