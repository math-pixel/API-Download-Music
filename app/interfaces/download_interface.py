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