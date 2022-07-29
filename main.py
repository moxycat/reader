from io import BytesIO
from datetime import datetime
import json
import PySimpleGUI as sg
from PIL import Image, ImageTk
import requests
import textwrap

import mangakatana
import reader, chapter_view, library, settings

from v2.reader import Reader # experimental

def myround(x, prec=2, base=.05):
  return round(base * round(float(x)/base),prec)

sg.theme("Default1")
sg.set_options(font=("Consolas", 10))

def popup_loading():
    return sg.Window("", layout=[
        [
            sg.Text("Loading...")
        ]
    ], modal=True, no_titlebar=True, finalize=True)

search_controls = [
    [
        sg.Menu([["File", ["Open reader"]], ["&Library", ["Reading list", "Favourites"]], ["&Settings", ["&Preferences", "&Help"]]], key="menu")
    ],
    [
        sg.Combo(["Book name", "Author"], default_value="Book name", readonly=True, key="search_method", background_color="white"),
        sg.Input("", key="search_bar", size=(90, 1), focus=True),
        sg.Button("⌕", key="search", bind_return_key=True)
    ],
    [sg.Text("", key="search_status", size=(90, 1))],
    [sg.HSeparator()],
    [
        sg.Column(
            [
                [sg.Listbox([], size=(50, 20), bind_return_key=False, enable_events=True, key="book_list")]
            ]
        ),
        sg.VSeparator(),
        #sg.Column(preview, scrollable=False, visible=False, key="preview_col"),
        sg.Column(
            [
                [sg.Text(key="preview_title", font="Consolas 14 underline")],
                [sg.Image(key="preview_image")]
            ]
        ),
        #sg.VSeparator(),
        sg.Column(
            [
                [sg.Text(key="preview_author")],
                [sg.Text(key="preview_genres")],
                [sg.Text(key="preview_status")],
                [sg.Text(key="preview_latest")],
                [sg.Text(key="preview_update")],
                [sg.Multiline(key="preview_desc", disabled=True, background_color="white", size=(50, 15), visible=False)],
                [
                    sg.Button("Continue reading", key="read_continue", visible=False),
                    sg.Button("View chapters", key="details", visible=False),
                    sg.Button("Latest chapter", key="read_latest", visible=False),
                ]
                #[sg.Listbox([], key="preview_chapters", size=(50, 15), visible=False, horizontal_scroll=True)]
            ]
        )
    ]
]

layout = [
    [sg.Column(search_controls, visible=True)],
    [sg.StatusBar("No activity", enable_events=True, key="search_statusbar", size=(50, 1))]
]

library.init_db()

wind = sg.Window("Moxy's manga reader [alpha ver. 1]", layout=layout, element_justification="l", finalize=True)

reader = Reader()

wdetails = None
wreadlist = None
wsettings = None
wloading = None
results = []
is_in_library = False
download_start_time = 0
download_end_time = 0

def set_status(text):
    global wind
    wind["search_statusbar"].update(text)
    wind.refresh()

