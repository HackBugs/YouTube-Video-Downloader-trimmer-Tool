
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog, scrolledtext, ttk
import subprocess
import threading
import os
import sys
import re
import json
import time
from datetime import datetime
from pathlib import Path

# python-vlc powers the inline video preview in the "Preview & Trim" tab.
# Requires: pip install python-vlc  AND  VLC Media Player installed on this PC.
# If it's missing, the app still works fully -- you just won't get live preview
# playback (trimming/downloading by typing times still works).
try:
    import vlc
    VLC_AVAILABLE = True
except Exception:
    VLC_AVAILABLE = False

# Configure CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")


def seconds_to_hhmmss(total_seconds):
    """Convert a float/int number of seconds into HH:MM:SS."""
    total_seconds = max(0, int(round(total_seconds or 0)))
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def hhmmss_to_seconds(text):
    """Convert HH:MM:SS / MM:SS / SS text into total seconds (int)."""
    parts = [p.strip() for p in text.strip().split(":")]
    parts = [int(p) for p in parts]
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, s = parts[-3:]
    return h * 3600 + m * 60 + s


class RangeSlider(ctk.CTkFrame):
    """A dual-handle range slider (Canvas based) for picking a start/end trim range.

    CustomTkinter has no built-in dual-handle slider, so this draws one on a
    plain tkinter Canvas: a track, a highlighted selected range, and two
    draggable handles (start = cyan, end = pink).
    """

    def __init__(self, master, from_=0, to=100, command=None, height=50, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.from_ = from_
        self.to = to if to > from_ else from_ + 1
        self.command = command
        self.start_val = from_
        self.end_val = self.to
        self.canvas_height = height
        self.pad = 16
        self.handle_r = 9
        self.dragging = None  # "start" | "end" | None

        self.canvas = tk.Canvas(self, height=height, bg="#171922", highlightthickness=0)
        self.canvas.pack(fill="x", expand=True)

        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Configure>", lambda e: self._redraw())

        self._redraw()

    def set_range(self, from_, to):
        """Reset the min/max bounds (e.g. once a video's real duration is known)."""
        self.from_ = from_
        self.to = to if to > from_ else from_ + 1
        self.start_val = from_
        self.end_val = self.to
        self._redraw()

    def get_values(self):
        return self.start_val, self.end_val

    def set_values(self, start, end):
        self.start_val = max(self.from_, min(start, self.to))
        self.end_val = max(self.start_val, min(end, self.to))
        self._redraw()

    def _val_to_x(self, val):
        w = self.canvas.winfo_width() or 600
        usable = max(1, w - 2 * self.pad)
        ratio = (val - self.from_) / (self.to - self.from_) if self.to > self.from_ else 0
        return self.pad + ratio * usable

    def _x_to_val(self, x):
        w = self.canvas.winfo_width() or 600
        usable = max(1, w - 2 * self.pad)
        x = max(self.pad, min(x, w - self.pad))
        ratio = (x - self.pad) / usable
        return self.from_ + ratio * (self.to - self.from_)

    def _redraw(self):
        c = self.canvas
        c.delete("all")
        w = c.winfo_width() or 600
        mid_y = self.canvas_height // 2

        c.create_line(self.pad, mid_y, w - self.pad, mid_y, fill="#2a2e3d", width=6, capstyle="round")

        x1 = self._val_to_x(self.start_val)
        x2 = self._val_to_x(self.end_val)
        c.create_line(x1, mid_y, x2, mid_y, fill="#6366f1", width=6, capstyle="round")

        c.create_oval(x1 - self.handle_r, mid_y - self.handle_r, x1 + self.handle_r, mid_y + self.handle_r,
                       fill="#6366f1", outline="#f4f5f7", width=2)
        c.create_oval(x2 - self.handle_r, mid_y - self.handle_r, x2 + self.handle_r, mid_y + self.handle_r,
                       fill="#fb7185", outline="#f4f5f7", width=2)

    def _on_press(self, event):
        x1 = self._val_to_x(self.start_val)
        x2 = self._val_to_x(self.end_val)
        self.dragging = "start" if abs(event.x - x1) <= abs(event.x - x2) else "end"
        self._on_drag(event)

    def _on_drag(self, event):
        if not self.dragging:
            return
        val = self._x_to_val(event.x)
        if self.dragging == "start":
            self.start_val = min(val, self.end_val)
        else:
            self.end_val = max(val, self.start_val)
        self._redraw()
        if self.command:
            self.command(self.start_val, self.end_val)

    def _on_release(self, event):
        self.dragging = None

class YouTubeDownloaderULTRA(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Configuration
        self.title("🎬 YouTube Downloader ULTRA - Professional Suite")
        self.geometry("1600x1000")
        self.minsize(1400, 900)

        # Your Exact Paths
        self.base_path = Path(r"C:\Users\Shahnwaz Aalam\Downloads\Compressed\yt-dlp_win\yt-dlp_win")
        self.cookies_path = self.base_path / "Cookies" / "cookies.txt"
        self.yt_dlp_path = self.base_path / "yt-dlp.exe"
        self.ffmpeg_path = self.base_path / "ffmpeg.exe"
        self.output_path = self.base_path / "Downloads"
        self.output_path.mkdir(exist_ok=True)

        # State Variables
        self.is_downloading = False
        self.download_queue = []
        self.download_history = []
        self.current_process = None
        self.queue_counter = 0

        # Preview & Trim state
        self.vlc_instance = None
        self.vlc_player = None
        self.preview_duration = 0
        self._playback_job = None

        # Initialize All yt-dlp Options
        self.init_all_variables()

        # Create UI
        self.create_ui()

        # Clean up VLC / background jobs on close
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Startup checks
        self.after(500, self.startup_checks)

    def on_closing(self):
        """Stop playback / timers cleanly before the window closes"""
        try:
            if self._playback_job:
                self.after_cancel(self._playback_job)
            if self.vlc_player:
                self.vlc_player.stop()
        except Exception:
            pass
        self.destroy()

    def init_all_variables(self):
        """Initialize ALL possible yt-dlp options"""

        # Core Options
        self.url = ctk.StringVar()
        self.batch_urls = ctk.StringVar()

        # Selection
        self.video_selection = ctk.StringVar(value="best")
        self.audio_selection = ctk.StringVar(value="bestaudio")
        self.format_spec = ctk.StringVar()

        # Quality
        self.quality_video = ctk.StringVar(value="best")
        self.quality_audio = ctk.StringVar(value="0")

        # Time
        self.time_start = ctk.StringVar(value="00:00:00")
        self.time_end = ctk.StringVar(value="00:00:00")
        self.dateafter = ctk.StringVar()
        self.datebefore = ctk.StringVar()

        # Playlist
        self.playlist_start = ctk.StringVar(value="1")
        self.playlist_end = ctk.StringVar()
        self.playlist_items = ctk.StringVar()
        self.max_downloads = ctk.StringVar()
        self.min_filesize = ctk.StringVar()
        self.max_filesize = ctk.StringVar()

        # Download Control
        self.concurrent_fragments = ctk.IntVar(value=5)
        self.limit_rate = ctk.StringVar()
        self.throttled_rate = ctk.StringVar()
        self.retries = ctk.IntVar(value=10)
        self.fragment_retries = ctk.IntVar(value=10)
        self.skip_unavailable = ctk.BooleanVar(value=True)
        self.keep_fragments = ctk.BooleanVar(value=False)
        self.buffer_size = ctk.IntVar(value=1024)
        self.no_resize_buffer = ctk.BooleanVar(value=False)
        self.http_chunk_size = ctk.StringVar()

        # Filesystem
        self.filename_template = ctk.StringVar(value="%(title)s.%(ext)s")
        self.restrict_filenames = ctk.BooleanVar(value=False)
        self.no_overwrites = ctk.BooleanVar(value=False)
        self.continue_dl = ctk.BooleanVar(value=True)
        self.part = ctk.BooleanVar(value=True)
        self.no_part = ctk.BooleanVar(value=False)
        self.mtime = ctk.BooleanVar(value=True)
        self.no_mtime = ctk.BooleanVar(value=False)

        # Thumbnail
        self.write_thumbnail = ctk.BooleanVar(value=False)
        self.write_all_thumbnails = ctk.BooleanVar(value=False)
        self.list_thumbnails = ctk.BooleanVar(value=False)
        self.embed_thumbnail = ctk.BooleanVar(value=False)

        # Subtitle
        self.write_subs = ctk.BooleanVar(value=False)
        self.write_auto_subs = ctk.BooleanVar(value=False)
        self.list_subs = ctk.BooleanVar(value=False)
        self.sub_format = ctk.StringVar(value="srt")
        self.sub_langs = ctk.StringVar(value="en")

        # Trim tab: burn-in (hardcode) subtitles at a chosen font size
        self.burn_subtitles = ctk.BooleanVar(value=False)
        self.subtitle_font_size = ctk.StringVar(value="20")
        self.embed_subs = ctk.BooleanVar(value=False)

        # Metadata
        self.write_info_json = ctk.BooleanVar(value=False)
        self.write_description = ctk.BooleanVar(value=False)
        self.write_annotations = ctk.BooleanVar(value=False)
        self.load_info_json = ctk.StringVar()
        self.add_metadata = ctk.BooleanVar(value=False)
        self.parse_metadata = ctk.StringVar()
        self.xattrs = ctk.BooleanVar(value=False)

        # Post-processing
        self.extract_audio = ctk.BooleanVar(value=False)
        self.audio_format = ctk.StringVar(value="mp3")
        self.audio_quality = ctk.StringVar(value="0")
        self.recode_video = ctk.StringVar(value="none")
        self.keep_video = ctk.BooleanVar(value=False)
        self.no_post_overwrites = ctk.BooleanVar(value=False)
        self.embed_chapters = ctk.BooleanVar(value=False)
        self.embed_info_json = ctk.BooleanVar(value=False)
        self.embed_subs_pp = ctk.BooleanVar(value=False)

        # SponsorBlock
        self.sponsorblock_mark = ctk.StringVar()
        self.sponsorblock_remove = ctk.StringVar()
        self.sponsorblock_chapter_title = ctk.StringVar(value="[SponsorBlock] %(category)s")
        self.no_sponsorblock = ctk.BooleanVar(value=False)

        # Chapter
        self.split_chapters = ctk.BooleanVar(value=False)
        self.remove_chapters = ctk.StringVar()
        self.no_chapters = ctk.BooleanVar(value=False)

        # Network
        self.use_cookies = ctk.BooleanVar(value=True)
        self.cookies_from_browser = ctk.StringVar()
        self.proxy = ctk.StringVar()
        self.socket_timeout = ctk.IntVar(value=30)
        self.source_address = ctk.StringVar()
        self.force_ipv4 = ctk.BooleanVar(value=False)
        self.force_ipv6 = ctk.BooleanVar(value=False)

        # Geo
        self.geo_verification_proxy = ctk.StringVar()
        self.geo_bypass = ctk.BooleanVar(value=False)
        self.geo_bypass_country = ctk.StringVar()
        self.geo_bypass_ip_block = ctk.StringVar()

        # Authentication
        self.username = ctk.StringVar()
        self.password = ctk.StringVar()
        self.twofactor = ctk.StringVar()
        self.netrc = ctk.BooleanVar(value=False)
        self.video_password = ctk.StringVar()

        # Verbosity
        self.quiet = ctk.BooleanVar(value=False)
        self.no_warnings = ctk.BooleanVar(value=True)
        self.simulate = ctk.BooleanVar(value=False)
        self.skip_download = ctk.BooleanVar(value=False)
        self.print_json = ctk.BooleanVar(value=False)
        self.dump_single_json = ctk.BooleanVar(value=False)
        self.print_to_file = ctk.StringVar()

        # Workarounds
        self.no_check_certificate = ctk.BooleanVar(value=False)
        self.prefer_insecure = ctk.BooleanVar(value=False)
        self.user_agent = ctk.StringVar()
        self.referer = ctk.StringVar()
        self.headers = ctk.StringVar()
        self.sleep_interval = ctk.IntVar(value=0)
        self.max_sleep_interval = ctk.IntVar(value=0)
        self.sleep_requests = ctk.IntVar(value=1)

        # Video Format
        self.merge_output_format = ctk.StringVar(value="mp4")
        self.video_format = ctk.StringVar(value="mp4")
        self.prefer_free_formats = ctk.BooleanVar(value=False)
        self.check_formats = ctk.BooleanVar(value=False)
        self.check_all_formats = ctk.BooleanVar(value=False)

        # Archive
        self.download_archive = ctk.BooleanVar(value=False)
        self.archive_path = ctk.StringVar()
        self.break_on_existing = ctk.BooleanVar(value=False)
        self.break_per_input = ctk.BooleanVar(value=False)

    def create_ui(self):
        """Create the futuristic UI"""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header with gradient effect
        self.create_futuristic_header()

        # Main Content
        self.create_main_content()

        # Status Bar
        self.create_status_bar()

    def create_futuristic_header(self):
        """Create a modern futuristic header"""
        header = ctk.CTkFrame(self, fg_color="#0a0b10", height=140, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)

        # Logo Area
        logo_frame = ctk.CTkFrame(header, fg_color="transparent", width=300)
        logo_frame.grid(row=0, column=0, sticky="ns", padx=20)
        logo_frame.grid_propagate(False)

        # Animated Title
        title_label = ctk.CTkLabel(
            logo_frame,
            text="▶ HackBugs",
            font=ctk.CTkFont(family="Consolas", size=36, weight="bold"),
            text_color="#6366f1"
        )
        title_label.place(relx=0.5, rely=0.28, anchor="center")

        subtitle = ctk.CTkLabel(
            logo_frame,
            text="ULTRA EDITION",
            font=ctk.CTkFont(family="Consolas", size=14),
            text_color="#fb7185"
        )
        subtitle.place(relx=0.5, rely=0.4, anchor="center")

        # Center Info Panel (Total Downloads / Speed / ETA / Status)
        info_frame = ctk.CTkFrame(header, fg_color="#171922", corner_radius=14, height=80)
        info_frame.grid(row=0, column=1, sticky="new", padx=20, pady=(30, 0))
        info_frame.grid_propagate(False)
        info_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        info_frame.grid_rowconfigure(0, weight=1)

        self.stat_total = self.create_stat_box(info_frame, "TOTAL DOWNLOADS", "0", 0, "#6366f1")
        self.stat_speed = self.create_stat_box(info_frame, "SPEED", "0 KB/s", 1, "#fb7185")
        self.stat_eta = self.create_stat_box(info_frame, "ETA", "--:--", 2, "#fbbf24")
        self.stat_status = self.create_stat_box(info_frame, "STATUS", "IDLE", 3, "#8b5cf6")

        # Right Control Panel
        ctrl_frame = ctk.CTkFrame(header, fg_color="transparent", width=200)
        ctrl_frame.grid(row=0, column=2, sticky="n", padx=20, pady=(15, 0))

        ctk.CTkButton(
            ctrl_frame,
            text="⚙️ Settings",
            width=120,
            height=35,
            fg_color="#171922",
            hover_color="#2a2e3d",
            command=self.show_settings
        ).pack(pady=5)

        ctk.CTkButton(
            ctrl_frame,
            text="❓ Help",
            width=120,
            height=35,
            fg_color="#171922",
            hover_color="#2a2e3d",
            command=self.show_help
        ).pack(pady=5)

    def create_stat_box(self, parent, label, value, col, color):
        """Create a statistic display box"""
        frame = ctk.CTkFrame(parent, fg_color="#0a0b10", corner_radius=12)
        frame.grid(row=0, column=col, sticky="new", padx=10, pady=6)

        ctk.CTkLabel(
            frame,
            text=label,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#8b93a8"
        ).pack(pady=(6, 0))

        label_val = ctk.CTkLabel(
            frame,
            text=value,
            font=ctk.CTkFont(family="Consolas", size=20, weight="bold"),
            text_color=color
        )
        label_val.pack(pady=(0, 6))

        return label_val


    def create_main_content(self):
        """Create main content area: a left icon sidebar (drag-resizable) + the tool panel on the right"""
        self.tab_frame = ctk.CTkFrame(self, fg_color="#111319")
        self.tab_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        self.tab_frame.grid_rowconfigure(0, weight=1)
        self.tab_frame.grid_columnconfigure(2, weight=1)  # content column stretches

        # ---------------------------------------------------------------
        # LEFT SIDEBAR: one icon + label per tool, stacked vertically
        # ---------------------------------------------------------------
        self.sidebar_min_width = 74
        self.sidebar_max_width = 260
        self.sidebar_width = 140

        self.sidebar = ctk.CTkFrame(
            self.tab_frame, fg_color="#0d0f16", corner_radius=16,
            width=self.sidebar_width
        )
        self.sidebar.grid(row=0, column=0, sticky="ns", padx=(10, 0), pady=10)
        self.sidebar.grid_propagate(False)
        self.sidebar.pack_propagate(False)

        self.sidebar_scroll = ctk.CTkScrollableFrame(
            self.sidebar, fg_color="transparent",
            scrollbar_button_color="#1c1f2a", scrollbar_button_hover_color="#2a2e3d"
        )
        self.sidebar_scroll.pack(fill="both", expand=True, padx=6, pady=(12, 6))

        self.tabs = {}
        tab_configs = [
            ("🚀", "Quick", "quick"),
            ("🎞️", "Preview & Trim", "preview"),
            ("🎬", "Video", "video"),
            ("🎵", "Audio", "audio"),
            ("📝", "Subs", "subs"),
            ("⚙️", "Post-Proc", "post"),
            ("🌐", "Network", "network"),
            ("📊", "Batch", "batch"),
            ("📜", "Output", "output"),
        ]
        self.tab_configs = tab_configs

        for icon, label, name in tab_configs:
            self.create_nav_item(self.sidebar_scroll, icon, label, name)

        # ---------------------------------------------------------------
        # DRAG HANDLE: grab and slide to resize the sidebar
        # ---------------------------------------------------------------
        self.sidebar_divider = ctk.CTkFrame(
            self.tab_frame, fg_color="#171922", width=10, corner_radius=0, cursor="sb_h_double_arrow"
        )
        self.sidebar_divider.grid(row=0, column=1, sticky="ns", pady=10)
        self.sidebar_divider.grid_propagate(False)

        grip = ctk.CTkLabel(
            self.sidebar_divider, text="⋮", font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#3a3f4d", cursor="sb_h_double_arrow"
        )
        grip.place(relx=0.5, rely=0.5, anchor="center")

        for widget in (self.sidebar_divider, grip):
            widget.bind("<ButtonPress-1>", self._start_sidebar_resize)
            widget.bind("<B1-Motion>", self._do_sidebar_resize)

        # ---------------------------------------------------------------
        # RIGHT PANEL: the currently selected tool opens here
        # ---------------------------------------------------------------
        self.content_frame = ctk.CTkFrame(self.tab_frame, fg_color="#171922", corner_radius=16)
        self.content_frame.grid(row=0, column=2, sticky="nsew", padx=(0, 10), pady=10)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        # Create all tab contents
        self.tab_contents = {}
        self.create_quick_tab()
        self.create_preview_tab()
        self.create_video_tab()
        self.create_audio_tab()
        self.create_subs_tab()
        self.create_post_tab()
        self.create_network_tab()
        self.create_batch_tab()
        self.create_output_tab()

        # Show quick tab by default
        self.current_tab = "quick"
        self.switch_tab("quick")

    def create_nav_item(self, parent, icon, label, name):
        """One sidebar entry: big icon on top, tool name below, click anywhere to open it"""
        item = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=12, height=88, cursor="hand2")
        item.pack(fill="x", pady=4, padx=2)
        item.pack_propagate(False)

        icon_lbl = ctk.CTkLabel(item, text=icon, font=ctk.CTkFont(size=24), text_color="#f4f5f7")
        icon_lbl.pack(pady=(12, 2))

        name_lbl = ctk.CTkLabel(
            item, text=label, font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#8b93a8", wraplength=self.sidebar_width - 16, justify="center"
        )
        name_lbl.pack(pady=(0, 10), fill="x", padx=6)

        for widget in (item, icon_lbl, name_lbl):
            widget.configure(cursor="hand2") if hasattr(widget, "configure") else None
            widget.bind("<Button-1>", lambda e, n=name: self.switch_tab(n))
            widget.bind("<Enter>", lambda e, n=name: self._nav_hover(n, True))
            widget.bind("<Leave>", lambda e, n=name: self._nav_hover(n, False))

        self.tabs[name] = {"frame": item, "icon": icon_lbl, "label": name_lbl}

    def _nav_hover(self, name, entering):
        """Subtle hover highlight for sidebar items (skipped for the active one)"""
        if name == getattr(self, "current_tab", None):
            return
        self.tabs[name]["frame"].configure(fg_color="#1c1f2a" if entering else "transparent")

    def _start_sidebar_resize(self, event):
        self._resize_start_x = event.x_root
        self._resize_start_width = self.sidebar.winfo_width()

    def _do_sidebar_resize(self, event):
        delta = event.x_root - self._resize_start_x
        new_width = self._resize_start_width + delta
        new_width = max(self.sidebar_min_width, min(new_width, self.sidebar_max_width))
        self.sidebar_width = new_width
        self.sidebar.configure(width=new_width)
        for widgets in self.tabs.values():
            widgets["label"].configure(wraplength=new_width - 16, width=new_width - 16)

    def switch_tab(self, tab_name):
        """Switch between tools: highlight the active sidebar item, open its panel"""
        for name, widgets in self.tabs.items():
            active = (name == tab_name)
            widgets["frame"].configure(fg_color="#6366f1" if active else "transparent")
            widgets["icon"].configure(text_color="#0a0b10" if active else "#f4f5f7")
            widgets["label"].configure(text_color="#0a0b10" if active else "#8b93a8")
        self.current_tab = tab_name
        self.show_tab(tab_name)

    def show_tab(self, tab_name):
        """Display selected tab content"""
        for content in self.tab_contents.values():
            content.grid_remove()
        self.tab_contents[tab_name].grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.current_tab = tab_name

    def create_quick_tab(self):
        """Quick download tab"""
        frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.tab_contents["quick"] = frame
        frame.grid_columnconfigure(0, weight=1)

        # URL Section
        url_card = self.create_modern_card(frame, "🔗 VIDEO URL", 0)

        self.url_entry = ctk.CTkEntry(
            url_card,
            textvariable=self.url,
            placeholder_text="https://youtube.com/watch?v=...",
            height=50,
            font=ctk.CTkFont(size=14),
            border_color="#6366f1",
            border_width=1,
            corner_radius=10,
            fg_color="#12141b"
        )
        self.url_entry.pack(fill="x", padx=15, pady=15)

        # Quick Actions
        btn_frame = ctk.CTkFrame(url_card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(0, 15))

        ctk.CTkButton(
            btn_frame,
            text="📋 Paste",
            width=100,
            command=self.paste_url,
            fg_color="#1c1f2a"
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="🔍 Analyze",
            width=100,
            command=self.analyze_video,
            fg_color="#1c1f2a"
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="📋 Formats",
            width=100,
            command=self.list_formats,
            fg_color="#fb7185"
        ).pack(side="right", padx=5)

        # Mode Selection
        mode_card = self.create_modern_card(frame, "🎯 DOWNLOAD MODE", 1)

        modes = ctk.CTkFrame(mode_card, fg_color="transparent")
        modes.pack(fill="x", padx=15, pady=15)
        modes.grid_columnconfigure((0,1,2,3), weight=1)

        self.mode_var = ctk.StringVar(value="video")

        mode_options = [
            ("🎬 Video", "video", "#6366f1"),
            ("🎵 Audio", "audio", "#818cf8"),
            ("📁 Playlist", "playlist", "#9333ea"),
            ("⚡ Best", "best", "#d946ef")
        ]

        for idx, (text, value, color) in enumerate(mode_options):
            btn = ctk.CTkRadioButton(
                modes,
                text=text,
                variable=self.mode_var,
                value=value,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color=color,
                height=40
            )
            btn.grid(row=0, column=idx, padx=10, sticky="ew")

        # Quality Row
        qual_card = self.create_modern_card(frame, "⚡ QUALITY & FORMAT", 2)

        qual_grid = ctk.CTkFrame(qual_card, fg_color="transparent")
        qual_grid.pack(fill="x", padx=15, pady=15)

        ctk.CTkLabel(qual_grid, text="Video Quality:", font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w")
        self.vid_qual = ctk.CTkComboBox(qual_grid, values=["best", "1080p", "720p", "480p", "360p", "worst"], width=150)
        self.vid_qual.grid(row=0, column=1, padx=10)
        self.vid_qual.set("best")

        ctk.CTkLabel(qual_grid, text="Format:", font=ctk.CTkFont(size=11)).grid(row=0, column=2, sticky="w", padx=(20,0))
        self.vid_fmt = ctk.CTkComboBox(qual_grid, values=["mp4", "mkv", "webm", "mov"], width=120)
        self.vid_fmt.grid(row=0, column=3, padx=10)
        self.vid_fmt.set("mp4")

        ctk.CTkLabel(qual_grid, text="Audio:", font=ctk.CTkFont(size=11)).grid(row=1, column=0, sticky="w", pady=(10,0))
        self.aud_fmt = ctk.CTkComboBox(qual_grid, values=["mp3", "wav", "m4a", "flac", "aac"], width=120)
        self.aud_fmt.grid(row=1, column=1, padx=10, pady=(10,0))
        self.aud_fmt.set("mp3")

        ctk.CTkLabel(qual_grid, text="Audio Quality:", font=ctk.CTkFont(size=11)).grid(row=1, column=2, sticky="w", padx=(20,0), pady=(10,0))
        self.aud_qual = ctk.CTkComboBox(qual_grid, values=["0 (Best)", "1", "2", "3", "4", "5 (Worst)"], width=120)
        self.aud_qual.grid(row=1, column=3, padx=10, pady=(10,0))
        self.aud_qual.set("0 (Best)")

        # Time Range
        time_card = self.create_modern_card(frame, "⏱️ TIME RANGE (Optional)", 3)

        time_frame = ctk.CTkFrame(time_card, fg_color="transparent")
        time_frame.pack(fill="x", padx=15, pady=15)

        ctk.CTkLabel(time_frame, text="Start:").pack(side="left", padx=5)
        ctk.CTkEntry(time_frame, textvariable=self.time_start, width=100).pack(side="left", padx=5)

        ctk.CTkLabel(time_frame, text="End:").pack(side="left", padx=(20,5))
        ctk.CTkEntry(time_frame, textvariable=self.time_end, width=100).pack(side="left", padx=5)

        ctk.CTkCheckBox(time_frame, text="Full Video", variable=ctk.BooleanVar(value=True)).pack(side="right", padx=20)

        # Main Download Button
        dl_frame = ctk.CTkFrame(frame, fg_color="transparent")
        dl_frame.grid(row=4, column=0, sticky="ew", pady=20)

        self.main_dl_btn = ctk.CTkButton(
            dl_frame,
            text="🚀 START DOWNLOAD",
            height=60,
            font=ctk.CTkFont(size=20, weight="bold"),
            fg_color="#6366f1",
            text_color="#000",
            hover_color="#4f46e5",
            command=self.start_main_download
        )
        self.main_dl_btn.pack(fill="x", padx=15)

    def create_preview_tab(self):
        """Preview & Trim tab: paste a link, watch it, drag a range, download just that clip"""
        frame = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        self.tab_contents["preview"] = frame
        frame.grid_columnconfigure(0, weight=1)

        # --- Link + Load ---
        url_card = self.create_modern_card(frame, "🔗 PASTE LINK TO PREVIEW", 0)
        row = ctk.CTkFrame(url_card, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=15)

        ctk.CTkEntry(
            row, textvariable=self.url, placeholder_text="https://youtube.com/watch?v=...",
            height=45, font=ctk.CTkFont(size=13), border_color="#6366f1", border_width=1,
            corner_radius=10, fg_color="#12141b"
        ).pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.load_preview_btn = ctk.CTkButton(
            row, text="▶ Load Preview", width=150, height=45,
            fg_color="#6366f1", text_color="#000", hover_color="#4f46e5",
            command=self.load_preview
        )
        self.load_preview_btn.pack(side="right")

        # --- Video panel ---
        video_card = self.create_modern_card(frame, "🎥 PREVIEW", 1)

        self.video_panel = tk.Frame(video_card, bg="black", height=380)
        self.video_panel.pack(fill="x", padx=15, pady=(15, 5))
        self.video_panel.pack_propagate(False)

        if not VLC_AVAILABLE:
            tk.Label(
                self.video_panel, bg="black", fg="#8b93a8",
                text="Inline preview needs python-vlc + VLC Media Player installed.\n"
                     "(pip install python-vlc)  --  trimming/downloading still works without it.",
                justify="center"
            ).place(relx=0.5, rely=0.5, anchor="center")

        self.preview_status_label = ctk.CTkLabel(
            video_card, text="Paste a link above and click Load Preview",
            text_color="#8b93a8", font=ctk.CTkFont(size=11)
        )
        self.preview_status_label.pack(anchor="w", padx=15, pady=(0, 10))

        controls = ctk.CTkFrame(video_card, fg_color="transparent")
        controls.pack(fill="x", padx=15, pady=(0, 15))

        self.play_pause_btn = ctk.CTkButton(
            controls, text="▶ Play", width=90, state="disabled", command=self.toggle_play
        )
        self.play_pause_btn.pack(side="left", padx=(0, 10))

        self.playback_time_label = ctk.CTkLabel(
            controls, text="00:00:00 / 00:00:00", font=ctk.CTkFont(family="Consolas", size=12)
        )
        self.playback_time_label.pack(side="left", padx=10)

        self.playback_slider = ctk.CTkSlider(
            controls, from_=0, to=100, state="disabled", command=self.on_seek
        )
        self.playback_slider.set(0)
        self.playback_slider.pack(side="left", fill="x", expand=True, padx=10)

        # --- Trim range ---
        trim_card = self.create_modern_card(frame, "✂️ TRIM RANGE (pick how much you want)", 2)

        self.range_slider = RangeSlider(trim_card, from_=0, to=100, command=self.on_range_change)
        self.range_slider.pack(fill="x", padx=15, pady=(15, 5))

        time_row = ctk.CTkFrame(trim_card, fg_color="transparent")
        time_row.pack(fill="x", padx=15, pady=(5, 10))

        ctk.CTkLabel(time_row, text="Start:").pack(side="left", padx=(0, 5))
        self.trim_start_entry = ctk.CTkEntry(time_row, width=90)
        self.trim_start_entry.insert(0, "00:00:00")
        self.trim_start_entry.pack(side="left", padx=5)
        self.trim_start_entry.bind("<Return>", self.on_trim_entry_change)
        self.trim_start_entry.bind("<FocusOut>", self.on_trim_entry_change)

        ctk.CTkButton(
            time_row, text="⏺ From playhead", width=130,
            fg_color="#1c1f2a", command=lambda: self.set_trim_from_playhead("start")
        ).pack(side="left", padx=5)

        ctk.CTkLabel(time_row, text="End:").pack(side="left", padx=(20, 5))
        self.trim_end_entry = ctk.CTkEntry(time_row, width=90)
        self.trim_end_entry.insert(0, "00:00:00")
        self.trim_end_entry.pack(side="left", padx=5)
        self.trim_end_entry.bind("<Return>", self.on_trim_entry_change)
        self.trim_end_entry.bind("<FocusOut>", self.on_trim_entry_change)

        ctk.CTkButton(
            time_row, text="⏺ From playhead", width=130,
            fg_color="#1c1f2a", command=lambda: self.set_trim_from_playhead("end")
        ).pack(side="left", padx=5)

        self.trim_duration_label = ctk.CTkLabel(
            trim_card, text="Clip length: 00:00:00", font=ctk.CTkFont(size=11), text_color="#34d399"
        )
        self.trim_duration_label.pack(anchor="w", padx=15, pady=(0, 10))

        # --- Burn-in subtitles (hardcoded into the video at a chosen font size) ---
        sub_row = ctk.CTkFrame(trim_card, fg_color="transparent")
        sub_row.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkCheckBox(
            sub_row, text="🔤 Burn-in Subtitles", variable=self.burn_subtitles
        ).pack(side="left", padx=(0, 15))

        ctk.CTkLabel(sub_row, text="Font Size:").pack(side="left", padx=(0, 5))
        self.trim_font_size_combo = ctk.CTkComboBox(
            sub_row, values=["16", "18", "20", "22", "24", "25", "28", "32"],
            variable=self.subtitle_font_size, width=80
        )
        self.trim_font_size_combo.pack(side="left", padx=5)

        ctk.CTkLabel(sub_row, text="Lang:").pack(side="left", padx=(20, 5))
        ctk.CTkEntry(sub_row, textvariable=self.sub_langs, width=60).pack(side="left", padx=5)

        ctk.CTkLabel(
            sub_row, text="(needs subtitles/captions available for the video)",
            font=ctk.CTkFont(size=10), text_color="#8b93a8"
        ).pack(side="left", padx=(15, 0))

        dl_row = ctk.CTkFrame(trim_card, fg_color="transparent")
        dl_row.pack(fill="x", padx=15, pady=(0, 15))

        ctk.CTkLabel(dl_row, text="Save as:").pack(side="left", padx=(0, 5))
        self.trim_format_combo = ctk.CTkComboBox(dl_row, values=["mp4", "mkv", "webm", "mp3", "m4a"], width=100)
        self.trim_format_combo.set("mp4")
        self.trim_format_combo.pack(side="left", padx=5)

        self.download_trim_btn = ctk.CTkButton(
            dl_row, text="✂️ DOWNLOAD TRIMMED CLIP", height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#fb7185", hover_color="#e11d48",
            command=self.download_trimmed_clip
        )
        self.download_trim_btn.pack(side="right", fill="x", expand=True, padx=(10, 0))

    # --- Preview & Trim: loading the video ---

    def load_preview(self):
        url = self.url.get().strip()
        if not url:
            messagebox.showerror("Error", "Please paste a YouTube link first")
            return

        if not VLC_AVAILABLE:
            self.log("⚠️ python-vlc not installed — fetching info only, no inline playback.")

        self.load_preview_btn.configure(state="disabled", text="⏳ Loading...")
        self.preview_status_label.configure(text="Fetching video info...", text_color="#8b93a8")
        threading.Thread(target=self._load_preview_async, args=(url,), daemon=True).start()

    def _load_preview_async(self, url):
        # YouTube's available formats vary by which internal "client" yt-dlp
        # queries (web/android/tv/etc), and can shift between requests. Try a
        # few combinations instead of one rigid selector so preview loading
        # is resilient instead of failing outright on the first miss.
        attempts = [
            {"fmt": "best[ext=mp4]/best", "client": "web,tv,android"},
            {"fmt": "best", "client": "web,tv,android,ios,mweb"},
            {"fmt": "18/best", "client": None},
        ]

        last_error = "Could not fetch video info"
        for i, attempt in enumerate(attempts, start=1):
            try:
                cmd = [str(self.yt_dlp_path), "-f", attempt["fmt"], "-j", "--no-warnings"]
                if attempt["client"]:
                    cmd.extend(["--extractor-args", f"youtube:player_client={attempt['client']}"])
                if self.use_cookies.get() and self.cookies_path.exists():
                    cmd.extend(["--cookies", str(self.cookies_path)])
                cmd.append(url)

                if i > 1:
                    self.after(0, self._preview_retrying, i, len(attempts))

                result = subprocess.run(
                    cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore",
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    timeout=60
                )
                if result.returncode != 0:
                    last_error = (result.stderr or "Could not fetch video info").strip()[-400:]
                    continue

                info = json.loads(result.stdout)

                stream_url = info.get("url")
                headers = info.get("http_headers") or {}
                if not stream_url and info.get("requested_formats"):
                    # No single progressive stream -- fall back to the video-only
                    # stream so preview still shows something (audio may be missing)
                    rf = info["requested_formats"][0]
                    stream_url = rf.get("url")
                    headers = rf.get("http_headers") or headers

                if not stream_url:
                    last_error = "No playable stream URL returned for this video"
                    continue

                self.after(0, self._preview_loaded, stream_url, info.get("duration") or 0,
                           info.get("title", ""), headers)
                return
            except Exception as e:
                last_error = str(e)
                continue

        self.after(0, self._preview_failed, last_error)

    def _preview_retrying(self, attempt_num, total):
        self.preview_status_label.configure(
            text=f"First method failed, trying alternate method ({attempt_num}/{total})...",
            text_color="#8b93a8"
        )

    def _preview_failed(self, error):
        self.load_preview_btn.configure(state="normal", text="▶ Load Preview")
        self.preview_status_label.configure(text=f"❌ {error}", text_color="#fb7185")
        self.log(f"❌ Preview failed: {error}")

    def _preview_loaded(self, stream_url, duration, title, headers=None):
        self.load_preview_btn.configure(state="normal", text="▶ Load Preview")
        self.preview_duration = duration or 1
        self.preview_status_label.configure(
            text=f"{title}  •  {seconds_to_hhmmss(duration)}", text_color="#34d399"
        )
        self.log(f"✅ Preview loaded: {title}")

        self.range_slider.set_range(0, self.preview_duration)
        self.range_slider.set_values(0, self.preview_duration)
        self._sync_trim_entries(0, self.preview_duration)

        self.playback_slider.configure(from_=0, to=self.preview_duration, state="normal")
        self.playback_slider.set(0)

        if VLC_AVAILABLE and stream_url:
            self._start_vlc_playback(stream_url, headers or {})
        else:
            self.preview_status_label.configure(
                text=self.preview_status_label.cget("text") + "  (install python-vlc + VLC to watch inline)"
            )

    @staticmethod
    def _get_header(headers, name):
        """Case-insensitive lookup in a headers dict"""
        for k, v in (headers or {}).items():
            if k.lower() == name.lower():
                return v
        return None

    def _start_vlc_playback(self, stream_url, headers=None):
        try:
            if self.vlc_player:
                self.vlc_player.stop()
            if not self.vlc_instance:
                self.vlc_instance = vlc.Instance()
            self.vlc_player = self.vlc_instance.media_player_new()
            media = self.vlc_instance.media_new(stream_url)

            # YouTube's stream URL is tied to the User-Agent (and sometimes Referer)
            # yt-dlp used to fetch it -- without matching headers, googlevideo.com
            # returns HTTP 403. Forward the exact headers yt-dlp reports.
            ua = self._get_header(headers, "User-Agent") or (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            referer = self._get_header(headers, "Referer") or "https://www.youtube.com/"
            media.add_option(f":http-user-agent={ua}")
            media.add_option(f":http-referrer={referer}")

            self.vlc_player.set_media(media)

            handle = self.video_panel.winfo_id()
            if os.name == "nt":
                self.vlc_player.set_hwnd(handle)
            elif sys.platform == "darwin":
                self.vlc_player.set_nsobject(handle)
            else:
                self.vlc_player.set_xwindow(handle)

            self.vlc_player.play()
            self.play_pause_btn.configure(state="normal", text="⏸ Pause")

            if self._playback_job:
                self.after_cancel(self._playback_job)
            self._schedule_playback_update()
        except Exception as e:
            self.log(f"❌ VLC playback error: {e}")

    # --- Preview & Trim: playback controls ---

    def toggle_play(self):
        if not self.vlc_player:
            return
        if self.vlc_player.is_playing():
            self.vlc_player.pause()
            self.play_pause_btn.configure(text="▶ Play")
        else:
            self.vlc_player.play()
            self.play_pause_btn.configure(text="⏸ Pause")

    def on_seek(self, value):
        if self.vlc_player and self.preview_duration:
            try:
                self.vlc_player.set_time(int(float(value) * 1000))
            except Exception:
                pass

    def _schedule_playback_update(self):
        self._update_playback_ui()
        self._playback_job = self.after(500, self._schedule_playback_update)

    def _update_playback_ui(self):
        if not self.vlc_player:
            return
        try:
            length_ms = self.vlc_player.get_length()
            time_ms = self.vlc_player.get_time()
            if length_ms and length_ms > 0:
                dur = length_ms / 1000
                cur = max(0, time_ms / 1000)
                self.playback_slider.set(cur)
                self.playback_time_label.configure(
                    text=f"{seconds_to_hhmmss(cur)} / {seconds_to_hhmmss(dur)}"
                )
        except Exception:
            pass

    # --- Preview & Trim: range selection ---

    def on_range_change(self, start_val, end_val):
        self._sync_trim_entries(start_val, end_val)

    def _sync_trim_entries(self, start_val, end_val):
        self.trim_start_entry.delete(0, "end")
        self.trim_start_entry.insert(0, seconds_to_hhmmss(start_val))
        self.trim_end_entry.delete(0, "end")
        self.trim_end_entry.insert(0, seconds_to_hhmmss(end_val))
        clip_len = max(0, end_val - start_val)
        self.trim_duration_label.configure(text=f"Clip length: {seconds_to_hhmmss(clip_len)}")

    def on_trim_entry_change(self, event=None):
        try:
            start_sec = hhmmss_to_seconds(self.trim_start_entry.get())
            end_sec = hhmmss_to_seconds(self.trim_end_entry.get())
            if end_sec <= start_sec:
                end_sec = start_sec + 1
            self.range_slider.set_values(start_sec, end_sec)
            self._sync_trim_entries(start_sec, end_sec)
        except Exception:
            self.log("⚠️ Invalid time format — use HH:MM:SS")

    def set_trim_from_playhead(self, which):
        if not self.vlc_player:
            messagebox.showinfo("Info", "Load and play the preview first")
            return
        cur_sec = max(0, self.vlc_player.get_time() / 1000)
        start_val, end_val = self.range_slider.get_values()
        if which == "start":
            start_val = cur_sec
        else:
            end_val = cur_sec
        if end_val <= start_val:
            end_val = start_val + 1
        self.range_slider.set_values(start_val, end_val)
        self._sync_trim_entries(start_val, end_val)

    # --- Preview & Trim: download the trimmed clip ---

    def download_trimmed_clip(self):
        url = self.url.get().strip()
        if not url:
            messagebox.showerror("Error", "Please paste a YouTube link first")
            return
        if self.is_downloading:
            messagebox.showwarning("Busy", "A download is already in progress")
            return

        try:
            start_sec = hhmmss_to_seconds(self.trim_start_entry.get())
            end_sec = hhmmss_to_seconds(self.trim_end_entry.get())
        except Exception:
            messagebox.showerror("Error", "Invalid start/end time — use HH:MM:SS")
            return

        if end_sec <= start_sec:
            messagebox.showerror("Error", "End time must be after start time")
            return

        start_hms = seconds_to_hhmmss(start_sec)
        end_hms = seconds_to_hhmmss(end_sec)
        out_fmt = self.trim_format_combo.get()
        is_audio = out_fmt in ("mp3", "m4a")
        burn_subs = self.burn_subtitles.get() and not is_audio

        cmd = [str(self.yt_dlp_path), "--newline", "--no-warnings"]

        if self.ffmpeg_path.exists():
            cmd.extend(["--ffmpeg-location", str(self.ffmpeg_path.parent)])

        if self.use_cookies.get() and self.cookies_path.exists():
            cmd.extend(["--cookies", str(self.cookies_path)])

        # download-sections cuts to the requested range; force-keyframes-at-cuts
        # re-encodes at the cut points so start/end land exactly where you picked
        cmd.extend(["--download-sections", f"*{start_hms}-{end_hms}"])
        cmd.append("--force-keyframes-at-cuts")

        # The "android_vr" client's stream URLs 403 when handed to ffmpeg for
        # section cuts (ffmpeg doesn't get the same header/session handling
        # yt-dlp's own downloader applies) -- steer around that client here.
        cmd.extend(["--extractor-args", "youtube:player_client=default,-android_vr"])

        if is_audio:
            cmd.append("--extract-audio")
            cmd.extend(["--audio-format", out_fmt])
        else:
            # Prefer plain HTTP/DASH formats over HLS (m3u8) — YouTube's HLS
            # "premium" streams (e.g. itag 616) constantly drop/reset the
            # connection when ffmpeg tries to seek/cut a section out of them,
            # which is what causes the download to stall for many minutes
            # with no real progress. Fall back to bestvideo+bestaudio only
            # if no non-HLS option exists for that video.
            cmd.extend(["-f",
                        "bestvideo[protocol^=http]+bestaudio[protocol^=http]/"
                        "best[protocol^=http]/bestvideo+bestaudio/best"])
            cmd.extend(["--merge-output-format", out_fmt])

        lang = self.sub_langs.get().strip() or "en"

        if burn_subs:
            # Fixed, predictable filename (no %(title)s) so we can find the
            # exact video + subtitle files afterwards to feed into ffmpeg
            base_name = f"clip_{int(time.time())}"
            cmd.extend(["-o", str(self.output_path / f"{base_name}.%(ext)s")])
            cmd.extend([
                "--write-subs", "--write-auto-subs",
                "--sub-langs", lang, "--sub-format", "srt/best",
                "--convert-subs", "srt"
            ])
        else:
            filename = "%(title)s_clip_%(section_start)s-%(section_end)s.%(ext)s"
            cmd.extend(["-o", str(self.output_path / filename)])

        cmd.append(url)

        self.log(f"✂️ Downloading trimmed clip: {start_hms} → {end_hms}")

        if burn_subs:
            font_size = self.subtitle_font_size.get().strip() or "20"
            video_path = self.output_path / f"{base_name}.{out_fmt}"
            srt_path = self.output_path / f"{base_name}.{lang}.srt"
            self.run_trim_and_burn(cmd, video_path, srt_path, font_size)
        else:
            self.run_command(cmd)

    def run_trim_and_burn(self, cmd, video_path, srt_path, font_size):
        """Download the trimmed clip, then hard-burn its subtitles into the
        video at the chosen font size using ffmpeg (runs after yt-dlp finishes)."""
        self.is_downloading = True
        self.main_dl_btn.configure(state="disabled")
        self.download_trim_btn.configure(state="disabled", text="⏳ WORKING...")
        self.stat_status.configure(text="DOWNLOADING", text_color="#fb7185")
        self.progress.start()

        self.log(f"Executing: {' '.join(cmd)}")

        thread = threading.Thread(
            target=self._run_trim_and_burn_async, args=(cmd, video_path, srt_path, font_size)
        )
        thread.daemon = True
        thread.start()

    def _run_trim_and_burn_async(self, cmd, video_path, srt_path, font_size):
        """Worker thread: run yt-dlp, then ffmpeg's subtitles filter to burn in text."""
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True, encoding='utf-8', errors='ignore', bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            self.current_process = proc

            for line in proc.stdout:
                if line:
                    self.after(0, self.log, line.strip())
                    if "KiB/s" in line or "MiB/s" in line:
                        speed = re.search(r'(\d+\.\d+)([KM]iB/s)', line)
                        if speed:
                            self.after(0, self.stat_speed.configure,
                                       {"text": f"{speed.group(1)} {speed.group(2)}"})

            proc.wait()

            if proc.returncode != 0:
                self.after(0, self.download_failed)
                return

            if not srt_path.exists():
                self.after(0, self.log,
                           "⚠️ No subtitles found for that language — keeping the clip without burned-in text.")
                self.after(0, self.download_success)
                return

            self.after(0, self.log, f"🔤 Burning subtitles into the video at font size {font_size}...")
            burned_path = video_path.with_name(video_path.stem + "_subtitled" + video_path.suffix)

            # ffmpeg's subtitles filter needs ':' escaped in the path (Windows drive letters etc)
            srt_filter_path = str(srt_path).replace("\\", "/").replace(":", "\\:")
            style = (
                f"FontSize={font_size},FontName=Arial,Bold=1,"
                "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                "BorderStyle=1,Outline=2,Shadow=0,MarginV=30"
            )

            ffmpeg_bin = str(self.ffmpeg_path) if self.ffmpeg_path.exists() else "ffmpeg"
            ffmpeg_cmd = [
                ffmpeg_bin, "-y", "-i", str(video_path),
                "-vf", f"subtitles='{srt_filter_path}':force_style='{style}'",
                "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                "-c:a", "copy",
                str(burned_path)
            ]

            burn_proc = subprocess.Popen(
                ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True, encoding='utf-8', errors='ignore', bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            self.current_process = burn_proc
            for line in burn_proc.stdout:
                if line:
                    self.after(0, self.log, line.strip())
            burn_proc.wait()

            if burn_proc.returncode == 0 and burned_path.exists():
                try:
                    video_path.unlink(missing_ok=True)
                    srt_path.unlink(missing_ok=True)
                except Exception:
                    pass
                self.after(0, self.log, f"✅ Subtitled clip saved: {burned_path.name}")
                self.after(0, self.download_success)
            else:
                self.after(0, self.log, "❌ Subtitle burn-in failed — the original clip is still in Downloads.")
                self.after(0, self.download_failed)

        except Exception as e:
            self.after(0, self.download_failed, str(e))
        finally:
            self.after(0, lambda: self.download_trim_btn.configure(
                state="normal", text="✂️ DOWNLOAD TRIMMED CLIP"))

    def create_video_tab(self):
        """Video specific options"""
        frame = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        self.tab_contents["video"] = frame

        # Video Selection
        card1 = self.create_modern_card(frame, "🎬 VIDEO SELECTION", 0)

        ctk.CTkLabel(card1, text="Format Selection:", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=15, pady=(10,0))
        ctk.CTkEntry(card1, textvariable=self.format_spec, placeholder_text="bestvideo[height<=1080]+bestaudio/best").pack(fill="x", padx=15, pady=5)

        opts = ctk.CTkFrame(card1, fg_color="transparent")
        opts.pack(fill="x", padx=15, pady=10)

        ctk.CTkCheckBox(opts, text="Prefer free formats", variable=self.prefer_free_formats).pack(side="left", padx=10)
        ctk.CTkCheckBox(opts, text="Check formats", variable=self.check_formats).pack(side="left", padx=10)
        ctk.CTkCheckBox(opts, text="Check all formats", variable=self.check_all_formats).pack(side="left", padx=10)

        # Output
        card2 = self.create_modern_card(frame, "📁 OUTPUT OPTIONS", 1)

        ctk.CTkLabel(card2, text="Merge Output Format:", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=15, pady=(10,0))
        ctk.CTkComboBox(card2, values=["mp4", "mkv", "webm", "avi", "mov"], variable=self.merge_output_format).pack(fill="x", padx=15, pady=5)

        ctk.CTkCheckBox(card2, text="Recode video (specify format)", variable=ctk.BooleanVar()).pack(anchor="w", padx=15, pady=5)

    def create_audio_tab(self):
        """Audio specific options"""
        frame = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        self.tab_contents["audio"] = frame

        card = self.create_modern_card(frame, "🎵 AUDIO EXTRACTION", 0)

        ctk.CTkCheckBox(card, text="Extract Audio Only", variable=self.extract_audio).pack(anchor="w", padx=15, pady=10)

        ctk.CTkLabel(card, text="Audio Format:", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=15)
        formats = ["mp3", "wav", "m4a", "flac", "aac", "opus", "vorbis"]
        for fmt in formats:
            ctk.CTkRadioButton(card, text=fmt.upper(), variable=self.audio_format, value=fmt).pack(anchor="w", padx=30)

        ctk.CTkCheckBox(card, text="Keep video after extraction", variable=self.keep_video).pack(anchor="w", padx=15, pady=10)

    def create_subs_tab(self):
        """Subtitle options"""
        frame = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        self.tab_contents["subs"] = frame

        card = self.create_modern_card(frame, "🌐 SUBTITLE OPTIONS", 0)

        ctk.CTkCheckBox(card, text="Write Subtitles", variable=self.write_subs).pack(anchor="w", padx=15, pady=10)
        ctk.CTkCheckBox(card, text="Write Auto-Generated Subtitles", variable=self.write_auto_subs).pack(anchor="w", padx=15, pady=10)
        ctk.CTkCheckBox(card, text="Embed Subtitles in Video", variable=self.embed_subs_pp).pack(anchor="w", padx=15, pady=10)
        ctk.CTkCheckBox(card, text="List Available Subtitles", variable=self.list_subs).pack(anchor="w", padx=15, pady=10)

        ctk.CTkLabel(card, text="Languages (comma separated):", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=15, pady=(10,0))
        ctk.CTkEntry(card, textvariable=self.sub_langs).pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(card, text="Subtitle Format:", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=15, pady=(10,0))
        ctk.CTkComboBox(card, values=["srt", "vtt", "ass", "lrc"], variable=self.sub_format).pack(fill="x", padx=15, pady=5)

    def create_post_tab(self):
        """Post-processing options"""
        frame = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        self.tab_contents["post"] = frame

        # Metadata
        card1 = self.create_modern_card(frame, "📊 METADATA", 0)
        ctk.CTkCheckBox(card1, text="Write info JSON", variable=self.write_info_json).pack(anchor="w", padx=15, pady=5)
        ctk.CTkCheckBox(card1, text="Write description", variable=self.write_description).pack(anchor="w", padx=15, pady=5)
        ctk.CTkCheckBox(card1, text="Add metadata to file", variable=self.add_metadata).pack(anchor="w", padx=15, pady=5)
        ctk.CTkCheckBox(card1, text="Write xattrs", variable=self.xattrs).pack(anchor="w", padx=15, pady=5)

        # Thumbnails
        card2 = self.create_modern_card(frame, "🖼️ THUMBNAILS", 1)
        ctk.CTkCheckBox(card2, text="Write thumbnail", variable=self.write_thumbnail).pack(anchor="w", padx=15, pady=5)
        ctk.CTkCheckBox(card2, text="Write all thumbnails", variable=self.write_all_thumbnails).pack(anchor="w", padx=15, pady=5)
        ctk.CTkCheckBox(card2, text="Embed thumbnail", variable=self.embed_thumbnail).pack(anchor="w", padx=15, pady=5)

        # SponsorBlock
        card3 = self.create_modern_card(frame, "🚫 SPONSORBLOCK", 2)
        ctk.CTkLabel(card3, text="Remove:", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=15, pady=(10,0))
        ctk.CTkComboBox(card3, values=["", "sponsor", "sponsor,intro", "sponsor,outro", "all"], variable=self.sponsorblock_remove).pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(card3, text="Mark:", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=15, pady=(10,0))
        ctk.CTkComboBox(card3, values=["", "sponsor", "all"], variable=self.sponsorblock_mark).pack(fill="x", padx=15, pady=5)

        # Chapters
        card4 = self.create_modern_card(frame, "📑 CHAPTERS", 3)
        ctk.CTkCheckBox(card4, text="Split by chapters", variable=self.split_chapters).pack(anchor="w", padx=15, pady=5)
        ctk.CTkCheckBox(card4, text="Embed chapters", variable=self.embed_chapters).pack(anchor="w", padx=15, pady=5)
        ctk.CTkCheckBox(card4, text="No chapters", variable=self.no_chapters).pack(anchor="w", padx=15, pady=5)

    def create_network_tab(self):
        """Network options"""
        frame = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        self.tab_contents["network"] = frame

        card = self.create_modern_card(frame, "🌐 NETWORK SETTINGS", 0)

        ctk.CTkCheckBox(card, text="Use cookies.txt", variable=self.use_cookies).pack(anchor="w", padx=15, pady=10)
        ctk.CTkCheckBox(card, text="Skip unavailable fragments", variable=self.skip_unavailable).pack(anchor="w", padx=15, pady=10)
        ctk.CTkCheckBox(card, text="No certificate check", variable=self.no_check_certificate).pack(anchor="w", padx=15, pady=10)
        ctk.CTkCheckBox(card, text="Prefer insecure", variable=self.prefer_insecure).pack(anchor="w", padx=15, pady=10)
        ctk.CTkCheckBox(card, text="Geo bypass", variable=self.geo_bypass).pack(anchor="w", padx=15, pady=10)

        ctk.CTkLabel(card, text="Proxy:", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=15, pady=(10,0))
        ctk.CTkEntry(card, textvariable=self.proxy, placeholder_text="http://proxy:8080").pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(card, text="Socket Timeout:", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=15, pady=(10,0))
        ctk.CTkEntry(card, textvariable=self.socket_timeout).pack(fill="x", padx=15, pady=5)

    def create_batch_tab(self):
        """Batch download"""
        frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.tab_contents["batch"] = frame
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        card = self.create_modern_card(frame, "📋 BATCH URLS (One per line)", 0)
        card.grid(row=0, column=0, sticky="nsew")

        self.batch_text = ctk.CTkTextbox(card, font=ctk.CTkFont(family="Consolas", size=11))
        self.batch_text.pack(fill="both", expand=True, padx=15, pady=15)

        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(0, 15))

        ctk.CTkButton(btn_frame, text="📂 Load File", command=self.load_batch).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="🧹 Clear", command=lambda: self.batch_text.delete("1.0", "end")).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="🚀 Download All", command=self.download_batch, fg_color="#6366f1", text_color="#000").pack(side="right", padx=5)

    def create_output_tab(self):
        """Output console"""
        frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.tab_contents["output"] = frame
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        # Output Text
        self.output_text = ctk.CTkTextbox(
            frame,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0a0b10",
            text_color="#34d399",
            wrap="none"
        )
        self.output_text.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Controls
        ctrl = ctk.CTkFrame(frame, fg_color="transparent")
        ctrl.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        ctk.CTkButton(ctrl, text="🧹 Clear", command=lambda: self.output_text.delete("1.0", "end"), fg_color="#1c1f2a").pack(side="left", padx=5)
        ctk.CTkButton(ctrl, text="💾 Save Log", command=self.save_log, fg_color="#1c1f2a").pack(side="left", padx=5)
        ctk.CTkButton(ctrl, text="⏹️ Stop", command=self.stop_download, fg_color="#fb7185").pack(side="right", padx=5)

    def create_modern_card(self, parent, title, row):
        """Create a modern card component"""
        card = ctk.CTkFrame(parent, fg_color="#1c1f2a", corner_radius=16, border_width=1, border_color="#262a38")
        card.grid(row=row, column=0, sticky="ew", padx=5, pady=8)
        card.grid_columnconfigure(0, weight=1)

        # Header
        header = ctk.CTkFrame(card, fg_color="#20242f", corner_radius=10, height=38)
        header.grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        header.grid_propagate(False)

        ctk.CTkLabel(
            header,
            text=title,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#fff"
        ).place(relx=0.02, rely=0.5, anchor="w")

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        content.grid_columnconfigure(0, weight=1)

        return content

    def create_status_bar(self):
        """Bottom status bar"""
        bar = ctk.CTkFrame(self, fg_color="#0a0b10", height=35, corner_radius=0)
        bar.grid(row=2, column=0, sticky="ew")
        bar.grid_propagate(False)

        self.status_text = ctk.CTkLabel(
            bar,
            text="Ready | HackBugs ULTRA Edition v3.0",
            font=ctk.CTkFont(size=11),
            text_color="#8b93a8"
        )
        self.status_text.place(relx=0.01, rely=0.5, anchor="w")

        self.progress = ctk.CTkProgressBar(bar, width=300, height=8, mode="indeterminate")
        self.progress.place(relx=0.99, rely=0.5, anchor="e")
        self.progress.set(0)

    # Action Methods
    def paste_url(self):
        try:
            import pyperclip
            self.url.set(pyperclip.paste())
        except:
            pass

    def analyze_video(self):
        self.log("Analyzing video...")
        self.build_and_run(["--dump-json"])

    def list_formats(self):
        self.log("Listing formats...")
        self.build_and_run(["--list-formats"])

    def load_batch(self):
        file = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file:
            with open(file) as f:
                self.batch_text.insert("end", f.read())

    def download_batch(self):
        urls = self.batch_text.get("1.0", "end").strip().split("\n")
        for url in urls:
            if url.strip():
                self.url.set(url.strip())
                self.start_main_download()

    def save_log(self):
        file = filedialog.asksaveasfilename(defaultextension=".txt")
        if file:
            with open(file, "w") as f:
                f.write(self.output_text.get("1.0", "end"))

    def stop_download(self):
        if self.current_process:
            self.current_process.terminate()
            self.log("⏹️ Download stopped")
            self.is_downloading = False
            self.main_dl_btn.configure(state="normal", text="🚀 START DOWNLOAD")

    def log(self, message):
        """Log to output"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.output_text.insert("end", f"[{timestamp}] {message}\n")
        self.output_text.see("end")

    def build_and_run(self, extra_args=None):
        """Build command and run"""
        cmd = [str(self.yt_dlp_path)]

        if extra_args:
            cmd.extend(extra_args)

        url = self.url.get()
        if url:
            cmd.append(url)
            self.run_command(cmd)

    def start_main_download(self):
        """Start main download with all options"""
        if self.is_downloading:
            return

        cmd = self.build_full_command()
        if cmd:
            self.run_command(cmd)

    def build_full_command(self):
        """Build complete command with all options"""
        url = self.url.get()
        if not url:
            messagebox.showerror("Error", "Please enter a URL")
            return None

        cmd = [str(self.yt_dlp_path)]

        # Basic
        cmd.extend(["--newline", "--no-warnings"])

        # Output
        cmd.extend(["-o", str(self.output_path / self.filename_template.get())])

        # Cookies
        if self.use_cookies.get() and self.cookies_path.exists():
            cmd.extend(["--cookies", str(self.cookies_path)])

        # Mode
        mode = self.mode_var.get()
        if mode == "audio":
            cmd.append("--extract-audio")
            cmd.extend(["--audio-format", self.aud_fmt.get()])
            qual = self.aud_qual.get().split()[0]
            cmd.extend(["--audio-quality", qual])
        elif mode == "best":
            cmd.extend(["-f", "bestvideo+bestaudio/best"])
        else:
            qual = self.vid_qual.get()
            if qual == "best":
                cmd.extend(["-f", "bestvideo+bestaudio/best"])
            elif qual == "1080p":
                cmd.extend(["-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]"])
            elif qual == "720p":
                cmd.extend(["-f", "bestvideo[height<=720]+bestaudio/best[height<=720]"])
            elif qual == "480p":
                cmd.extend(["-f", "bestvideo[height<=480]+bestaudio/best[height<=480]"])
            elif qual == "360p":
                cmd.extend(["-f", "bestvideo[height<=360]+bestaudio/best[height<=360]"])
            elif qual == "worst":
                cmd.extend(["-f", "worst"])

        # Format
        cmd.extend(["--merge-output-format", self.vid_fmt.get()])

        # Time range
        if self.time_start.get() != "00:00:00" or self.time_end.get() != "00:00:00":
            cmd.extend(["--download-sections", f"*{self.time_start.get()}-{self.time_end.get()}"])
            # Same android_vr + ffmpeg 403 workaround as the trim tab (see download_trimmed_clip)
            cmd.extend(["--extractor-args", "youtube:player_client=default,-android_vr"])

        # Network
        if self.proxy.get():
            cmd.extend(["--proxy", self.proxy.get()])
        if self.no_check_certificate.get():
            cmd.append("--no-check-certificate")
        if self.geo_bypass.get():
            cmd.append("--geo-bypass")

        # Performance
        cmd.extend(["--concurrent-fragments", str(self.concurrent_fragments.get())])
        cmd.extend(["--retries", str(self.retries.get())])
        cmd.extend(["--fragment-retries", str(self.fragment_retries.get())])
        if self.skip_unavailable.get():
            cmd.append("--skip-unavailable-fragments")

        # Subtitles
        if self.write_subs.get():
            cmd.extend(["--sub-langs", self.sub_langs.get()])
            cmd.append("--write-subs")
        if self.write_auto_subs.get():
            cmd.append("--write-auto-subs")
        if self.embed_subs_pp.get():
            cmd.append("--embed-subs")

        # Metadata
        if self.write_thumbnail.get():
            cmd.append("--write-thumbnail")
        if self.embed_thumbnail.get():
            cmd.append("--embed-thumbnail")
        if self.add_metadata.get():
            cmd.append("--add-metadata")
        if self.write_info_json.get():
            cmd.append("--write-info-json")

        # SponsorBlock
        if self.sponsorblock_remove.get():
            cmd.extend(["--sponsorblock-remove", self.sponsorblock_remove.get()])
        if self.sponsorblock_mark.get():
            cmd.extend(["--sponsorblock-mark", self.sponsorblock_mark.get()])

        # Chapters
        if self.split_chapters.get():
            cmd.append("--split-chapters")
        if self.embed_chapters.get():
            cmd.append("--embed-chapters")
        if self.no_chapters.get():
            cmd.append("--no-chapters")

        # Filesystem
        if self.restrict_filenames.get():
            cmd.append("--restrict-filenames")
        if self.no_overwrites.get():
            cmd.append("--no-overwrites")
        if self.continue_dl.get():
            cmd.append("--continue")

        # URL
        cmd.append(url)

        return cmd

    def run_command(self, cmd):
        """Execute command"""
        self.is_downloading = True
        self.main_dl_btn.configure(state="disabled", text="⏳ DOWNLOADING...")
        self.stat_status.configure(text="DOWNLOADING", text_color="#fb7185")
        self.progress.start()

        self.log(f"Executing: {' '.join(cmd)}")

        thread = threading.Thread(target=self._run_async, args=(cmd,))
        thread.daemon = True
        thread.start()

    def _run_async(self, cmd):
        """Run command in thread"""
        try:
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                encoding='utf-8',
                errors='ignore',
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            for line in self.current_process.stdout:
                if line:
                    self.after(0, self.log, line.strip())
                    # Parse speed for stats
                    if "KiB/s" in line or "MiB/s" in line:
                        speed = re.search(r'(\d+\.\d+)([KM]iB/s)', line)
                        if speed:
                            self.after(0, self.stat_speed.configure, 
                                     {"text": f"{speed.group(1)} {speed.group(2)}"})

            self.current_process.wait()

            if self.current_process.returncode == 0:
                self.after(0, self.download_success)
            else:
                self.after(0, self.download_failed)

        except Exception as e:
            self.after(0, self.download_failed, str(e))

    def download_success(self):
        """Handle success"""
        self.is_downloading = False
        self.progress.stop()
        self.progress.set(1)
        self.main_dl_btn.configure(state="normal", text="🚀 START DOWNLOAD")
        self.stat_status.configure(text="COMPLETED", text_color="#34d399")
        self.log("✅ Download completed successfully!")

        self.queue_counter += 1
        self.stat_total.configure(text=str(self.queue_counter))

    def download_failed(self, error=None):
        """Handle failure"""
        self.is_downloading = False
        self.progress.stop()
        self.progress.set(0)
        self.main_dl_btn.configure(state="normal", text="🚀 START DOWNLOAD")
        self.stat_status.configure(text="FAILED", text_color="#fb7185")
        if error:
            self.log(f"❌ Error: {error}")
        else:
            self.log("❌ Download failed")

    def startup_checks(self):
        """Check dependencies on startup"""
        if not self.yt_dlp_path.exists():
            self.log("⚠️ WARNING: yt-dlp.exe not found in base directory")
        else:
            self.log("✅ yt-dlp found")

        if not self.cookies_path.exists():
            self.log("⚠️ Cookies file not found")
        else:
            self.log("✅ Cookies found")

        if not VLC_AVAILABLE:
            self.log("⚠️ python-vlc not installed — Preview & Trim tab won't show inline video. "
                      "Run: pip install python-vlc (also needs VLC Media Player installed).")
        else:
            self.log("✅ python-vlc found — inline preview available")

        self.log("🚀 System ready!")

    def show_settings(self):
        """Show settings dialog"""
        messagebox.showinfo("Settings", "All settings available in respective tabs!")

    def show_help(self):
        """Show help"""
        help_text = """HackBugs ULTRA Edition Help

Quick Start:
1. Paste YouTube URL in Quick tab
2. Select download mode (Video/Audio/Playlist)
3. Adjust quality settings
4. Click START DOWNLOAD

Tips:
- Use Time Range to download sections
- Enable SponsorBlock to skip ads
- Use Batch tab for multiple URLs
- Check Output tab for live logs

All yt-dlp features are available in various tabs!"""
        messagebox.showinfo("Help", help_text)

if __name__ == "__main__":
    app = YouTubeDownloaderULTRA()
    app.mainloop()