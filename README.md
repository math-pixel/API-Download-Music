
# 🎧 DJ API - Multi-Platform Music Search & Download

A local API that allows you to search and download music from multiple platforms (Deezer, YouTube, SoundCloud, Spotify) for use with DJ software like Mixxx.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## 📖 Description

**DJ API** is a local REST API that allows DJs to:

- 🔍 **Search** for tracks across multiple platforms simultaneously
- 📥 **Download** tracks automatically in MP3 320kbps
- 🎵 **Retrieve BPM** to make mixing easier
- 🎛️ **Integrate with Mixxx** or other DJ software

### Supported Platforms

| Platform | Search | Download | BPM |
|----------|--------|----------|-----|
| Deezer | ✅ | ✅ (via YouTube) | ✅ |
| YouTube | ✅ | ✅ | ❌ |
| SoundCloud | ✅ | ✅ | ❌ |
| Spotify | ✅ | ✅ (via YouTube) | ✅ |

### Use Case

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│   Mixxx     │────▶│   DJ API    │────▶│  Deezer/YouTube │
│  (or other) │◀────│ (localhost) │◀────│  SoundCloud/... │
└─────────────┘     └─────────────┘     └─────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  downloads/ │
                    │  (MP3 320k) │
                    └─────────────┘
```


## 🚀 Installation

### Prerequisites

- Python 3.10 or higher
- FFmpeg (for audio conversion)

### 1. Clone the project

```bash
git clone https://github.com/your-username/dj-api.git
cd dj-api
```

### 2. Create a virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install FFmpeg

#### Windows
```bash
# With Chocolatey
choco install ffmpeg

# Or download from https://ffmpeg.org/download.html
```

#### Linux
```bash
sudo apt update
sudo apt install ffmpeg
```

#### Mac
```bash
brew install ffmpeg
```

### 5. Configure environment variables

Create a `.env` file at the project root:

```env
# SoundCloud (optional)
SOUNDCLOUD_CLIENT_ID=your_soundcloud_client_id

# Spotify (optional - for search and BPM)
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret

# YouTube (optional)
YOUTUBE_API_KEY=your_youtube_api_key

# Configuration
DOWNLOAD_PATH=./downloads
MAX_RESULTS=20
```

> 💡 **Note**: Deezer and YouTube work without an API key for basic search.

---

## ▶️ Running the Application

### Method 1: With Python

```bash
python run.py
```

### Method 2: With Uvicorn

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Method 3: With Python module

```bash
python -m uvicorn app.main:app --reload --port 8000
```

The API will be accessible at: **http://localhost:8000**

---

## 📚 API Documentation

Once the API is running, access the interactive documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 🛣️ API Routes

### Information

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/` | API information |
| `GET` | `/platforms` | List of available platforms |

### Search

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/search?q={query}` | Search across all platforms |
| `GET` | `/search/{platform}?q={query}` | Search on a specific platform |

### Tracks

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/track/{source}/{track_id}` | Get track information |

### Download

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/download/{source}/{track_id}` | Download a track |
| `POST` | `/download` | Download a track (with JSON body) |

---

## 📝 Usage Examples

### Search across all platforms

```bash
curl "http://localhost:8000/search?q=daft%20punk&limit=5"
```

**Response:**

```json
{
  "query": "daft punk",
  "total_results": 10,
  "results": [
    {
      "id": "dz_3135556",
      "title": "One More Time",
      "artist": "Daft Punk",
      "source": "deezer",
      "url": "https://www.deezer.com/track/3135556",
      "bpm": 122.0,
      "duration": 320,
      "artwork_url": "https://e-cdns-images.dzcdn.net/images/cover/...",
      "genre": null
    }
  ]
}
```

### Search on Deezer only

```bash
curl "http://localhost:8000/search/deezer?q=daft%20punk&limit=10"
```

### Search on YouTube only

```bash
curl "http://localhost:8000/search/youtube?q=daft%20punk%20one%20more%20time"
```

### Search on specific platforms

```bash
curl "http://localhost:8000/search?q=daft%20punk&platforms=deezer,youtube&limit=5"
```

### Get track information

```bash
curl "http://localhost:8000/track/deezer/dz_3135556"
```

### Download a track (GET)

```bash
curl "http://localhost:8000/download/deezer/dz_3135556"
```

**Response:**

```json
{
  "status": "ready",
  "filepath": "./downloads/Daft Punk - One More Time.mp3",
  "track": {
    "id": "dz_3135556",
    "title": "One More Time",
    "artist": "Daft Punk",
    "source": "deezer",
    "bpm": 122.0
  }
}
```

### Download a track (POST)

```bash
curl -X POST "http://localhost:8000/download" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.deezer.com/track/3135556",
    "source": "deezer",
    "track_id": "dz_3135556"
  }'
