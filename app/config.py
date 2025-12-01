from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # SoundCloud
    soundcloud_client_id: Optional[str] = None
    
    # Spotify
    spotify_client_id: Optional[str] = None
    spotify_client_secret: Optional[str] = None
    
    # YouTube
    youtube_api_key: Optional[str] = None
    
    # Config générale
    download_path: str = "./downloads"
    max_results: int = 20
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Créer le dossier de téléchargement s'il n'existe pas
os.makedirs(settings.download_path, exist_ok=True)