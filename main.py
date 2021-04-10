import pyglet
pyglet.font.add_file('Lato-Light.ttf')
pyglet.font.add_file('IBMPlexMono-Thin.ttf')
default_font_m = ("Consolas", 11)
default_font_s = ("Consolas", 10)
default_font = ("Consolas", 12)

default_ui_font_l = ("Lato-Light", 16)
default_ui_font = ("Lato-Light", 12)
default_ui_font_s = ("Lato-Light", 10)

from shutil import copytree as copyfolder
from shutil import rmtree

import tkinter
import tkinter.ttk
from tkinter import ttk
import tkinter.font
import tkinter.filedialog
import time
import os
import os.path
import sys
import subprocess
import webbrowser

from pathlib import Path
path = Path(sys.argv[0])

global parent_folder
parent_folder = str(path.parent.absolute())

if (os.path.exists(f"{parent_folder}\\song_path.txt") == False):
    song_path = parent_folder
    with open(f"{parent_folder}\\song_path.txt", "w") as file:
        file.write(song_path)

else:
    with open(f"{parent_folder}\\song_path.txt", "r") as file:
        song_path = file.read()

import pychorus
from pyunpack import Archive
from PIL import ImageTk, Image

# Gdown functions:
import re
import warnings

from six.moves import urllib_parse


def parse_url(url, warning=True):
    """Parse URLs especially for Google Drive links.

    file_id: ID of file on Google Drive.
    is_download_link: Flag if it is download link of Google Drive.
    """
    parsed = urllib_parse.urlparse(url)
    query = urllib_parse.parse_qs(parsed.query)
    is_gdrive = parsed.hostname == "drive.google.com"
    is_download_link = parsed.path.endswith("/uc")

    file_id = None
    if is_gdrive and "id" in query:
        file_ids = query["id"]
        if len(file_ids) == 1:
            file_id = file_ids[0]
    match = re.match(r"^/file/d/(.*?)/view$", parsed.path)
    if match:
        file_id = match.groups()[0]

    if is_gdrive and not is_download_link:
        warnings.warn(
            "You specified Google Drive Link but it is not the correct link "
            "to download the file. Maybe you should try: {url}".format(
                url="https://drive.google.com/uc?id={}".format(file_id)
            )
        )

    return file_id, is_download_link


import json
import os
import os.path as osp
import re
import shutil
import sys
import tempfile
import textwrap
import time

import requests
import six
import tqdm


CHUNK_SIZE = 512 * 1024  # 512KB
home = osp.expanduser("~")


if hasattr(textwrap, "indent"):
    indent_func = textwrap.indent
else:

    def indent_func(text, prefix):
        def prefixed_lines():
            for line in text.splitlines(True):
                yield (prefix + line if line.strip() else line)

        return "".join(prefixed_lines())


def get_url_from_gdrive_confirmation(contents):
    url = ""
    for line in contents.splitlines():
        m = re.search(r'href="(\/uc\?export=download[^"]+)', line)
        if m:
            url = "https://docs.google.com" + m.groups()[0]
            url = url.replace("&amp;", "&")
            return url
        m = re.search("confirm=([^;&]+)", line)
        if m:
            confirm = m.groups()[0]
            url = re.sub(
                r"confirm=([^;&]+)", r"confirm={}".format(confirm), url
            )
            return url
        m = re.search('"downloadUrl":"([^"]+)', line)
        if m:
            url = m.groups()[0]
            url = url.replace("\\u003d", "=")
            url = url.replace("\\u0026", "&")
            return url
        m = re.search('<p class="uc-error-subcaption">(.*)</p>', line)
        if m:
            error = m.groups()[0]
            raise RuntimeError(error)


