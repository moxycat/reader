import base64
from io import BytesIO
from datetime import datetime
import json
import PySimpleGUI as sg
from PIL import Image, ImageTk
import textwrap
import base64
import time
import os

import mangakatana
import chapter_view, library, settings
from reader import Reader
from util import DEFAULT_COVER, popup_loading
import authenticate
from requests_html import HTMLSession

tabtable = {
    "tab_reading": "lib_tree_cr",
    "tab_completed": "lib_tree_cmpl",
    "tab_onhold": "lib_tree_idle",
    "tab_dropped": "lib_tree_drop",
    "tab_ptr": "lib_tree_ptr"
}
list2tree = {
    "books_cr": "lib_tree_cr",
    "books_cmpl": "lib_tree_cmpl",
    "books_idle": "lib_tree_idle",
    "books_drop": "lib_tree_drop",
    "books_ptr": "lib_tree_ptr"
}

sg.theme("Default1")
sg.set_options(font=("Consolas", 10))

if not os.path.exists("settings.json"):
    sg.popup_error("Settings file missing!")
    exit(1)
settings.read_settings()
settings.verify()

if settings.settings["ui"]["theme"] == "Dark":
    sg.theme("DarkGrey10")

menu = [["&Readers", []], ["&Library", ["&Open library", "&History"]], ["&Settings", ["&Preferences", "&Help"]]]

search_controls = [
    [
        sg.Menu(menu, key="menu")
    ],
    [
        sg.Combo(["Book name", "Author"], default_value="Book name", readonly=True, key="search_method", background_color="white"),
        sg.Input("", key="search_bar", size=(125, 1), focus=True, expand_x=True),
        sg.Button("⌕", key="search", bind_return_key=True),
        sg.Button("x", key="search_cancel")
    ],
    [sg.Text("", key="search_status", size=(125, 1))],
    [sg.HSeparator()],
    [
        sg.vtop(sg.Column(
            [
                [sg.Listbox([], size=(50, 27), bind_return_key=False, enable_events=True, key="book_list")]
            ], element_justification="c", vertical_alignment="c")),
        sg.VSeparator(),
        #sg.Column(preview, scrollable=False, visible=False, key="preview_col"),
        sg.vtop(
            sg.Column(
            [
                [sg.Text(key="preview_title", font="Consolas 14 underline", visible=False)],
                [sg.Image(key="preview_image")],
                [sg.Text("Current list", key="preview_list", visible=False), sg.Combo(["Reading", "Completed", "On-hold", "Dropped", "Plan to read"], "Reading", enable_events=True, visible=False, key="preview_book_list", readonly=True, background_color="white"), sg.Button("Add to list", key="add_to_list", visible=False)],
                [sg.Button("Edit details", key="preview_edit_details", visible=False)]
            ], key="preview_col_0")
        ),
        #sg.VSeparator(),
        sg.vtop(sg.Column(
            [
                [sg.Text(key="preview_author")],
                [sg.Text(key="preview_genres")],
                [sg.Text(key="preview_status")],
                [sg.Text(key="preview_latest")],
                [sg.Text(key="preview_update")],
                #[sg.HSeparator()],
                [sg.Multiline(key="preview_desc", disabled=True, background_color="white", size=(50, 15), visible=False)],
                [
                    sg.Button("Continue reading", key="read_continue", visible=False),
                    sg.Button("View chapters", key="details", visible=False),
                    sg.Button("Latest chapter", key="read_latest", visible=False)
                ]
                #[sg.Listbox([], key="preview_chapters", size=(50, 15), visible=False, horizontal_scroll=True)]
            ], key="preview_col_1"))
    ]
]

layout = [
    [sg.Column(search_controls, visible=True)],
    [sg.StatusBar("No activity", enable_events=True, key="search_statusbar", size=(50, 1))]
]

print("init db")
if not library.init_db():
    if not authenticate.do():
        exit(0)

if not library.verify_schema():
    sg.popup_error("Your library database file is incompatible!")
    exit(1)

print("updating book info")
if settings.settings["general"]["offline"]:
    library.refresh_book_info()
