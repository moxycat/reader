import base64
from io import BytesIO
from datetime import datetime
import json
import PySimpleGUI as sg
from PIL import Image, ImageTk
import requests
import textwrap
import base64

import mangakatana
import chapter_view, library, settings
from reader import Reader
from util import DEFAULT_COVER

tabtable = {
    "tab_reading": "lib_tree_cr",
    "tab_completed": "lib_tree_cmpl",
    "tab_onhold": "lib_tree_idle",
    "tab_dropped": "lib_tree_drop",
    "tab_ptr": "lib_tree_ptr"
}

settings.read_settings()

if settings.settings["ui"]["theme"] == "Dark":
    sg.theme("DarkGrey10")
elif settings.settings["ui"]["theme"] == "Light":
    sg.theme("Default1")

sg.set_options(font=("Consolas", 10))

def popup_loading():
    return sg.Window("", layout=[
        [
            sg.Text("Loading...", font=("Consolas", 14))
        ]
    ], modal=True, no_titlebar=True, finalize=True)

menu = [["&Readers", []], ["&Library", ["&Open library", "&History"]], ["&Settings", ["&Preferences", "&Help"]]]

search_controls = [
    [
        sg.Menu(menu, key="menu")
    ],
    [
        sg.Combo(["Book name", "Author"], default_value="Book name", readonly=True, key="search_method", background_color="white"),
        sg.Input("", key="search_bar", size=(90, 1), focus=True, expand_x=True),
        sg.Button("⌕", key="search", bind_return_key=True),
        sg.Button("x", key="search_cancel")
    ],
    [sg.Text("", key="search_status", size=(90, 1))],
    [sg.HSeparator()],
    [
        sg.vtop(sg.Column(
            [
                [sg.Listbox([], size=(50, 20), bind_return_key=False, enable_events=True, key="book_list")]
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
library.init_db()
print("updating book info")
library.update_book_info()
print("done")

wind = sg.Window("Moxy's manga reader [alpha ver. 1]", layout=layout, element_justification="l", finalize=True)
#wind.bind("<FocusIn>", "main_focusin")
reader = Reader() # temp reader used for info tx when browsing books
readers = []

book_list_ix = -1

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


cats = ["Reading", "Completed", "On-hold", "Dropped", "Plan to read"]

results = [(library.book_info[k]["info"], library.book_info[k]["last_update"]) for k in library.book_info.keys()]
names = [(textwrap.shorten(library.book_info[k]["info"]["title"], width=50, placeholder="..."), library.book_info[k]["last_update"]) for k in library.book_info.keys()]
names = sorted(names,
    key=lambda x: datetime.strptime(x[1], "%b-%d-%Y %H:%M:%S") if x[1] != "unknown" else datetime.fromtimestamp(0), reverse=True)
results = sorted(results,
    key=lambda x: datetime.strptime(x[1], "%b-%d-%Y %H:%M:%S") if x[1] != "unknown" else datetime.fromtimestamp(0), reverse=True)
names = [item[0] for item in names]
results = [item[0] for item in results]
wind["book_list"].update(names)

def set_status(text):
    wind["search_statusbar"].update(text)
    wind.refresh()

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
                wind.perform_long_operation(lambda: mangakatana.get_manga_info(url), "book_list_got_info")
        
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
                library.update(readers[ix].book_info["url"], ch=readers[ix].chapter_index)
                if readers[ix].book_info["url"] == reader.book_info["url"]:
                    wind.perform_long_operation(lambda: mangakatana.get_manga_info(reader.book_info["url"]), "book_list_got_info")
            print("done")
    
    menu_clean = [a.replace("&", "") for a in menu[0][1]]

    if e in menu_clean:
        ix = menu_clean.index(e)
        print(ix)
        try:
            readers[ix].window.un_hide()
            readers[ix].window.bring_to_front()
        except: continue

    if w == wind and e == sg.WIN_CLOSED: break
    
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
        mangakatana.stop_search = False
        searcher_thread = wind.perform_long_operation(lambda: mangakatana.search(query, mode), "search_got_results")

    if e == "search_cancel":
        if searcher_thread is not None:
            wind["search_status"].update("Cancelling search...")
            mangakatana.stop_search = True

    if e == "search_got_results":
        w["search_bar"].update(disabled=False)
        results = v[e]
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
        
        wind.perform_long_operation(lambda: mangakatana.get_manga_info(url), "book_list_got_info")

    if e == "book_list_got_info":
        set_status("Fetched book information!")
        try:
            reader.set_book_info(v[e])
        except: continue

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

        is_in_library, rows, which_list = library.is_in_lib(reader.book_info["url"])
        if is_in_library:
            wind["add_to_list"].update(visible=False)
            wind["preview_edit_details"].update(visible=True)
            wind["preview_book_list"].update(visible=True, value=cats[which_list])
            ix = int(rows[1])
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
            cover = requests.get(reader.book_info["cover_url"], stream=True)
            if cover.status_code != 200: raise Exception
            im = Image.open(cover.raw)
        except:
            im = Image.open(BytesIO(base64.b64decode(DEFAULT_COVER)))
        im.thumbnail(size=(320, 320), resample=Image.BICUBIC)
        wind["preview_image"].update(data=ImageTk.PhotoImage(image=im))
        wind["preview_title"].update("\n".join(textwrap.wrap(reader.book_info["title"], width=im.width//8)))
        wind["preview_title"].set_tooltip("\n".join(reader.book_info["alt_names"]))

    if e == "preview_book_list":
        dest = cats.index(v["preview_book_list"])
        src = which_list
        library.move(reader.book_info["url"], src=src, dest=dest)
        which_list = dest
    
    if e == "add_to_list":
        library.add(reader.book_info["url"], 0, 0, "unknown", "unknown", "0")
        wind["add_to_list"].update(visible=False)
        wind["preview_book_list"].update(visible=True, value="Plan to read")
        which_list = library.BookStatus.PLAN_TO_READ

    if e == "details":
        wdetails = chapter_view.make_window()
        wdetails.TKroot.title(reader.book_info["title"])
        wdetails["details_chapters"].bind("<Double-Button-1>", "_open_book")
        chapters = [a["name"] for a in reader.book_info["chapters"][::-1]]
        dates = [datetime.strftime(a["date"], "%b-%d-%Y") for a in reader.book_info["chapters"][::-1]]
        longestname = max([len(a) for a in chapters])
        chapter_and_date = ["{}{}{}".format(a[0], " " * (longestname - len(a[0]) + 5), a[1]) for a in zip(chapters, dates)]
        wdetails["details_chapters"].Widget.configure(width = max([len(a) for a in chapter_and_date]))
        wdetails["details_chapters"].update(values=chapter_and_date, visible=True)
        if is_in_library:
            l = len(reader.book_info["chapters"])
            ix = l - reader.chapter_index - 1
            wdetails["details_chapters"].Widget.itemconfigure(ix, bg="yellow")
            pos = 1.0 - ((reader.chapter_index + 1) / len(reader.book_info["chapters"]))
            print(pos)
            wdetails["details_chapters"].set_vscroll_position(pos)
    
    if w == wdetails and e == sg.WIN_CLOSED:
        wdetails.close()
        wdetails = None
    
    if e == "details_chapters_open_book":
        ix = wdetails["details_chapters"].get_indexes()[0]
        ix = len(reader.book_info["chapters"]) - ix - 1

        readers.append(Reader(reader.book_info))
        """
        menu[0][1].append("{} - {}".format(readers[-1].book_info["title"],
            readers[-1].book_info["chapters"][ix]["name"]))
        wind["menu"].update(menu)
        """

        set_status("Downloading chapter...")
        download_start_time = datetime.utcnow().timestamp()
        #wloading = popup_loading()
        #wloading.read(timeout=0)
        wind["read_continue"].update(disabled=True)
        wind["read_latest"].update(disabled=True)
        wind["details"].update(disabled=True)
        #print(readers[-1].book_info["chapters"][readers[-1].chapter_index]["url"])
        wind.perform_long_operation(lambda: readers[-1].set_chapter(ix), "open_reader")
        wdetails.close()

    if e == "read_latest":
        ix = len(reader.book_info["chapters"]) - 1

        readers.append(Reader(reader.book_info))
        """
        menu[0][1].append("{} - {}".format(readers[-1].book_info["title"],
            readers[-1].book_info["chapters"][ix]["name"]))
        wind["menu"].update(menu)
        """

        set_status("Downloading chapter...")
        download_start_time = datetime.utcnow().timestamp()
        #wloading = popup_loading()
        #wloading.read(timeout=0)
        wind["read_continue"].update(disabled=True)
        wind["read_latest"].update(disabled=True)
        wind["details"].update(disabled=True)
        wind.perform_long_operation(lambda: readers[-1].set_chapter(ix), "open_reader")
    
    if e == "read_continue":
        
        readers.append(Reader(reader.book_info))
        """
        menu[0][1].append("{} - {}".format(readers[-1].book_info["title"],
            readers[-1].book_info["chapters"][reader.chapter_index]["name"]))
        wind["menu"].update(menu)
        """

        set_status("Downloading chapter...")
        download_start_time = datetime.utcnow().timestamp()
        #wloading = popup_loading()
        #wloading.read(timeout=0)
        wind["read_continue"].update(disabled=True)
        wind["read_latest"].update(disabled=True)
        wind["details"].update(disabled=True)
        wind.perform_long_operation(lambda: readers[-1].set_chapter(reader.chapter_index), "open_reader")
    
    if e == "open_reader":
        wind["read_continue"].update(disabled=False)
        wind["read_latest"].update(disabled=False)
        wind["details"].update(disabled=False)
        if v[e] == False:
            #wloading.close()
            sg.popup_error("Failed to download chapter.")
            continue
        menu[0][1].append("{} - {}".format(readers[-1].book_info["title"],
            readers[-1].book_info["chapters"][readers[-1].chapter_index]["name"]))
        wind["menu"].update(menu)

        download_end_time = datetime.utcnow().timestamp()
        if wloading is not None: wloading.close()
        set_status(
            f"Downloaded chapter! Took {round(download_end_time - download_start_time, 2)} seconds for {len(readers[-1].images)} pages ({round(float(len(readers[-1].images))/(download_end_time - download_start_time), 2)} page/s)")
        if is_in_library: readers[-1].updated = True
        if is_in_library and reader.chapter_index < readers[-1].chapter_index:
            library.update(readers[-1].book_info["url"], ch=readers[-1].chapter_index)
            if wreadlist is not None:
                print("updating entry...")
                url = readers[-1].book_info["url"]
                #print("DASDJASJDKASDJASKDJKAS: ", [x[1] for x in tabtable.items()][which_list])
                wreadlist[[x[1] for x in tabtable.items()][which_list]].update(key=url, value=[
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
        elif is_in_library:
            library.update(readers[-1].book_info["url"])
        elif not is_in_library:
            readers[-1].updated = library.start_reading()
            if readers[-1].updated:
                library.add(readers[-1].book_info["url"], readers[-1].chapter_index, 0, datetime.today().strftime("%Y-%m-%d"), "unknown", "0", where=library.BookStatus.READING)
                # update lib interface if open
        readers[-1].make_window()
        readers[-1].set_page(0)
    
    if e == "preview_edit_details":
        ret = library.edit_chapter_progress(reader.book_info["url"])
        if ret:
            wind.perform_long_operation(lambda: mangakatana.get_manga_info(url), "book_list_got_info")

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
                wind.perform_long_operation(lambda: mangakatana.get_manga_info(url), "book_list_got_info")
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
        print(url, reader.book_info["url"])
        if url == reader.book_info["url"]:
            wind.perform_long_operation(lambda: mangakatana.get_manga_info(url), "book_list_got_info")
    
    if w == wreadlist and e == "Show in search":
        tab = v["tab_group"]
        try:
            url = v[tabtable[tab]][0]
        except: continue
        set_status("Fetching book information...")
        
        wind.perform_long_operation(lambda: mangakatana.get_manga_info(v[tabtable[tab]][0]), "book_list_got_info")
    
    if w == wreadlist and e == "View chapters":
        tab = v["tab_group"]
        url = v[tabtable[tab]][0]
        # finish this part

    # move
    if w == wreadlist and e in cats:
        tab = v["tab_group"]
        print(tab)
        try:
            url = v[tabtable[tab]][0]
            library.move(url, src=list(tabtable.keys()).index(tab), dest=cats.index(e))
            print(url, reader.book_info["url"])
            if url == reader.book_info["url"]:
                wind.perform_long_operation(lambda: mangakatana.get_manga_info(url), "book_list_got_info")
            wloading = popup_loading()
            wloading.read(timeout=0)
            wind.perform_long_operation(lambda: library.make_treedata(True), "library_moved")
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
        wreadlist.close()
        wind.perform_long_operation(library.make_window, "lib_window_made")
    
    if e in [v + "_open_book" for _, v in tabtable.items()]:
        tab = v["tab_group"]
        print(tab)
        try:
            url = v[tabtable[tab]][0]
        except: continue
        print(url)
        wind.perform_long_operation(lambda: mangakatana.get_manga_info(url), "lib_open_book")
    
    if e == "lib_open_book":
        try:
            reader.set_book_info(v[e])
        except: continue
        is_in_library, rows, which_list = library.is_in_lib(reader.book_info["url"])
        if is_in_library:
            ix = int(rows[1])
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
                "path": v["settings_storage_db_path"]
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
        print("All of the free manga found on this app are hosted on third-party servers that are freely available to read online for all internet users. Any legal issues regarding the free manga should be taken up with the actual file hosts themselves, as we're not affiliated with them. Copyrights and trademarks for the manga, and other promotional materials are held by their respective owners and their use is allowed under the fair use clause of the Copyright Law.")

wind.close()