def gdown_download(
    url, output=None, quiet=False, proxy=None, speed=None, use_cookies=True
):
    """Download file from URL.

    Parameters
    ----------
    url: str
        URL. Google Drive URL is also supported.
    output: str, optional
        Output filename. Default is basename of URL.
    quiet: bool
        Suppress terminal output. Default is False.
    proxy: str
        Proxy.
    speed: float
        Download byte size per second (e.g., 256KB/s = 256 * 1024).
    use_cookies: bool
        Flag to use cookies. Default is True.

    Returns
    -------
    output: str
        Output filename.
    """
    url_origin = url
    sess = requests.session()

    # Load cookies
    cache_dir = osp.join(home, ".cache", "gdown")
    if not osp.exists(cache_dir):
        os.makedirs(cache_dir)
    cookies_file = osp.join(cache_dir, "cookies.json")
    if osp.exists(cookies_file) and use_cookies:
        with open(cookies_file) as f:
            cookies = json.load(f)
        for k, v in cookies:
            sess.cookies[k] = v

    if proxy is not None:
        sess.proxies = {"http": proxy, "https": proxy}
        print("Using proxy:", proxy, file=sys.stderr)

    file_id, is_download_link = parse_url(url)

    while True:

        try:
            res = sess.get(url, stream=True)
        except requests.exceptions.ProxyError as e:
            print("An error has occurred using proxy:", proxy, file=sys.stderr)
            print(e, file=sys.stderr)
            return

        # Save cookies
        with open(cookies_file, "w") as f:
            cookies = [
                (k, v)
                for k, v in sess.cookies.items()
                if not k.startswith("download_warning_")
            ]
            json.dump(cookies, f, indent=2)

        if "Content-Disposition" in res.headers:
            # This is the file
            break
        if not (file_id and is_download_link):
            break

        # Need to redirect with confirmation
        try:
            url = get_url_from_gdrive_confirmation(res.text)
        except RuntimeError as e:
            print("Access denied with the following error:")
            error = "\n".join(textwrap.wrap(str(e)))
            error = indent_func(error, "\t")
            print("\n", error, "\n", file=sys.stderr)
            print(
                "You may still be able to access the file from the browser:",
                file=sys.stderr,
            )
            print("\n\t", url_origin, "\n", file=sys.stderr)
            return

        if url is None:
            print("Permission denied:", url_origin, file=sys.stderr)
            print(
                "Maybe you need to change permission over "
                "'Anyone with the link'?",
                file=sys.stderr,
            )
            return

    if file_id and is_download_link:
        m = re.search('filename="(.*)"', res.headers["Content-Disposition"])
        filename_from_url = m.groups()[0]
    else:
        filename_from_url = osp.basename(url)

    if output is None:
        output = filename_from_url

    output_is_path = isinstance(output, six.string_types)
    if output_is_path and output.endswith(osp.sep):
        if not osp.exists(output):
            os.makedirs(output)
        output = osp.join(output, filename_from_url)

    if not quiet:
        print("Downloading...", file=sys.stderr)
        print("From:", url_origin, file=sys.stderr)
        print(
            "To:",
            osp.abspath(output) if output_is_path else output,
            file=sys.stderr,
        )

    if output_is_path:
        tmp_file = tempfile.mktemp(
            suffix=tempfile.template,
            prefix=osp.basename(output),
            dir=osp.dirname(output),
        )
        f = open(tmp_file, "wb")
    else:
        tmp_file = None
        f = output

    try:
        total = res.headers.get("Content-Length")
        if total is not None:
            total = int(total)
        if not quiet:
            pbar = tqdm.tqdm(total=total, unit="B", unit_scale=True)
        t_start = time.time()
        for chunk in res.iter_content(chunk_size=CHUNK_SIZE):
            f.write(chunk)
            if not quiet:
                pbar.update(len(chunk))
            if speed is not None:
                elapsed_time_expected = 1.0 * pbar.n / speed
                elapsed_time = time.time() - t_start
                if elapsed_time < elapsed_time_expected:
                    time.sleep(elapsed_time_expected - elapsed_time)
        if not quiet:
            pbar.close()
        if tmp_file:
            f.close()
            shutil.move(tmp_file, output)
    except IOError as e:
        print(e, file=sys.stderr)
        return
    finally:
        sess.close()
        try:
            if tmp_file:
                os.remove(tmp_file)
        except OSError:
            pass

    return output

############################

import shutil

from threading import Thread

from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw


global songs
songs = []
album_size = (400, 400)
current_song_link = ""