else:
    library.refresh_book_info(settings.settings["storage"]["refresh"])
print("done")

wind = sg.Window("Moxy's manga reader [alpha ver. 1]", layout=layout, element_justification="l", finalize=True)
wind.TKroot.focus_force()

if settings.settings["general"]["offline"]:
    wind["search"].update(disabled=True)
    wind["search_bar"].update(disabled=True)
    wind["search_cancel"].update(disabled=True)
    wind["search_method"].update(disabled=True)

html_session = HTMLSession()
html_session.browser

reader = Reader() # temp reader used for info tx when browsing books
readers = []

wdetails = None
wreadlist = None
wsettings = None
wloading = None
results = []
is_in_library = False
which_list = 0
rows = []
download_start_time = 0
download_end_time = 0
searcher_thread = None
have_searched = False

cats = ["Reading", "Completed", "On-hold", "Dropped", "Plan to read"]
list2cat = {"books_cr": "Reading", "books_cmpl": "Completed", "books_idle": "On-hold", "books_drop": "Dropped", "books_ptr": "Plan to read"}

results = [(library.book_info[k]["info"], library.book_info[k]["last_update"]) for k in library.book_info.keys()]
names = [(textwrap.shorten(library.book_info[k]["info"]["title"], width=50, placeholder="..."), library.book_info[k]["last_update"]) for k in library.book_info.keys()]
names = sorted(names,
    key=lambda x: x[1], reverse=True)
results = sorted(results,
    key=lambda x: x[1], reverse=True)
names = [item[0] for item in names]
results = [item[0] for item in results]
wind["book_list"].update(names)

def set_status(text):
    wind["search_statusbar"].update(text)
    wind.refresh()

def refresh_ui(url: str, event: str):
    if settings.settings["general"]["offline"]:
        wind.perform_long_operation(lambda: library.get_book_info(url), event)
    else:
        #wind.perform_long_operation(lambda: mangakatana.get_manga_info(url), event)
        wind.perform_long_operation(lambda: library.update_info(url), event)

def refresh_library_ui():
    tds = library.make_treedata()
    wreadlist["lib_tree_cr"].update(tds[0])
    wreadlist["lib_tree_cmpl"].update(tds[1])
    wreadlist["lib_tree_idle"].update(tds[2])
    wreadlist["lib_tree_drop"].update(tds[3])
    wreadlist["lib_tree_ptr"].update(tds[4])
    wreadlist.refresh()