while True:
    w, e, v = sg.read_all_windows()
    print(e)
    if w == reader.window:
        if e == sg.WIN_CLOSED:
            wind.un_hide()
            reader.window.close()
        else: reader.handle(e)
    if w == wind and e == sg.WIN_CLOSED: break
    
    if e == "search":
        query = v["search_bar"]
        mode = 0 if v["search_method"] == "Book name" else 1 if v["search_method"] == "Author" else 0
        if len(query) < 3:
            wind["search_status"].update("Try searching for 3 or more characters.")
            continue
        wind["search_status"].update("Searching...")
        set_status("Searching...")
        wind.refresh()
        wind.perform_long_operation(lambda: mangakatana.search(query, mode), "search_got_results")
        
    if e == "search_got_results":
        results = v[e]
        if results is None:
            wind["search_status"].update("Found nothing.")
            continue
        names = [textwrap.shorten(a["title"], width=50, placeholder="...") for a in results]
        l = len(results)
        wind["search_status"].update("Found {} result{}.".format(l, "s" if l > 1 else ""))
        set_status("Search complete!")
        wind["book_list"].update(names)

    if e == "book_list":
        try:
            ix = wind["book_list"].get_indexes()[0]
        except: continue
        url = results[ix]["url"]
        set_status("Fetching book information...")
        
        wind.perform_long_operation(lambda: mangakatana.get_manga_info(url), "book_list_got_info")

    if e == "book_list_got_info":
        set_status("Fetched book information!")
        info = v[e]
        reader.set_book_info(info)
        im = Image.open(requests.get(reader.book_info["cover_url"], stream=True).raw)
        im.thumbnail(size=(320, 320), resample=Image.BICUBIC)
        wind["preview_image"].update(data=ImageTk.PhotoImage(image=im))
        wind["preview_title"].update("\n".join(textwrap.wrap(reader.book_info["title"], width=im.width//8)))
        wind["preview_title"].set_tooltip("\n".join(reader.book_info["alt_names"]))
        #wind["preview_alt_names"].update("Alt names(s): " + ";\n                     ".join(reader.book_info["alt_names"]))
        wind["preview_author"].update("Author:         " + reader.book_info["author"])
        genres = ""
        for i, g in enumerate(reader.book_info["genres"]):
            if i == len(reader.book_info["genres"]) - 1:
                genres += g
                break
            genres += g + "," + ("\n                " if i % 3 == 2 else " ")
        wind["preview_genres"].update("Genres:         " + genres)
        wind["preview_status"].update("Status:         " + reader.book_info["status"])
        wind["preview_latest"].update("Latest chapter: " + reader.book_info["chapters"][-1]["name"])
        wind["preview_update"].update("Updated at:     " + reader.book_info["chapters"][-1]["date"])
        wind["preview_desc"].update("\n".join(textwrap.wrap(reader.book_info["description"], width=50)), visible=True)
        
        is_in_library, rows = library.is_in_lib(reader.book_info["url"])
        if is_in_library:
            ix = int(rows[1]) + (1 if int(rows[1]) < len(reader.book_info["chapters"]) else 0)
            wind["read_continue"].update(
                text="[{}]".format(textwrap.shorten(reader.book_info["chapters"][ix]["name"], width=30, placeholder="...")),
                visible=True)
            wind["read_continue"].set_tooltip(reader.book_info["chapters"][ix]["name"])
            reader.chapter_index = ix # kinda huh ngl maybe figure out a better solution
        else: wind["read_continue"].update(visible=False)
        wind["read_latest"].update(visible=True)
        wind["details"].update(visible=True)
        #wind.refresh() don't think this is needed? the window should refresh on each read call

    if e == "details":
        wdetails = chapter_view.make_window()
        wdetails.TKroot.title(reader.book_info["title"])
        chapters = [a["name"] for a in reader.book_info["chapters"][::-1]]
        dates = [a["date"] for a in reader.book_info["chapters"][::-1]]
        longestname = max([len(a) for a in chapters])
        chapter_and_date = ["{}{}{}".format(a[0], " " * (longestname - len(a[0]) + 5), a[1]) for a in zip(chapters, dates)]
        wdetails["details_chapters"].Widget.configure(width = max([len(a) for a in chapter_and_date]))
        wdetails["details_chapters"].update(values=chapter_and_date, visible=True)
    
    if w == wdetails and e == sg.WIN_CLOSED:
        wdetails.close()
        wdetails = None
    
    # loader + downloader
    if e == "details_chapters":
        ix = wdetails["details_chapters"].get_indexes()[0]
        ix = len(reader.book_info["chapters"]) - ix - 1
        
        set_status("Downloading chapter...")
        download_start_time = datetime.utcnow().timestamp()
        wloading = popup_loading()
        wloading.read(timeout=0)
        wind.perform_long_operation(lambda: reader.set_chapter(ix), "open_reader")
        wdetails.close()

    if e == "read_latest":
        ix = len(reader.book_info["chapters"]) - 1
        set_status("Downloading chapter...")
        download_start_time = datetime.utcnow().timestamp()
        wloading = popup_loading()
        wloading.read(timeout=0)
        wind.perform_long_operation(lambda: reader.set_chapter(ix), "open_reader")
    
    if e == "read_continue":
        set_status("Downloading chapter...")
        download_start_time = datetime.utcnow().timestamp()
        wloading = popup_loading()
        wloading.read(timeout=0)
        wind.perform_long_operation(lambda: reader.set_chapter(), "open_reader")
    
    if e == "open_reader":
        download_end_time = datetime.utcnow().timestamp()
        if wloading is not None: wloading.close()
        set_status(
            f"Downloaded chapter! Took {round(download_end_time - download_start_time, 2)} seconds for {len(reader.images)} pages ({round(float(len(reader.images))/(download_end_time - download_start_time), 2)} page/s)")
        reader.make_window()
        reader.set_page(0)
        wind.hide()

    if e == "Save screenshot":
        filename = sg.popup_get_file(message="Please choose where to save the file", title="Save screenshot",
        default_extension="png", file_types=(("Image", "*.png png"),), save_as=True,
        default_path=f"{reader.page_index + 1}.png")
        im = Image.open(BytesIO(reader.images[reader.page_index]))
        im.save(filename, "png")
        im.close()
    
    if e == "Reading list":
        if wreadlist is not None:
            wreadlist.un_hide()
            wreadlist.bring_to_front()
        else:
            wind.perform_long_operation(library.make_window_layout, "lib_window_made")

    if e == "lib_window_made":
        lo = v[e]
        wreadlist = sg.Window("Reading list", lo, finalize=True)
        wreadlist["lib_tree"].bind("<Double-Button-1>", "lib_tree_open_book")
        #wreadlist["lib_tree"].bind("<Button-3>", lambda event, element=wreadlist["lib_tree"]: library.right_click_menu_callback(event, element))
    
    if w == wreadlist and e == "Edit chapter":
        url = v["lib_tree"][0]
        library.edit_chapter_progress(url, len(library.book_info[url]["info"]["chapters"]))
    
    if w == wreadlist and e == "Refresh":
        wreadlist.close()
        wind.perform_long_operation(library.make_window_layout, "lib_window_made")

    if e == "lib_tree":
        #print(library.rows[v[e][0]])
        continue

    if e == "lib_tree_open_book":
        print(v["lib_tree"])
    
    if w == wreadlist and e == sg.WIN_CLOSED:
        wreadlist.close()
        wreadlist = None
    
    if e == "Preferences":
        wsettings = settings.make_window()
    
    if e == "settings_save":
        d = {
            "ui": {
                "theme": v["settings_ui_theme"]
            },
            "reader": {
                "w": v["settings_reader_width"],
                "h": v["settings_reader_height"]
            },
            "server": {
                "source": v["settings_server_source"]
            }
        }
        with open("settings.json", "w") as f:
            f.write(json.dumps(d))
        wsettings.close()
    
    if e == "settings_cancel":
        wsettings.close()
    
    if w == wsettings and e == sg.WIN_CLOSED:
        wsettings.write_event_value("settings_cancel", "")
    
    if e == "Open reader":
        #if len(images) > 0: open_reader()
        continue
    
        
wind.close()