cjk_ranges = [
        (0x4E00,  0x62FF),
        (0x6300,  0x77FF),
        (0x7800,  0x8CFF),
        (0x8D00,  0x9FCC),
        (0x3400,  0x4DB5),
        (0x33a0,  0x30ff),
        (0x4e00,  0x9faf),
        (0x20000, 0x215FF),
        (0x21600, 0x230FF),
        (0x23100, 0x245FF),
        (0x24600, 0x260FF),
        (0x26100, 0x275FF),
        (0x27600, 0x290FF),
        (0x29100, 0x2A6DF),
        (0x2A700, 0x2B734),
        (0x2B740, 0x2B81D),
        (0x2B820, 0x2CEAF),
        (0x2CEB0, 0x2EBEF),
        (0x2F800, 0x2FA1F)
    ]
                     
def is_cjk(_char):
    ch = _char
    char = ord(_char)
    for bottom, top in cjk_ranges:
        if char >= bottom and char <= top:
            print(ch, "EEEEEEEEEEEEEEEEEEEEEEEEEEE")
            return True
    return False

def format_seconds(seconds):
    seconds = seconds % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60

    return "%d:%02d:%02d" % (hour, minutes, seconds)

def song_info_format(name, artist, album, genre):
    result = ""
    if (name == None):
        name = "not defined"

    if (artist == None):
        artist = "not defined"

    if (album == None):
        album = "not defined"

    if (genre == None):
        genre = "not defined"

    cjk_count_name = 0
    cjk_count_artist = 0
    cjk_count_album = 0
    cjk_count_genre = 0
    
    for char in name:
        #print(char)
        if (is_cjk(char)):
            cjk_count_name + 1

    for char in artist:
        if (is_cjk(char)):
            cjk_count_artist + 1

    for char in album:
        if (is_cjk(char)):
            cjk_count_album + 1

    for char in genre:
        if (is_cjk(char)):
            cjk_count_genre + 1


    if (len(name) > 50):
        name = name[:46] + "..."

    if (len(artist) > 50):
        artist = artist[:46] + "..."

    if (len(album) > 50):
        album = album[:46] + "..."

    if (len(genre) > 50):
        genre = genre[:46] + "..."

    result += name
    result += " " * ((50 - cjk_count_name) - len(result))

    result += artist
    result += " " * ((100 - cjk_count_artist) - len(result))

    result += album
    result += " " * ((150 - cjk_count_album) - len(result))

    result += genre

    return result

def disable_search():
    # Prevents the user from searching like 20 times
    search_entry.unbind("<Return>")
    adv_song_entry.unbind("<Return>")
    adv_artist_entry.unbind("<Return>")
    adv_album_entry.unbind("<Return>")
    adv_genre_entry.unbind("<Return>")
    adv_year_entry.unbind("<Return>")
    adv_charter_entry.unbind("<Return>")

def enable_search():
    search_entry.bind("<Return>", search)
    adv_song_entry.bind("<Return>", advanced_search)
    adv_artist_entry.bind("<Return>", advanced_search)
    adv_album_entry.bind("<Return>", advanced_search)
    adv_genre_entry.bind("<Return>", advanced_search)
    adv_year_entry.bind("<Return>", advanced_search)
    adv_charter_entry.bind("<Return>", advanced_search)
    
def _update_song_list():
    global songs

    for i, song, in enumerate(songs):
        song_list.insert(i, song_info_format(song.name, song.artist, song.album, song.genre))
        if ((i) % 2): song_list.itemconfig(i, bg = "#ebebeb")

def advanced_search(event):
    search_thread = Thread(target=_advanced_search)
    search_thread.start()

