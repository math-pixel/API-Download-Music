import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.exceptions import SpotifyException
from typing import Optional
import asyncio
from urllib.parse import unquote
import traceback
import time

from app.interfaces.download_interface import DownloadInterface
from app.models.track import Track, PlatformSource
from app.config import settings


class SpotifyPlatform(DownloadInterface):
    
    def __init__(self):
        self._client: Optional[spotipy.Spotify] = None
        self._last_auth_time: float = 0
        self._auth_retry_count: int = 0
        self._max_auth_retries: int = 3
        self._init_client()
    
    def _init_client(self) -> bool:
        """Initialise le client Spotify avec gestion d'erreurs"""
        
        try:
            # Vérifier les credentials
            if not settings.spotify_client_id:
                print("[Spotify] ⚠️ SPOTIFY_CLIENT_ID non configuré")
                return False
            
            if not settings.spotify_client_secret:
                print("[Spotify] ⚠️ SPOTIFY_CLIENT_SECRET non configuré")
                return False
            
            print("[Spotify] 🔐 Initialisation du client...")
            
            auth_manager = SpotifyClientCredentials(
                client_id=settings.spotify_client_id,
                client_secret=settings.spotify_client_secret
            )
            
            self._client = spotipy.Spotify(
                auth_manager=auth_manager,
                requests_timeout=10,  # Timeout pour les requêtes
                retries=3,  # Nombre de retries automatiques
            )
            
            # Test de connexion
            self._client.search(q="test", type="track", limit=1)
            
            self._last_auth_time = time.time()
            self._auth_retry_count = 0
            
            print("[Spotify] ✅ Client initialisé avec succès")
            return True
            
        except SpotifyException as e:
            print(f"[Spotify] ❌ Erreur Spotify: {e}")
            self._client = None
            return False
            
        except Exception as e:
            print(f"[Spotify] ❌ Erreur initialisation: {type(e).__name__}: {e}")
            traceback.print_exc()
            self._client = None
            return False
    
    def _ensure_client(self) -> bool:
        """S'assure que le client est valide, réinitialise si nécessaire"""
        
        if self._client is None:
            if self._auth_retry_count >= self._max_auth_retries:
                print("[Spotify] ❌ Max retries atteint, client désactivé")
                return False
            
            print("[Spotify] 🔄 Tentative de réinitialisation du client...")
            self._auth_retry_count += 1
            return self._init_client()
        
        # Vérifier si le token a plus de 50 minutes (expire après 60)
        if time.time() - self._last_auth_time > 3000:
            print("[Spotify] 🔄 Token potentiellement expiré, réinitialisation...")
            return self._init_client()
        
        return True
    
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
        return False
    
    @property
    def supports_bpm(self) -> bool:
        return True
    
    # ============================================
    # MÉTHODES PRINCIPALES
    # ============================================
    
    async def search(self, query: str, limit: int = 20) -> list[Track]:
        """Recherche Spotify avec gestion d'erreurs complète"""
        
        try:
            # Vérifier le client
            if not self._ensure_client():
                print("[Spotify] ❌ Client non disponible")
                return []
            
            # Décoder et nettoyer la query
            decoded_query = unquote(query).strip()
            
            if not decoded_query:
                print("[Spotify] ⚠️ Query vide après décodage")
                return []
            
            # Limiter la taille de la query
            if len(decoded_query) > 250:
                print("[Spotify] ⚠️ Query trop longue, truncation à 250 caractères")
                decoded_query = decoded_query[:250]
            
            # Valider la limite (Spotify max = 50)
            limit = max(1, min(limit, 50))
            
            print(f"[Spotify] 🔍 Recherche: '{decoded_query}' (limit: {limit})")
            
            # Exécuter la recherche dans un thread avec timeout
            loop = asyncio.get_event_loop()
            
            try:
                results = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: self._search_sync(decoded_query, limit)
                    ),
                    timeout=20.0
                )
                
                if results is None:
                    return []
                
                tracks = []
                track_ids = []
                
                items = results.get("tracks", {}).get("items", [])
                
                if not items:
                    print(f"[Spotify] ℹ️ Aucun résultat pour '{decoded_query}'")
                    return []
                
                print(f"[Spotify] 📦 {len(items)} résultats bruts")
                
                # Parser les tracks
                for idx, item in enumerate(items):
                    if not item or not isinstance(item, dict):
                        continue
                    
                    try:
                        track = self._parse_track(item)
                        
                        if track:
                            tracks.append(track)
                            
                            # Garder l'ID original pour le batch BPM
                            original_id = item.get("id")
                            if original_id:
                                track_ids.append(original_id)
                        
                    except Exception as e:
                        print(f"[Spotify] ⚠️ Erreur parsing item {idx}: {e}")
                        continue
                
                # Récupérer les BPM en batch (non bloquant)
                if track_ids:
                    try:
                        bpm_map = await asyncio.wait_for(
                            self._get_bpm_batch(track_ids),
                            timeout=10.0
                        )
                        
                        # Appliquer les BPM
                        for track in tracks:
                            spotify_id = track.id.replace("sp_", "")
                            if spotify_id in bpm_map:
                                track.bpm = bpm_map[spotify_id]
                        
                        print(f"[Spotify] 🎵 BPM récupérés pour {len(bpm_map)} tracks")
                        
                    except asyncio.TimeoutError:
                        print("[Spotify] ⏱️ Timeout récupération BPM batch")
                    except Exception as e:
                        print(f"[Spotify] ⚠️ Erreur BPM batch: {e}")
                
                print(f"[Spotify] ✅ {len(tracks)} tracks valides extraites")
                return tracks
                
            except asyncio.TimeoutError:
                print(f"[Spotify] ⏱️ Timeout après 20s pour '{decoded_query}'")
                return []
                
        except SpotifyException as e:
            self._handle_spotify_error(e, "search")
            return []
            
        except Exception as e:
            print(f"[Spotify] ❌ ERREUR search: {type(e).__name__}: {e}")
            traceback.print_exc()
            return []
    
    def _search_sync(self, query: str, limit: int) -> Optional[dict]:
        """Recherche synchrone avec gestion d'erreurs"""
        
        try:
            return self._client.search(q=query, type='track', limit=limit)
            
        except SpotifyException as e:
            self._handle_spotify_error(e, "_search_sync")
            return None
            
        except Exception as e:
            print(f"[Spotify] ❌ Erreur _search_sync: {e}")
            return None
    
    async def get_track(self, track_id: str) -> Optional[Track]:
        """Récupère un track par ID avec validation"""
        
        try:
            # Vérifier le client
            if not self._ensure_client():
                print("[Spotify] ❌ Client non disponible")
                return None
            
            print(f"[Spotify] 🔍 get_track: {track_id}")
            
            # Décoder et nettoyer
            track_id = unquote(track_id).strip()
            
            if not track_id:
                print("[Spotify] ❌ track_id vide")
                return None
            
            # Enlever le préfixe si présent
            if track_id.startswith("sp_"):
                track_id = track_id[3:]
            
            # Valider le format de l'ID Spotify (22 caractères alphanumériques)
            if not self._is_valid_spotify_id(track_id):
                print(f"[Spotify] ⚠️ ID invalide: {track_id}")
                return None
            
            loop = asyncio.get_event_loop()
            
            try:
                data = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: self._get_track_sync(track_id)
                    ),
                    timeout=15.0
                )
                
                if not data:
                    print(f"[Spotify] ❌ Track non trouvée: {track_id}")
                    return None
                
                track = self._parse_track(data)
                
                if track:
                    # Récupérer le BPM (non bloquant)
                    try:
                        bpm = await asyncio.wait_for(
                            self.get_bpm(track),
                            timeout=5.0
                        )
                        track.bpm = bpm
                    except:
                        pass  # Ignorer les erreurs BPM
                    
                    print(f"[Spotify] ✅ Track trouvée: {track.artist} - {track.title}")
                
                return track
                
            except asyncio.TimeoutError:
                print(f"[Spotify] ⏱️ Timeout get_track pour {track_id}")
                return None
                
        except SpotifyException as e:
            self._handle_spotify_error(e, "get_track")
            return None
            
        except Exception as e:
            print(f"[Spotify] ❌ ERREUR get_track: {type(e).__name__}: {e}")
            traceback.print_exc()
            return None
    
    def _get_track_sync(self, track_id: str) -> Optional[dict]:
        """Récupération synchrone d'un track"""
        
        try:
            return self._client.track(track_id)
            
        except SpotifyException as e:
            self._handle_spotify_error(e, "_get_track_sync")
            return None
            
        except Exception as e:
            print(f"[Spotify] ❌ Erreur _get_track_sync: {e}")
            return None
    
    async def download(self, track: Track, output_path: str) -> str:
        """
        Spotify ne permet pas le téléchargement direct.
        Lève une exception avec un message explicite.
        """
        
        print(f"[Spotify] ⚠️ Téléchargement direct non supporté pour: {track.title}")
        
        # Option: Rediriger vers YouTube
        raise NotImplementedError(
            f"Spotify ne supporte pas le téléchargement direct. "
            f"Recherchez '{track.artist} {track.title}' sur YouTube ou SoundCloud."
        )
    
    async def get_bpm(self, track: Track) -> Optional[float]:
        """Récupère le BPM avec gestion d'erreur"""
        
        try:
            if not self._ensure_client():
                return None
            
            if not track or not track.id:
                return None
            
            spotify_id = track.id.replace("sp_", "")
            
            if not self._is_valid_spotify_id(spotify_id):
                print(f"[Spotify] ⚠️ ID invalide pour BPM: {spotify_id}")
                return None
            
            loop = asyncio.get_event_loop()
            
            features = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self._get_audio_features_sync([spotify_id])
                ),
                timeout=10.0
            )
            
            if features and len(features) > 0 and features[0]:
                tempo = features[0].get("tempo")
                if tempo and tempo > 0:
                    return round(float(tempo), 1)
            
            return None
            
        except asyncio.TimeoutError:
            print(f"[Spotify] ⏱️ Timeout get_bpm")
            return None
            
        except SpotifyException as e:
            self._handle_spotify_error(e, "get_bpm")
            return None
            
        except Exception as e:
            print(f"[Spotify] ⚠️ Erreur get_bpm: {e}")
            return None
    
    # ============================================
    # MÉTHODES PRIVÉES
    # ============================================
    
    async def _get_bpm_batch(self, track_ids: list[str]) -> dict[str, float]:
        """Récupère les BPM pour plusieurs tracks en une seule requête"""
        
        try:
            if not self._ensure_client():
                return {}
            
            if not track_ids:
                return {}
            
            # Spotify limite à 100 IDs par requête
            track_ids = track_ids[:100]
            
            # Filtrer les IDs invalides
            valid_ids = [tid for tid in track_ids if self._is_valid_spotify_id(tid)]
            
            if not valid_ids:
                return {}
            
            loop = asyncio.get_event_loop()
            
            features = await loop.run_in_executor(
                None,
                lambda: self._get_audio_features_sync(valid_ids)
            )
            
            if not features:
                return {}
            
            bpm_map = {}
            
            for i, feature in enumerate(features):
                if feature and isinstance(feature, dict):
                    tempo = feature.get("tempo")
                    if tempo and isinstance(tempo, (int, float)) and tempo > 0:
                        bpm_map[valid_ids[i]] = round(float(tempo), 1)
            
            return bpm_map
            
        except SpotifyException as e:
            self._handle_spotify_error(e, "_get_bpm_batch")
            return {}
            
        except Exception as e:
            print(f"[Spotify] ⚠️ Erreur _get_bpm_batch: {e}")
            return {}
    
    def _get_audio_features_sync(self, track_ids: list[str]) -> Optional[list]:
        """Récupération synchrone des audio features"""
        
        try:
            return self._client.audio_features(track_ids)
            
        except SpotifyException as e:
            self._handle_spotify_error(e, "_get_audio_features_sync")
            return None
            
        except Exception as e:
            print(f"[Spotify] ❌ Erreur _get_audio_features_sync: {e}")
            return None
    
    def _parse_track(self, data: dict) -> Optional[Track]:
        """Parse une track Spotify avec validation complète"""
        
        try:
            # Validation des données essentielles
            if not isinstance(data, dict):
                print(f"[Spotify] ⚠️ Data invalide: {type(data)}")
                return None
            
            track_id = data.get("id")
            title = data.get("name")
            
            if not track_id or not title:
                print(f"[Spotify] ⚠️ Données manquantes: id={track_id}, name={title}")
                return None
            
            # Extraire les artistes
            artists_data = data.get("artists", [])
            
            if isinstance(artists_data, list) and artists_data:
                artist_names = []
                for artist in artists_data:
                    if isinstance(artist, dict) and artist.get("name"):
                        artist_names.append(artist["name"])
                
                artists = ", ".join(artist_names) if artist_names else "Unknown Artist"
            else:
                artists = "Unknown Artist"
            
            # Extraire l'artwork
            album_data = data.get("album", {})
            artwork_url = None
            
            if isinstance(album_data, dict):
                images = album_data.get("images", [])
                if isinstance(images, list) and images:
                    # Prendre la plus grande image
                    for img in images:
                        if isinstance(img, dict) and img.get("url"):
                            artwork_url = img["url"]
                            break
            
            # Extraire la durée (en ms → convertir en secondes)
            duration_ms = data.get("duration_ms", 0)
            
            if isinstance(duration_ms, (int, float)):
                duration = int(duration_ms) // 1000
            else:
                duration = 0
            
            # Extraire l'URL Spotify
            external_urls = data.get("external_urls", {})
            
            if isinstance(external_urls, dict):
                url = external_urls.get("spotify", "")
            else:
                url = ""
            
            track = Track(
                id=self.generate_track_id(track_id),
                title=str(title),
                artist=str(artists),
                source=self.platform_name,
                url=str(url),
                bpm=None,  # Sera rempli après
                duration=duration,
                artwork_url=artwork_url,
                genre=None  # Spotify ne donne pas le genre par track
            )
            
            return track
            
        except Exception as e:
            print(f"[Spotify] ❌ Erreur _parse_track: {type(e).__name__}: {e}")
            traceback.print_exc()
            return None
    
    def _is_valid_spotify_id(self, track_id: str) -> bool:
        """Vérifie si l'ID est un ID Spotify valide"""
        
        if not track_id:
            return False
        
        # Les IDs Spotify sont des chaînes Base62 de 22 caractères
        if len(track_id) != 22:
            return False
        
        # Vérifier que c'est alphanumériques
        return track_id.isalnum()
    
    def _handle_spotify_error(self, error: SpotifyException, context: str = ""):
        """Gère les erreurs Spotify de manière centralisée"""
        
        http_status = getattr(error, 'http_status', None)
        
        context_str = f" ({context})" if context else ""
        
        if http_status == 401:
            print(f"[Spotify] 🔐 Erreur 401{context_str}: Token invalide/expiré")
            print("[Spotify] 🔄 Tentative de réinitialisation...")
            self._client = None
            self._init_client()
            
        elif http_status == 403:
            print(f"[Spotify] 🚫 Erreur 403{context_str}: Accès refusé")
            print("[Spotify] ⚠️ Vérifiez vos credentials ou les permissions de l'app")
            
        elif http_status == 404:
            print(f"[Spotify] ℹ️ Erreur 404{context_str}: Ressource non trouvée")
            
        elif http_status == 429:
            print(f"[Spotify] ⏱️ Erreur 429{context_str}: Rate limit atteint")
            print("[Spotify] 💡 Attendez quelques secondes avant de réessayer")
            
        elif http_status and http_status >= 500:
            print(f"[Spotify] 🔥 Erreur {http_status}{context_str}: Erreur serveur Spotify")
            
        else:
            print(f"[Spotify] ❌ Erreur{context_str}: {error}")
        
        # Log le message complet pour debug
        if hasattr(error, 'msg'):
            print(f"[Spotify] 📄 Message: {error.msg}")