while True:
    w, e, v = sg.read_all_windows()
    print(e)
    reader_windows = [r.window for r in readers]
    if w in reader_windows:
        ix = reader_windows.index(w)
        print(ix)
        if e == "reader_loaded_chapter":
            download_end_time = datetime.utcnow().timestamp()
            set_status(
            f"Downloaded chapter! Took {round(download_end_time - download_start_time, 2)} seconds for {len(readers[-1].images)} pages ({round(float(len(readers[-1].images))/(download_end_time - download_start_time), 2)} page/s)")
            menu[0][1][ix] = "{} - {}".format(readers[ix].book_info["title"],
                readers[ix].book_info["chapters"][readers[ix].chapter_index]["name"])
            wind["menu"].update(menu)
            wind["read_continue"].update(disabled=False)
            wind["read_latest"].update(disabled=False)
            wind["details"].update(disabled=False)
            if readers[ix].book_info["url"] == reader.book_info["url"]:
                refresh_ui(reader.book_info["url"], "book_list_got_info")
                #wind.perform_long_operation(lambda: mangakatana.get_manga_info(url), "book_list_got_info")
        
        if e == "reader_cache":
            wind["read_continue"].update(disabled=True)
            wind["read_latest"].update(disabled=True)
            wind["details"].update(disabled=True)
            
        if e == "reader_cached_next":
            wind["read_continue"].update(disabled=False)
            wind["read_latest"].update(disabled=False)
            wind["details"].update(disabled=False)

        if e == "reader_mini":
            readers[ix].window.hide()
        
        if e == sg.WIN_CLOSED:
            wind.un_hide()
            readers[ix].window.close()
            del readers[ix]
            del menu[0][1][ix]
            wind["menu"].update(menu)
        else:
            readers[ix].handle(e)
        
        if e == "reader_go_prev_ch":
            download_start_time = datetime.utcnow().timestamp()
            wind["read_continue"].update(disabled=True)
            wind["read_latest"].update(disabled=True)
            wind["details"].update(disabled=True)
            set_status("Downloading chapter...")

        if e == "reader_go_next_ch":
            download_start_time = datetime.utcnow().timestamp()
            wind["read_continue"].update(disabled=True)
            wind["read_latest"].update(disabled=True)
            wind["details"].update(disabled=True)
            set_status("Downloading chapter...")
            
            print("updating...")
            if readers[ix].updated:
                if readers[ix].chapter_index > library.book_info[readers[ix].book_info["url"]]["ch"]:
                    library.update_userdata(readers[ix].book_info["url"], ch=readers[ix].chapter_index)
                    if readers[ix].book_info["url"] == reader.book_info["url"]:
                        refresh_ui(reader.book_info["url"], "book_list_got_info")
                        #wind.perform_long_operation(lambda: mangakatana.get_manga_info(reader.book_info["url"]), "book_list_got_info")
            print("done")
    
    menu_clean = [a.replace("&", "") for a in menu[0][1]]

    if e in menu_clean:
        ix = menu_clean.index(e)
        print(ix)
        try:
            readers[ix].window.un_hide()
            readers[ix].window.bring_to_front()
        except: continue

    if w == wind and e == sg.WIN_CLOSED:
        wloading = popup_loading("Saving changes...")
        wloading.read(timeout=0)
        wind.perform_long_operation(library.cleanup_and_close, "close_ready")
    
    if e == "close_ready": break

    if e == "search":
        query = v["search_bar"]
        mode = 0 if v["search_method"] == "Book name" else 1 if v["search_method"] == "Author" else 0
        if len(query) < 3:
            wind["search_status"].update("Try searching for 3 or more characters.")
            continue
        wind["search_status"].update("Searching...")
        set_status("Searching...")
        w["search_bar"].update(disabled=True)
        wind.refresh()
        have_searched = True
        mangakatana.stop_search = False
        searcher_thread = wind.perform_long_operation(lambda: mangakatana.new_search(query, mode, html_session, wind), "search_got_results")

    if e == "search_update_status":
        wind["search_status"].update("Found %d results and counting..." % v[e])
        wind.refresh()

    if e == "search_cancel":
        if searcher_thread is not None:
            wind["search_status"].update("Cancelling search...")
            mangakatana.stop_search = True

    if e == "search_got_results":
        w["search_bar"].update(disabled=False)
        results = v[e]
        searcher_thread = None
        #print(results)
        if results is None:
            wind["search_status"].update("Search cancelled.")
            continue
        if results == []:
            wind["search_status"].update("Found nothing.")
            wind["book_list"].update([])
            continue
        l = len(results)
        names = [textwrap.shorten(a["title"], width=50, placeholder="...") for a in results]
        wind["search_status"].update("Found {} result{}.".format(l, "s" if l > 1 else ""))
        set_status("Search complete!")
        wind["book_list"].update(names)
        #wind["book_list"].set_size((None, len(names)))

    if e == "book_list":
        try:
            ix = wind["book_list"].get_indexes()[0]
        except: continue
        url = results[ix]["url"]
        set_status("Fetching book information...")
        
        #wind.perform_long_operation(lambda: mangakatana.get_manga_info(url), "book_list_got_info")
        refresh_ui(url, "book_list_got_info")

    if e == "book_list_got_info":
        set_status("Fetched book information!")
        try:
            reader.set_book_info(v[e])
        except:
            print("bruh")
            continue

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
        wind["preview_update"].update("Updated at:     " + datetime.strftime(reader.book_info["chapters"][-1]["date"], "%b-%d-%Y"))
        wind["preview_desc"].update("\n".join(textwrap.wrap(reader.book_info["description"], width=50)), visible=True)
        wind["preview_list"].update(visible=True)

        is_in_library, rows = library.get_book(reader.book_info["url"])
        if is_in_library:
            wind["add_to_list"].update(visible=False, disabled=False)
            wind["preview_edit_details"].update(visible=True)
            wind["preview_book_list"].update(visible=True, value=list2cat[rows[1]])
            ix = int(rows[9])
            wind["read_continue"].update(
                text="[{}]".format(textwrap.shorten(reader.book_info["chapters"][ix]["name"], width=20, placeholder="...")),
                visible=True)
            wind["read_continue"].set_tooltip(reader.book_info["chapters"][ix]["name"])
            reader.chapter_index = ix
            reader.page_index = 0
        else:
            wind["read_continue"].update(visible=False)
            wind["add_to_list"].update(visible=True)
            wind["preview_book_list"].update(visible=False)
            wind["preview_edit_details"].update(visible=False)
        
        wind["read_latest"].update(visible=True)
        wind["details"].update(visible=True)
        try:
            im = Image.open(BytesIO(base64.b64decode(reader.book_info["cover"])))
        except:
            im = Image.open(BytesIO(base64.b64decode(DEFAULT_COVER)))
        im.thumbnail(size=(320, 320), resample=Image.BICUBIC)
        wind["preview_image"].update(data=ImageTk.PhotoImage(image=im))
        wind["preview_title"].update("\n".join(textwrap.wrap(reader.book_info["title"], width=im.width//8)), visible=True)
        wind["preview_title"].set_tooltip("\n".join(reader.book_info["alt_names"]))

    if e == "preview_book_list":
        dest = cats.index(v["preview_book_list"])
        library.move(reader.book_info["url"], dest=dest)
        if wreadlist is not None:
            refresh_library_ui()
    
    if e == "add_to_list":
        wind["add_to_list"].update(disabled=True)
        library.add(reader.book_info["url"], 0, 0, -1, -1, 0)
        refresh_ui(reader.book_info["url"], "book_list_got_info")
        if wreadlist is not None:
            refresh_library_ui()
        #wind.perform_long_operation(lambda: mangakatana.get_manga_info(reader.book_info["url"]), "book_list_got_info")

    if e == "details":
        wdetails = chapter_view.make_window()
        wdetails.TKroot.title(reader.book_info["title"])
        wdetails["details_chapters"].bind("<Double-Button-1>", "_open_book")
        chapters = [a["name"] for a in reader.book_info["chapters"][::-1]]
        dates = [datetime.strftime(a["date"], "%b-%d-%Y") for a in reader.book_info["chapters"][::-1]]
        longestname = max([len(a) for a in chapters])
        chapter_and_date = ["{}{}{}".format(a[0], " " * (longestname - len(a[0]) + 5), a[1]) for a in zip(chapters, dates)]
        wdetails["details_chapters"].Widget.configure(width=max([len(a) for a in chapter_and_date]))
        wdetails["details_chapters"].update(values=chapter_and_date, visible=True)
        
        if is_in_library:
            if settings.settings["general"]["offline"]:
                wdetails["details_chapters"].set_right_click_menu(["", ["Mark as read", "---", "!Download", "Delete"]])
            else:
                wdetails["details_chapters"].set_right_click_menu(["", ["Mark as read", "---", "Download", "Delete"]])
            downloaded_chapters = library.get_downloaded_chapters()
            l = len(reader.book_info["chapters"])
            ix = l - reader.chapter_index - 1
            wdetails["details_chapters"].Widget.itemconfigure(ix, bg="yellow")
            #if settings.settings["general"]["offline"]:
            
            for i, ch in enumerate(reader.book_info["chapters"][::-1]):
                if ch["url"] in downloaded_chapters:
                    if i == ix:
                        wdetails["details_chapters"].Widget.itemconfigure(i, bg="#D6E865")
                    else: wdetails["details_chapters"].Widget.itemconfigure(i, bg="green")

            pos = 1.0 - ((reader.chapter_index + 1) / len(reader.book_info["chapters"]))
            print(pos)
            wdetails["details_chapters"].set_vscroll_position(pos)
    
    if w == wdetails and e == sg.WIN_CLOSED:
        wdetails.close()
        wdetails = None
    
    if w == wdetails and e == "Mark as read":
        ix = len(reader.book_info["chapters"]) - wdetails["details_chapters"].get_indexes()[0] - 1
        ix1 = wdetails["details_chapters"].get_indexes()[0]
        wdetails["details_chapters"].Widget.itemconfigure(ix1, bg="yellow")
        downloaded_chapters = library.get_downloaded_chapters()
        for i, ch in enumerate(reader.book_info["chapters"][::-1]):
            if ch["url"] in downloaded_chapters:
                if i == ix1:
                    wdetails["details_chapters"].Widget.itemconfigure(i, bg="#D6E865")
                else: wdetails["details_chapters"].Widget.itemconfigure(i, bg="green")
            else:
                wdetails["details_chapters"].Widget.itemconfigure(i, bg="white")
        
        library.update_userdata(reader.book_info["url"], ch=ix)
        refresh_ui(reader.book_info["url"], "book_list_got_info")
        #wind.perform_long_operation(lambda: mangakatana.get_manga_info(reader.book_info["url"]), "book_list_got_info")
    
    if w == wdetails and e == "Download":
        ixs = wdetails["details_chapters"].get_indexes()
        #ixs = [len(reader.book_info["chapters"]) - ix - 1 for ix in ixs_original]
        #chapters = (reader.book_info["chapters"][ix]["url"] for ix in ixs)
        wdetails["details_chapters"].update(disabled=True, set_to_index=[])
        sg.one_line_progress_meter("Downloading...", 0, len(ixs), key="download_progress", keep_on_top=True, orientation="h", no_titlebar=True, no_button=True)
        for i, ix in enumerate(ixs, start=1):
            if not library.set_pages(reader.book_info["chapters"][len(reader.book_info["chapters"]) - ix - 1]["url"], reader.html_session):
                sg.popup("Failed to download [{}]".format(reader.book_info["chapters"][ix]["url"]), title="Download error")
            else:
                wdetails["details_chapters"].Widget.itemconfigure(ix, bg="green")
                if len(reader.book_info["chapters"]) - ix - 1 == reader.chapter_index:
                    wdetails["details_chapters"].Widget.itemconfigure(ix, bg="#D6E865")
            sg.one_line_progress_meter("Downloading...", i, len(ixs), key="download_progress", keep_on_top=True, orientation="h", no_titlebar=True, no_button=True)
        wdetails["details_chapters"].update(disabled=False, set_to_index=[])

    if w == wdetails and e == "Delete":
        ixs = wdetails["details_chapters"].get_indexes()
        for ix in ixs:
            library.delete_pages(reader.book_info["chapters"][len(reader.book_info["chapters"]) - ix - 1]["url"])
            wdetails["details_chapters"].Widget.itemconfigure(ix, bg="white")
        wdetails["details_chapters"].Widget.itemconfigure(len(reader.book_info["chapters"]) - reader.chapter_index - 1, bg="yellow")
        continue

    if e in ["read_latest", "read_continue", "details_chapters_open_book"]:
        if e == "read_continue": ix = reader.chapter_index
        elif e == "read_latest": ix = len(reader.book_info["chapters"]) - 1
        elif e == "details_chapters_open_book":
            ix = wdetails["details_chapters"].get_indexes()[0]
            ix = len(reader.book_info["chapters"]) - ix - 1

        if reader.book_info["chapters"][ix]["url"] not in library.get_downloaded_chapters() and settings.settings["general"]["offline"]:
            continue

        if wdetails is not None:
            wdetails.close()
            wdetails = None

        readers.append(Reader(reader.book_info))

        set_status("Downloading chapter...")
        download_start_time = datetime.utcnow().timestamp()
        wind["read_continue"].update(disabled=True)
        wind["read_latest"].update(disabled=True)
        wind["details"].update(disabled=True)
        #if reader.book_info["chapters"]["url"] in library.get_downloaded_chapters() or settings.settings["general"]["offline"]:
        wind.perform_long_operation(lambda: readers[-1].set_chapter(ix), "open_reader")

    if e == "open_reader":
        wind["read_continue"].update(disabled=False)
        wind["read_latest"].update(disabled=False)
        wind["details"].update(disabled=False)
        if v[e] == False:
            sg.popup_error("Failed to download chapter.")
            wind["search_statusbar"].update("Failed to download chapter.")
            continue
        menu[0][1].append("{} - {}".format(readers[-1].book_info["title"],
            readers[-1].book_info["chapters"][readers[-1].chapter_index]["name"]))
        wind["menu"].update(menu)

        download_end_time = datetime.utcnow().timestamp()
        if wloading is not None: wloading.close()
        set_status(
            f"Downloaded chapter! Took {round(download_end_time - download_start_time, 2)} seconds for {len(readers[-1].images)} pages ({round(float(len(readers[-1].images))/(download_end_time - download_start_time), 2)} page/s)")
        is_in_library, rows = library.get_book(readers[-1].book_info["url"])
        if is_in_library: readers[-1].updated = True
        if is_in_library and reader.chapter_index < readers[-1].chapter_index:
            library.update_userdata(readers[-1].book_info["url"], ch=readers[-1].chapter_index)
            if wreadlist is not None:
                print("updating entry...")
                refresh_library_ui()
        elif is_in_library:
            library.update_userdata(readers[-1].book_info["url"])
        elif not is_in_library:
            readers[-1].updated = library.start_reading()
            if readers[-1].updated:
                library.add(readers[-1].book_info["url"], readers[-1].chapter_index, 0, int(time.time()), -1, 0, where=library.BookList.READING)
                refresh_library_ui()
        readers[-1].make_window()
        readers[-1].set_page(0)
        if reader.book_info["url"] == readers[-1].book_info["url"]:
            refresh_ui(reader.book_info["url"], "book_list_got_info")
            #wind.perform_long_operation(lambda: mangakatana.get_manga_info(readers[-1].book_info["url"]), "book_list_got_info")
    
    if e == "preview_edit_details":
        ret = library.edit_chapter_progress(reader.book_info["url"])
        if ret:
            refresh_ui(reader.book_info["url"], "book_list_got_info")
            #wind.perform_long_operation(lambda: mangakatana.get_manga_info(url), "book_list_got_info")

    if e == "Save screenshot":
        filename = sg.popup_get_file(message="Please choose where to save the file", title="Save screenshot",
        default_extension="png", file_types=(("Image", "*.png png"),), save_as=True,
        default_path=f"{readers[ix].page_index + 1}.png")
        if filename is None: continue
        im = Image.open(BytesIO(readers[ix].images[readers[ix].page_index]))
        im.save(filename, "png")
        im.close()
    
    if e == "Open library":
        if wreadlist is not None:
            wreadlist.un_hide()
            wreadlist.bring_to_front()
        else:
            try:
                wloading = popup_loading()
                wloading.read(timeout=0)
                wind.perform_long_operation(library.make_window, "lib_window_made")
            except:
                wloading.close()
                sg.popup("Failed to load library.", title="Error", keep_on_top=True)

    if e == "lib_window_made":
        if wloading is not None: wloading.close()
        layout = v[e]
        wreadlist = sg.Window("Library", layout, finalize=True, element_justification="l")

        wreadlist["lib_tree_cr"].bind("<Double-Button-1>", "_open_book")
        wreadlist["lib_tree_cmpl"].bind("<Double-Button-1>", "_open_book")
        wreadlist["lib_tree_idle"].bind("<Double-Button-1>", "_open_book")
        wreadlist["lib_tree_drop"].bind("<Double-Button-1>", "_open_book")
        wreadlist["lib_tree_ptr"].bind("<Double-Button-1>", "_open_book")
        library.get_original(wreadlist["lib_tree_cr"])
    
    if w == wreadlist and e == "Check for updates":
        library.refresh_book_info(full=True)
        tds = library.make_treedata()
        wreadlist["lib_tree_cr"].update(tds[0])
        wreadlist["lib_tree_cmpl"].update(tds[1])
        wreadlist["lib_tree_idle"].update(tds[2])
        wreadlist["lib_tree_drop"].update(tds[3])
        wreadlist["lib_tree_ptr"].update(tds[4])
        wreadlist.refresh()
    
    if w == wreadlist and e in ["Title::title", "Score::score", "Chapters::chapters", "Volumes::volumes", "Latest upload::upload", "Last update::update"]:
        orders = {
            "Title::title": library.OrderBy.TITLE,
            "Score::score": library.OrderBy.SCORE,
            "Chapters::chapters": library.OrderBy.CHAPTERS,
            "Volumes::volumes": library.OrderBy.VOLUMES,
            "Latest upload::upload": library.OrderBy.UPLOAD,
            "Last update::update": library.OrderBy.UPDATE
        }
        tds = library.make_treedata(orders[e])
        wreadlist["lib_tree_cr"].update(tds[0])
        wreadlist["lib_tree_cmpl"].update(tds[1])
        wreadlist["lib_tree_idle"].update(tds[2])
        wreadlist["lib_tree_drop"].update(tds[3])
        wreadlist["lib_tree_ptr"].update(tds[4])
        wreadlist.refresh()
        pass
    
    if e == "lib_search":
        q = v["lib_search_query"]
        tab = v["tab_group"]

        library.get_original(wreadlist[tabtable[tab]])
        library.clear_search(wreadlist[tabtable[tab]])
        if q == "": continue
        library.search(q, wreadlist[tabtable[tab]])
    
    if e == "tab_group":
        q = v["lib_search_query"]
        tab = v["tab_group"]

        library.get_original(wreadlist[tabtable[tab]])
        library.clear_search(wreadlist[tabtable[tab]])
        if q == "": continue
        library.search(q, wreadlist[tabtable[tab]])

    if w == wreadlist and e == "Edit":
        try:
            tab = v["tab_group"]
            url = v[tabtable[tab]][0]
            ret = library.edit_chapter_progress(url)
            if ret == False: continue
            wreadlist[tabtable[tab]].update(key=url, value=[
                textwrap.shorten(library.book_info[url]["info"]["title"], width=50, placeholder="..."),
                library.book_info[url]["score"],
                "{}/{}".format(
                    str(int(library.book_info[url]["ch"]) + 1).zfill(2),
                    str(len(library.book_info[url]["info"]["chapters"])).zfill(2) if library.book_info[url]["info"]["status"] == "Completed" else "[" + str(len(library.book_info[url]["info"]["chapters"])).zfill(2) + "]"
                ),
                library.book_info[url]["vol"],
                str((datetime.now() - library.book_info[url]["info"]["chapters"][-1]["date"]).days) + " days ago"
            ])

            wreadlist.refresh()
            if url == reader.book_info["url"]:
                refresh_ui(url, "book_list_got_info")
                #wind.perform_long_operation(lambda: mangakatana.get_manga_info(url), "book_list_got_info")
            library.get_original(wreadlist[tabtable[tab]])
            q = v["lib_search_query"]
            library.clear_search(wreadlist[tabtable[tab]])
            if q == "": continue
            library.search(q, wreadlist[tabtable[tab]])
            print("=" * 50)
        except Exception as e:
            print(e)
            continue
    
    if w == wreadlist and e == "Remove":
        tab = v["tab_group"]
        try:
            url = v[tabtable[tab]][0]
        except: continue
        
        library.delete(url)
        wreadlist[tabtable[tab]].delete_selected()
        wreadlist.refresh()
        tds = library.make_treedata()
        #library.update_info(url)
        wreadlist["lib_tree_cr"].update(tds[0])
        wreadlist["lib_tree_cmpl"].update(tds[1])
        wreadlist["lib_tree_idle"].update(tds[2])
        wreadlist["lib_tree_drop"].update(tds[3])
        wreadlist["lib_tree_ptr"].update(tds[4])
        print(have_searched)
        if not have_searched:
            ix = [a["url"] for a in results].index(url)
            print(ix)
            del results[ix]
            del names[ix]
            wind["book_list"].update(names)
            wind.refresh()
        #wind["book_list"].
        wreadlist.refresh()
        #print(url, reader.book_info["url"])
        if url == reader.book_info["url"]:
            refresh_ui(url, "book_list_got_info")
            #wind.perform_long_operation(lambda: mangakatana.get_manga_info(url), "book_list_got_info")
    
    if w == wreadlist and e == "More info":
        tab = v["tab_group"]
        try:
            url = v[tabtable[tab]][0]
        except: continue
        set_status("Fetching book information...")
        refresh_ui(url, "book_list_got_info")
        #wind.perform_long_operation(lambda: mangakatana.get_manga_info(v[tabtable[tab]][0]), "book_list_got_info")
    
    if w == wreadlist and e == "View chapters":
        tab = v["tab_group"]
        try:
            url = v[tabtable[tab]][0]
        except: continue
        # finish this part

    # move
    if w == wreadlist and e in cats:
        tab = v["tab_group"]
        print(tab)
        try:
            url = v[tabtable[tab]][0]
            library.move(url, dest=cats.index(e))
            print(url, reader.book_info["url"])
            if url == reader.book_info["url"]:
                refresh_ui(url, "book_list_got_info")
                #wind.perform_long_operation(lambda: mangakatana.get_manga_info(url), "book_list_got_info")
            wloading = popup_loading()
            wloading.read(timeout=0)
            wind.perform_long_operation(lambda: library.make_treedata(), "library_moved")
        except: continue
    
    if e == "library_moved":
        wloading.close()
        tds = v[e]
        wreadlist["lib_tree_cr"].update(tds[0])
        wreadlist["lib_tree_cmpl"].update(tds[1])
        wreadlist["lib_tree_idle"].update(tds[2])
        wreadlist["lib_tree_drop"].update(tds[3])
        wreadlist["lib_tree_ptr"].update(tds[4])
        wreadlist.refresh()
        
    if w == wreadlist and e == "Refresh":
        tds = library.make_treedata()
        wreadlist["lib_tree_cr"].update(tds[0])
        wreadlist["lib_tree_cmpl"].update(tds[1])
        wreadlist["lib_tree_idle"].update(tds[2])
        wreadlist["lib_tree_drop"].update(tds[3])
        wreadlist["lib_tree_ptr"].update(tds[4])
        wreadlist.refresh()
    
    if e in [v + "_open_book" for _, v in tabtable.items()]:
        tab = v["tab_group"]
        print(tab)
        try:
            url = v[tabtable[tab]][0]
        except: continue
        print(url)
        refresh_ui(url, "lib_open_book")
        #wind.perform_long_operation(lambda: mangakatana.get_manga_info(url), "lib_open_book")
    
    if e == "lib_open_book":
        try:
            reader.set_book_info(v[e])
        except: continue
        is_in_library, rows = library.get_book(reader.book_info["url"])
        if is_in_library:
            ix = int(rows[9])
            reader.chapter_index = ix
            reader.page_index = 0
            wind.write_event_value("read_continue", "")
    
    if w == wreadlist and e == sg.WIN_CLOSED:
        wreadlist.close()
        wreadlist = None
    
    if e == "Preferences":
        if wsettings is not None:
            wsettings.un_hide()
            wsettings.bring_to_front()
        else:
            wsettings = settings.make_window()
    
    if e == "settings_save":
        d = {
            "general": {
                "offline": v["settings_offline"]
            },
            "ui": {
                "theme": v["settings_ui_theme"]
            },
            "reader": {
                "w": v["settings_reader_width"],
                "h": v["settings_reader_height"],
                "filter": v["settings_bluefilter_perc"]
            },
            "server": {
                "source": v["settings_server_source"]
            },
            "storage": {
                "path": v["settings_storage_db_path"],
                "refresh": v["settings_storage_refresh"]
            }
        }
        with open("settings.json", "w") as f:
            f.write(json.dumps(d))
        settings.read_settings() # refresh
        wsettings.close()
        wsettings = None
    
    if e == "settings_cancel":
        wsettings.close()
        wsettings = None
    
    if w == wsettings and e == sg.WIN_CLOSED:
        wsettings.close()
        wsettings = None
        
    if w == wind and e == "Help":
        continue

wind.close()