def _advanced_search():

    # Prevents the user from searching like 20 times
    disable_search()
    
    global songs
    returned_songs = []
    existing_ids = []

    song_list.delete(0, 'end')
    songs = []

    _page = -1

    searching = True

    global search_progress
    adv_search_progress.pack(side = "left", padx = (5, 0), pady = 5)
    adv_search_progress.start()

    global search_result
    try:
        adv_search_result.pack_forget()

    except:
        pass
    adv_search_amount.pack(side = "left", padx = (5, 0), pady = 5)
    adv_search_amount["text"] = f"Songs found: {len(songs)}"

    kwargs = {}

    songname = adv_song_entry.get()
    if (songname != "Song name . . .       "): kwargs["name"] = songname

    artistname = adv_artist_entry.get()
    if (artistname != "Artist name . . .       "): kwargs["artist"] = artistname

    albumname = adv_album_entry.get()
    if (albumname != "Album name . . .       "): kwargs["album"] = albumname

    genrename = adv_genre_entry.get()
    if (genrename != "Genre . . .       "): kwargs["genre"] = genrename

    year = adv_year_entry.get()
    if (year != "Year . . .       "): kwargs["year"] = year

    chartername = adv_charter_entry.get()
    if (chartername != "Charter's name . . .       "): kwargs["charter"] = chartername

    while (True):
        _page += 1

        try:
            result = pychorus.search(**kwargs, page = _page)
            for i, song in enumerate(result):

                if (song == None):
                    continue

                if (song.id in existing_ids):
                    continue

                returned_songs.append(song)
                existing_ids.append(song.id)

                songs.append(song)
                adv_search_amount["text"] = f"Songs found: {len(songs)}"

        except pychorus.PageNotFoundError:
            adv_search_progress.stop()
            adv_search_progress.pack_forget()
            adv_search_amount.pack_forget()
            adv_search_result.pack(side = "left", padx = (5, 0), pady = 5)
            adv_search_result["text"] = f"Showing {len(songs)} results"

            _update_song_list()

            # Restore search function
            enable_search()
            return

def search(event):
    search_thread = Thread(target=_search)
    search_thread.start()

def _search():
    disable_search()
    global songs
    query = search_entry.get()

    returned_songs = []

    existing_ids = []

    song_list.delete(0, 'end')
    songs = []

    _page = -1
    
    root.grab_set()

    searching = True

    global search_progress
    search_progress.pack(side = "left", padx = (5, 0), pady = 5)
    search_progress.start()

    global search_result
    try:
        search_result.pack_forget()

    except:
        pass
    search_amount.pack(side = "left", padx = (5, 0), pady = 5)
    search_amount["text"] = f"Songs found: {len(songs)}"

    while (True):
        _page += 1

        try:
            result = pychorus.search(generic = query, page = _page)
            for i, song in enumerate(result):

                if (song == None):
                    continue

                if (song.id in existing_ids):
                    continue

                returned_songs.append(song)
                existing_ids.append(song.id)

                songs.append(song)
                search_amount["text"] = f"Songs found: {len(songs)}"

        except pychorus.PageNotFoundError:
            search_progress.stop()
            search_progress.pack_forget()
            search_amount.pack_forget()
            search_result.pack(side = "left", padx = (5, 0), pady = 5)
            search_result["text"] = f"Showing {len(songs)} results for \"{query}\""

            _update_song_list()
            enable_search()
            return

def remove_bad_path_chars(string):
    return string.replace(":", "").replace("<", "").replace(">", "").replace("*", "").replace("\"", "").replace("|", "").replace("/", "").replace("?", "")

def _download_song():
    global gdown
    global download_window

    global songs
    w = song_list
    print(w.curselection())
    index = int(w.curselection()[0])
    value = w.get(index)

    song = songs[index]
    download_window = tkinter.Toplevel(root)

    download_window.grab_set()

    info = tkinter.Label(download_window, text = f"Downloading \"{song.name}\" . . .")
    info.pack(padx = 10, pady = 10)

    progress = tkinter.ttk.Progressbar(download_window, orient = tkinter.HORIZONTAL, length = 200, mode = 'indeterminate')
    progress.pack(padx = 10, pady = 10)

    progress.start()
    global current_song_link
    global song_path

    print(song.all_info())
    
    filename = song.download()
    print("filename:", filename)

    ext = os.path.splitext(filename)[1]
    info["text"] = f"Extracting \"{filename}\" . . ."

    if (ext == ".zip"):
        shutil.unpack_archive(filename, ".")

    else:
        Archive(filename).extractall(".")
    
    info["text"] = f"Cleaning up . . ."

    good_name = remove_bad_path_chars(song.name)

    try:
        os.rename(f"{remove_bad_path_chars(song.artist)} - {remove_bad_path_chars(song.name)}", good_name)

    except FileNotFoundError:
        pass#os.rename(f"{remove_bad_path_chars(song.name)}", good_name)
        
    try:
        CREATE_NO_WINDOW = 0x08000000
        subprocess.call(f"robocopy \"{good_name}\" \"{song_path}\\{os.path.splitext(good_name)[0]}\"  /NFL /NDL /NJH /NJS /nc /ns /np", creationflags=CREATE_NO_WINDOW)
        #copyfolder(good_name, f"{song_path}\\{os.path.splitext(good_name)[0]}")

    except FileExistsError:
        pass
    
    os.remove(filename)
    rmtree(os.path.splitext(filename)[0])
    
    progress.stop()
    download_window.destroy()