```

---

## 📁 Project Structure

```
dj-api/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Configuration (.env)
│   ├── interfaces/
│   │   ├── __init__.py
│   │   └── download_interface.py   # Abstract interface
│   ├── platforms/
│   │   ├── __init__.py
│   │   ├── soundcloud.py       # SoundCloud implementation
│   │   ├── spotify.py          # Spotify implementation
│   │   ├── deezer.py           # Deezer implementation
│   │   └── youtube.py          # YouTube implementation
│   ├── services/
│   │   ├── __init__.py
│   │   ├── search_service.py   # Search service
│   │   └── download_service.py # Download service
│   └── models/
│       ├── __init__.py
│       └── track.py            # Pydantic models
├── downloads/                   # Downloads folder
├── requirements.txt
├── run.py                       # Launch script
├── .env                         # Environment variables
└── README.md
```

---

## 🔧 Advanced Configuration

### Change download folder

In `.env`:

```env
DOWNLOAD_PATH=D:/My Music/DJ
```

### Limit search results

In `.env`:

```env
MAX_RESULTS=50
```

### Getting API Keys

#### Spotify
1. Go to https://developer.spotify.com/dashboard
2. Create an application
3. Copy the Client ID and Client Secret

#### SoundCloud
1. Go to https://developers.soundcloud.com/
2. Create an application
3. Copy the Client ID

---

## 🎛️ Integration with Mixxx

Mixxx is an open source DJ software, which is why it's easy to integrate my API with this software.

### Option 1: Watched Folder

1. Configure `DOWNLOAD_PATH` to your Mixxx folder
2. In Mixxx, add this folder to your library
3. New downloads will appear automatically

### Option 2: Custom Script

See the Mixxx documentation to create controller scripts:
https://github.com/mixxxdj/mixxx/wiki/Midi-Scripting

### Option 2 bis: Mixxx Add-on (Coming Soon)

---

## ⚠️ Legal Disclaimer

This API is intended for **personal use only**.

- ❌ Do not use for public broadcasting
- ❌ Do not redistribute downloaded files
- ✅ Use for preparing personal DJ sets
- ✅ Respect copyright laws

---

## 🐛 Troubleshooting

### Error: `ModuleNotFoundError: No module named 'app'`

```bash
# Run from the project root
cd dj-api
python -m uvicorn app.main:app --reload
```

### Error: `FFmpeg not found`

Install FFmpeg and add it to your PATH.

### Error: `yt-dlp` download fails

```bash
# Update yt-dlp
pip install --upgrade yt-dlp
```

### BPM not showing

- Deezer: BPM is available
- Spotify: Requires API keys
- YouTube/SoundCloud: BPM not available via API

---

## 🤝 Contributing

Contributions are welcome!

1. Fork the project
2. Create a branch (`git checkout -b feature/new-feature`)
3. Commit (`git commit -m 'Add new feature'`)
4. Push (`git push origin feature/new-feature`)
5. Open a Pull Request

---

## 📄 License

MIT License - See the [LICENSE](LICENSE) file for more details.
