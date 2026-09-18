# YouTube Downloader ULTRA 🎬

A desktop GUI app (built with Python + CustomTkinter) for downloading YouTube videos/audio/playlists using **yt-dlp** and **ffmpeg**, with features like time-range trimming, subtitles, SponsorBlock, thumbnails, and batch downloads.

---

## 1. Tools You Need to Download First

Before running this app, install/download these:

| # | Tool | What it's for | Download Link |
|---|------|----------------|----------------|
| 1 | **Python 3.10+** | To run the script | https://www.python.org/downloads/ |
| 2 | **yt-dlp.exe** | Actually downloads the videos | https://github.com/yt-dlp/yt-dlp/releases (download `yt-dlp.exe`) |
| 3 | **ffmpeg** | Merges video+audio, trims, converts formats | https://www.gyan.dev/ffmpeg/builds/ (get the "essentials" or "full" build zip) |
| 4 | **VLC Media Player** (optional) | Needed only for live video preview in the "Preview & Trim" tab | https://www.videolan.org/vlc/ |

You'll also need a few Python packages (installed via `pip`, see Step 3 below):
- `customtkinter`
- `python-vlc` (optional, only for preview feature)

---

## 2. Create Folder For Setup

The app expects one main folder containing everything. Create a folder like this:

```
yt-dlp_win/
│
├── yt-dlp.exe          ← from Step 1 download
├── ffmpeg.exe          ← extract from the ffmpeg zip (inside the "bin" folder)
├── Cookies/
│   └── cookies.txt     ← optional, only needed for private/age-restricted videos
└── Downloads/          ← this folder is auto-created; downloaded files go here
```

**Important:** In the script file (`Tool_ultra-v1.py`), find this line near the top of the code (around line 156):

```python
self.base_path = Path(r"C:\Users\Shahnwaz Aalam\Downloads\Compressed\yt-dlp_win\yt-dlp_win")
```

Change the path inside the quotes to match **your own folder location** (the one you made above). For example:

```python
self.base_path = Path(r"C:\Users\YourName\Documents\yt-dlp_win")
```

---

## 3. Step-by-Step Setup (Easy)

1. **Install Python** — download and install from python.org. During install, tick ✅ "Add Python to PATH".
2. **Download yt-dlp.exe** and put it inside your `yt-dlp_win` folder.
3. **Download ffmpeg**, unzip it, and copy `ffmpeg.exe` (found inside the `bin` folder) into your `yt-dlp_win` folder.
4. **(Optional) Install VLC Media Player** if you want live video preview inside the app.
5. **Open Command Prompt / Terminal** and install the required Python packages:
   ```
   pip install customtkinter
   pip install python-vlc
   ```
6. **Edit the script** — open `Tool_ultra-v1.py` in any text editor (Notepad, VS Code, etc.) and update the `base_path` line as shown in Step 2 above, to match your folder.
7. **Run the app**:
   ```
   python Tool_ultra-v1.py
   ```
8. Paste a YouTube URL into the app, pick your quality/mode, and click **START DOWNLOAD**.

---

## 4. Common Problems

- **"yt-dlp.exe not found" warning in the log** → Make sure `yt-dlp.exe` is inside the same folder as `base_path`.
- **Videos download but no sound / merge fails** → `ffmpeg.exe` is missing or in the wrong folder.
- **No live preview in "Preview & Trim" tab** → Install `python-vlc` (`pip install python-vlc`) AND install VLC Media Player itself on your PC.
- **Private/restricted videos fail** → Add a valid `cookies.txt` file inside the `Cookies` folder (exported from your browser using an extension like "Get cookies.txt").

---

## 5. Requirements Summary

```
Python 3.10+
customtkinter
python-vlc (optional)
yt-dlp.exe (external binary)
ffmpeg.exe (external binary)
VLC Media Player (optional, for preview)
```

---

⚠️ **Note:** Only download and use this tool for content you have the right to download. Respect YouTube's Terms of Service and copyright laws.