def download_song():
    global download_window
    download_thread = Thread(target = _download_song)
    download_thread.start()

def update_song_panel(event):
    update_thread = Thread(target = _update_song_panel, args = (event,))
    update_thread.start()

def _update_song_panel(event):
    global gdown
    global songs
    w = event.widget
    index = int(w.curselection()[0])
    value = w.get(index)
    song = songs[index]

    tmp = Image.open(f"{parent_folder}\\assets\\empty.png")
    tmp = tmp.resize(album_size)
    img = ImageTk.PhotoImage(tmp)

    song_album_cover.configure(image=img)
    song_album_cover.image = img

    song_name["text"] = song.name
    artist_name["text"] = song.artist
    song_length["text"] = f"Song length: {format_seconds(song.length)}"
    song_year["text"] = f"Song released: {song.year}"
    song_charter["text"] = f"Charted by: {song.charter}"

    link = song.link
    global current_song_link
    current_song_link = song.link

    song_link["text"] = link

    download_song.pack(side = "bottom", pady = 25)

    if (hasattr(song, "directLinks")):
        try:
            filename = gdown_download(song.directLinks["album.png"], f"{parent_folder}\\asset\\album.png", quiet = True)
            album_filename = f"{parent_folder}\\assets\\album.png"
        except:
            try:
                filename = gdown_download(song.directLinks["album.jpg"], f"{parent_folder}\\assets\\album.jpg",quiet = True)
                album_filename = f"{parent_folder}\\assets\\album.jpg"

            except:
                tmp = Image.open(f"{parent_folder}\\assets\\empty.png")
                tmp = tmp.resize(album_size)
                song_album_cover["text"] = "Album preview not available"

                img = ImageTk.PhotoImage(tmp)
                song_album_cover.configure(image=img)
                song_album_cover.image = img
                return

    song_album_cover["text"] = ""
    tmp = Image.open(album_filename)
    tmp = tmp.resize(album_size)
    img = ImageTk.PhotoImage(tmp)

    song_album_cover.configure(image=img)
    song_album_cover.image = img

def set_song_path():
    folder_selected = tkinter.filedialog.askdirectory(title = "Select your Clone Hero songs folder.")
    if (folder_selected == ""):
        return

    with open("song_path.txt", "w") as file:
        file.write(folder_selected)

    song_path = folder_selected
    print(song_path)
    song_path_var.set(song_path)

class PlaceholderEntry(tkinter.Entry):
    def __init__(self, master=None, placeholder="PLACEHOLDER", color='grey'):
        super().__init__(master)

        self.placeholder = placeholder
        self.placeholder_color = color
        self.default_fg_color = self['fg']

        self['font'] = default_ui_font
        self['selectbackground'] = "#c9c9c9"
        self['selectforeground'] = "black"
        self.bind("<FocusIn>", self.foc_in)
        self.bind("<FocusOut>", self.foc_out)

        self.put_placeholder()

    def put_placeholder(self):
        self.insert(0, self.placeholder)
        self['fg'] = self.placeholder_color

    def foc_in(self, *args):
        if self['fg'] == self.placeholder_color:
            self.delete('0', 'end')
            self['fg'] = self.default_fg_color

    def foc_out(self, *args):
        if not self.get():
            self.put_placeholder()


root = tkinter.Tk()

#root = tkinter.Tk()#(theme="breeze")

# Remove the "dotted" focus from ttk.Notebook tabs:
style = tkinter.ttk.Style()

style.layout("Tab",
[('Notebook.tab', {'sticky': 'nswe', 'children':
    [('Notebook.padding', {'side': 'top', 'sticky': 'nswe', 'children':
        #[('Notebook.focus', {'side': 'top', 'sticky': 'nswe', 'children':
            [('Notebook.label', {'side': 'top', 'sticky': ''})],
        #})],
    })],
})]
)



