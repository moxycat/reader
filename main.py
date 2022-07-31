from io import BytesIO
from datetime import datetime
import json
import PySimpleGUI as sg
from PIL import Image, ImageTk
import requests
import textwrap

import mangakatana
import chapter_view, library, settings
from reader import Reader

def myround(x, prec=2, base=.05):
  return round(base * round(float(x)/base),prec)

#print(sg.LOOK_AND_FEEL_TABLE["DefaultNoMoreNagging"])
#sg.LOOK_AND_FEEL_TABLE["Default1"] = {'BACKGROUND': '#222222', 'TEXT': '#ffffff', 'INPUT': '1234567890', 'TEXT_INPUT': '1234567890', 'SCROLL': '1234567890', 'BUTTON': ('black', 'white'), 'PROGRESS': '1234567890', 'BORDER': 1, 'SLIDER_DEPTH': 1, 'PROGRESS_DEPTH': 0}
sg.theme("Default1")
sg.set_options(font=("Consolas", 10))

def popup_loading():
    return sg.Window("", layout=[
        [
            sg.Text("Loading...", font=("Consolas", 14))
        ]
    ], modal=True, no_titlebar=True, finalize=True)

menu = [["Readers", []], ["&Library", ["Reading list", "Favourites"]], ["&Settings", ["&Preferences", "&Help"]]]

search_controls = [
    [
        sg.Menu(menu, key="menu")
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
            ], element_justification="c", vertical_alignment="c"),
        sg.VSeparator(),
        #sg.Column(preview, scrollable=False, visible=False, key="preview_col"),
        sg.Column(
            [
                [sg.Text(key="preview_title", font="Consolas 14 underline")],
                [sg.Image(key="preview_image")]
            ], key="preview_col_0"),
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
            ], key="preview_col_1")
    ]
]

layout = [
    [sg.Column(search_controls, visible=True)],
    [sg.StatusBar("No activity", enable_events=True, key="search_statusbar", size=(50, 1))]
]

library.init_db()

wind = sg.Window("Moxy's manga reader [alpha ver. 1]", layout=layout, element_justification="l", finalize=True)

reader = Reader()
readers = []
#active_reader_index = -1

wdetails = None
wreadlist = None
wsettings = None
wloading = None
results = []
is_in_library = False
rows = []
download_start_time = 0
download_end_time = 0