# Change the font of ttk.Notebook:
style.configure('TNotebook.Tab', font = default_ui_font)
style.configure('TButton', font = default_ui_font_l)

### Begin window layout:
notebook = tkinter.ttk.Notebook(root, takefocus = False)
notebook.pack(expand = True, fill = "both")


## Browse frame:
browse_frame = tkinter.Frame(notebook, bg = "white")

# Song Panel:
song_panel = tkinter.Frame(browse_frame)
song_panel.pack(side = "right", fill = "y", padx = 5, pady = 5, ipadx = 5, ipady = 5)

tmp = Image.open(f"{parent_folder}\\assets\\empty.png")
tmp = tmp.resize(album_size)
img = ImageTk.PhotoImage(tmp)

song_album_cover = tkinter.Label(song_panel, image = img, compound = "center", text = "", font = default_ui_font_l)
song_album_cover.pack(side = "top", anchor = "n", pady = 5)

song_name = tkinter.Label(song_panel, text = "", font = default_ui_font_l, wraplength = 350, justify = "center")
song_name.pack(anchor = "n", pady = 5)

artist_name = tkinter.Label(song_panel, text = "", font = default_ui_font_l, wraplength = 350, justify = "center")
artist_name.pack(anchor = "n", pady = 5)

song_info_panel = tkinter.Frame(song_panel, bg = "#f5f5f5")
song_info_panel.pack(expand = True, fill = "both", padx = 5, pady = 5, ipadx = 5, ipady = 5)

song_charter = tkinter.Label(song_info_panel, text = "", bg = "#f5f5f5", font = default_ui_font)
song_charter.pack(anchor = "nw", padx = 5, pady = 2)

song_length = tkinter.Label(song_info_panel, text = "", bg = "#f5f5f5", font = default_ui_font)
song_length.pack(anchor = "nw", padx = 5, pady = 2)

song_year = tkinter.Label(song_info_panel, text = "", bg = "#f5f5f5", font = default_ui_font)
song_year.pack(anchor = "nw", padx = 5, pady = 2)

song_link = tkinter.Label(song_info_panel, text = "", wraplength = 350, justify = "left", fg = "#0645AD", bg = "#f5f5f5", font = default_ui_font)
song_link.bind("<Button-1>", lambda n: webbrowser.open(current_song_link, new = 0))
song_link.pack(anchor = "nw", padx = 5, pady = 2)

download_song = tkinter.ttk.Button(song_panel, text = "Download song", takefocus = False, command = download_song)
download_song.pack(side = "bottom", pady = 25)
download_song.pack_forget()


# Search bar:
search_bar = tkinter.Frame(browse_frame)
search_bar.pack(side = "top", anchor = "w", fill = "x", padx = (5, 0), pady = 5, ipadx = 5, ipady = 5)

search_type = tkinter.ttk.Notebook(search_bar, takefocus = False)

# Normal Search:
regular_search = tkinter.Frame(search_type)
regular_search.pack(fill = "x", expand = True)

search_entry = PlaceholderEntry(regular_search, placeholder = "Search . . .")
search_entry.pack(side = "left", padx = (5, 0), pady = 5)
search_entry.bind("<Return>", search)

search_progress = tkinter.ttk.Progressbar(regular_search, orient = tkinter.HORIZONTAL, length = 200, mode = 'indeterminate')
search_progress.pack(side = "left", padx = (5, 0), pady = 5)
search_progress.pack_forget()

search_amount = tkinter.Label(regular_search, text = "", font = default_ui_font)
search_amount.pack(side = "left", padx = (5, 0), pady = 5)
search_amount.pack_forget()

search_result = tkinter.Label(regular_search, text = "", font = default_ui_font)
search_result.pack(side = "left", padx = (5, 0), pady = 5)
search_result.pack_forget()

search_type.add(regular_search, text = "Normal Search")


# Advanced Search:

adv_search = tkinter.Frame(search_type)

adv_song_entry = PlaceholderEntry(adv_search, placeholder = "Song name . . .       ")
adv_song_entry.pack(side = "left", padx = 5, pady = 5)

adv_artist_entry = PlaceholderEntry(adv_search, placeholder = "Artist name . . .       ")
adv_artist_entry.pack(side = "left", padx = 5, pady = 5)