def set_status(text):
    global wind
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
            menu[0][1][ix] = "{} - {}".format(readers[ix].book_info["title"],
                readers[ix].book_info["chapters"][readers[ix].chapter_index]["name"])
            wind["menu"].update(menu)
        
        if e == "reader_mini":
            readers[ix].window.hide()
        
        if e == sg.WIN_CLOSED:
            wind.un_hide()
            #library.update(readers[ix].book_info["url"], readers[ix].chapter_index, readers[ix].page_index)
            readers[ix].window.close()
            del readers[ix]
            del menu[0][1][ix]
            wind["menu"].update(menu)
        else:
            readers[ix].handle(e)
        
        if e == "reader_go_next_ch":
            library.update(readers[ix].book_info["url"], readers[ix].chapter_index, 0)
    
    if e in menu[0][1]:
        ix = menu[0][1].index(e)
        readers[ix].window.un_hide()
        readers[ix].window.bring_to_front()

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
        reader.set_book_info(v[e])
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
            ix = int(rows[1])
            wind["read_continue"].update(
                text="[{}]".format(textwrap.shorten(reader.book_info["chapters"][ix]["name"], width=25, placeholder="...")),
                visible=True)
            wind["read_continue"].set_tooltip(reader.book_info["chapters"][ix]["name"])
            reader.chapter_index = ix # kinda huh ngl maybe figure out a better solution
            reader.page_index = int(rows[2])
        else: wind["read_continue"].update(visible=False)
        wind["read_latest"].update(visible=True)
        wind["details"].update(visible=True)
        from tkinter.font import Font
        tkfont = Font(font=("Consolas", 10))
        fw, fh = tkfont.measure("A"), tkfont.metrics("linespace")
        _, colh = wind["preview_col_0"].get_size()
        _, colh1 = wind["preview_col_1"].get_size()
        #print(colh, colh1)
        #wind["book_list"].set_size((None, colh - 15))

    if e == "details":
        wdetails = chapter_view.make_window()
        wdetails.TKroot.title(reader.book_info["title"])
        chapters = [a["name"] for a in reader.book_info["chapters"][::-1]]
        dates = [a["date"] for a in reader.book_info["chapters"][::-1]]
        longestname = max([len(a) for a in chapters])
        chapter_and_date = ["{}{}{}".format(a[0], " " * (longestname - len(a[0]) + 5), a[1]) for a in zip(chapters, dates)]
        wdetails["details_chapters"].Widget.configure(width = max([len(a) for a in chapter_and_date]))
        wdetails["details_chapters"].update(values=chapter_and_date, visible=True)
        if is_in_library:
            wdetails["details_chapters"].Widget.itemconfigure(len(reader.book_info["chapters"]) - reader.chapter_index - 1, bg="yellow")
    
    if w == wdetails and e == sg.WIN_CLOSED:
        wdetails.close()
        wdetails = None
    
    # loader + downloader
    if e == "details_chapters":
        ix = wdetails["details_chapters"].get_indexes()[0]
        ix = len(reader.book_info["chapters"]) - ix - 1

        readers.append(Reader(reader.book_info))
        menu[0][1].append("{} - {}".format(readers[-1].book_info["title"],
            readers[-1].book_info["chapters"][ix]["name"]))
        wind["menu"].update(menu)

        set_status("Downloading chapter...")
        download_start_time = datetime.utcnow().timestamp()
        wloading = popup_loading()
        wloading.read(timeout=0)
        wind.perform_long_operation(lambda: readers[-1].set_chapter(ix), "open_reader")
        wdetails.close()

    if e == "read_latest":
        wind["menu"].update(menu)
        ix = len(reader.book_info["chapters"]) - 1

        readers.append(Reader(reader.book_info))
        menu[0][1].append("{} - {}".format(readers[-1].book_info["title"],
            readers[-1].book_info["chapters"][ix]["name"]))

        set_status("Downloading chapter...")
        download_start_time = datetime.utcnow().timestamp()
        wloading = popup_loading()
        wloading.read(timeout=0)
        wind.perform_long_operation(lambda: readers[-1].set_chapter(ix), "open_reader")
    
    if e == "read_continue":
        readers.append(Reader(reader.book_info))
        menu[0][1].append("{} - {}".format(readers[-1].book_info["title"],
            readers[-1].book_info["chapters"][ix]["name"]))
        wind["menu"].update(menu)
        #print(menu[0])
        set_status("Downloading chapter...")
        download_start_time = datetime.utcnow().timestamp()
        wloading = popup_loading()
        wloading.read(timeout=0)
        #readers[-1].page_index = reader.page_index
        wind.perform_long_operation(lambda: readers[-1].set_chapter(reader.chapter_index), "open_reader")
    
    if e == "open_reader":
        download_end_time = datetime.utcnow().timestamp()
        if wloading is not None: wloading.close()
        set_status(
            f"Downloaded chapter! Took {round(download_end_time - download_start_time, 2)} seconds for {len(readers[-1].images)} pages ({round(float(len(readers[-1].images))/(download_end_time - download_start_time), 2)} page/s)")
        if is_in_library and reader.chapter_index < readers[-1].chapter_index:
            library.update(readers[-1].book_info["url"], readers[-1].chapter_index, 0)
        elif not is_in_library: library.add(readers[-1].book_info["url"], readers[-1].chapter_index, 0)
        readers[-1].make_window()
        readers[-1].set_page(0)
        #wind.hide()

    if e == "Save screenshot":
        ix = reader_windows.index(w)
        filename = sg.popup_get_file(message="Please choose where to save the file", title="Save screenshot",
        default_extension="png", file_types=(("Image", "*.png png"),), save_as=True,
        default_path=f"{readers[ix].page_index + 1}.png")
        im = Image.open(BytesIO(readers[ix].images[readers[ix].page_index]))
        im.save(filename, "png")
        im.close()
    
    if e == "Reading list":
        if wreadlist is not None:
            wreadlist.un_hide()
            wreadlist.bring_to_front()
        else:
            wloading = popup_loading()
            wloading.read(timeout=0)
            wind.perform_long_operation(library.make_window_layout, "lib_window_made")

    if e == "lib_window_made":
        if wloading is not None: wloading.close()
        lo = v[e]
        wreadlist = sg.Window("Reading list", lo, finalize=True)
        wreadlist["lib_tree"].bind("<Double-Button-1>", "_open_book")
        # idk why this happens but when you double click an event gets generated for the tree AND the double click but they get merged into one
        #wreadlist["lib_tree"].bind("<Button-3>", lambda event, element=wreadlist["lib_tree"]: library.right_click_menu_callback(event, element))
    
    if e == "lib_search":
        q = v["lib_search_query"]
        print(q)
        library.search(q, wreadlist["lib_tree"])

    if w == wreadlist and e == "Edit chapter":
        url = v["lib_tree"][0]
        library.edit_chapter_progress(url)
    
    if w == wreadlist and e == "Refresh":
        wreadlist.close()
        wind.perform_long_operation(library.make_window_layout, "lib_window_made")

    if e == "lib_tree_open_book":
        url = v["lib_tree"][0]
        wind.perform_long_operation(lambda: mangakatana.get_manga_info(url), "book_list_got_info")
    
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