adv_album_entry = PlaceholderEntry(adv_search, placeholder = "Album name . . .       ")
adv_album_entry.pack(side = "left", padx = 5, pady = 5)

adv_genre_entry = PlaceholderEntry(adv_search, placeholder = "Genre . . .       ")
adv_genre_entry.pack(side = "left", padx = 5, pady = 5)

adv_year_entry = PlaceholderEntry(adv_search, placeholder = "Year . . .       ")
adv_year_entry.configure(width = int(adv_year_entry["width"] * 0.66))
adv_year_entry.pack(side = "left", padx = 5, pady = 5)

adv_charter_entry = PlaceholderEntry(adv_search, placeholder = "Charter's name . . .       ")
adv_charter_entry.pack(side = "left", padx = 5, pady = 5)

adv_search_progress = tkinter.ttk.Progressbar(adv_search, orient = tkinter.HORIZONTAL, length = 200, mode = 'indeterminate')
search_progress.pack(side = "left", padx = (5, 0), pady = 5)
search_progress.pack_forget()

adv_search_amount = tkinter.Label(adv_search, text = "", font = default_ui_font)
adv_search_amount.pack(side = "left", padx = (5, 0), pady = 5)
adv_search_amount.pack_forget()

adv_search_result = tkinter.Label(adv_search, text = "", font = default_ui_font)
adv_search_result.pack(side = "left", padx = (5, 0), pady = 5)
adv_search_result.pack_forget()


adv_song_entry.bind("<Return>", advanced_search)
adv_artist_entry.bind("<Return>", advanced_search)
adv_album_entry.bind("<Return>", advanced_search)
adv_genre_entry.bind("<Return>", advanced_search)
adv_year_entry.bind("<Return>", advanced_search)
adv_charter_entry.bind("<Return>", advanced_search)

search_type.add(adv_search, text = "Advanced Search")

# Packing search_type:
search_type.pack(side = "left", fill = "x", expand = True)



# Song List:
song_info = tkinter.ttk.Label(browse_frame, text = song_info_format("Name", "Artist", "Album", "Genre"), font = default_font_m)
song_info.pack(padx = (5, 0), anchor = "w", fill = "x")

song_list_scrollbar = tkinter.ttk.Scrollbar(browse_frame)
song_list_scrollbar.pack(side = "right", fill = "y")

song_list_x_scrollbar = tkinter.ttk.Scrollbar(browse_frame, orient = tkinter.HORIZONTAL)
song_list_x_scrollbar.pack(side = "bottom", fill = "x")

global song_list
song_list = tkinter.Listbox(browse_frame, relief = "flat", takefocus = False,
                            activestyle = 'none', selectbackground = "#c9c9c9",
                            selectforeground = "black", bg = "#f5f5f5",
                            bd = 0, highlightthickness = 0, borderwidth = 2,
                            font = default_font_m, selectmode = "single",
                            xscrollcommand = song_list_x_scrollbar.set, yscrollcommand = song_list_scrollbar.set)

song_list.pack(expand = True, anchor = "w", side = "left", fill = "both", padx = 5, pady = 5)

song_list_scrollbar.config(command=song_list.yview)
song_list_x_scrollbar.config(command=song_list.xview)

song_list.bind("<<ListboxSelect>>", update_song_panel)

notebook.add(browse_frame, text = "Browse")

# Settings frame:
settings_frame = tkinter.Frame(notebook, bg = "white")

song_path_prompt = tkinter.Label(settings_frame, text = "Song Path", bg = "white", font = default_ui_font)
song_path_prompt.pack(anchor = "w", padx = 5, pady = 5)

song_path_var = tkinter.StringVar(root, value=song_path)

song_path_box = tkinter.ttk.Entry(settings_frame, width = 100, textvariable = song_path_var, state = "disabled")
song_path_box.pack(anchor = "w", padx = 5, pady = 5)

song_path_button = tkinter.Button(settings_frame, text = "Set song path", font = default_ui_font, takefocus = False, command = set_song_path)
song_path_button.pack(anchor = "w", padx = 5, pady = 5)

notebook.add(settings_frame, text = "Settings")


# Window configuration:
root.after(1, lambda: root.focus_force())

root.title("Charty")

root.state('zoomed')

root.mainloop()