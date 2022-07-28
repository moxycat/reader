from io import BytesIO
from datetime import datetime
import PySimpleGUI as sg
from PIL import Image, ImageTk
import requests
import textwrap

import mangakatana
import reader, chapter_view, library

def myround(x, prec=2, base=.05):
  return round(base * round(float(x)/base),prec)

sg.theme("Default1")
sg.set_options(font=("Consolas", 10))

search_controls = [
    [
        sg.Menu([["&Library", ["Reading list", "Favourites"]], ["&Settings", ["&Preferences", "&Help"]]], key="menu")
    ],
    [
        sg.Combo(["Book name", "Author"], default_value="Book name", readonly=True, key="search_method", background_color="white", ),
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

wind = sg.Window("Moxy's manga reader [alpha ver. 1]", layout=layout, element_justification="l", finalize=True)
wreader = None
wdetails = None
wreadlist = None
results = []
info = {}
images = []
image_urls = []
chapter_index = 0
page_index = 0
vscroll_perc = 0.0
hscroll_perc = 0.0
is_in_library = False
download_start_time = 0
download_end_time = 0

def set_page():
    global wreader, images, page_index, chapter_index, vscroll_perc, hscroll_perc
    wreader["reader_page_num"].update("{}/{}".format(str(page_index + 1).zfill(2), str(len(images)).zfill(2)))
    wreader.TKroot.title(info["chapters"][chapter_index]["name"])
    wreader["reader_page_img"].update(data=images[page_index])
    wreader.refresh()
    wreader["reader_page_img_col"].contents_changed()
    if chapter_index == 0:
        wreader["reader_go_prev_ch"].update(disabled=True)
    else:
        wreader["reader_go_prev_ch"].update(disabled=False)

    if chapter_index == len(info["chapters"]) - 1:
        wreader["reader_go_next_ch"].update(disabled=True)
    else:
        wreader["reader_go_next_ch"].update(disabled=False)

    if page_index == 0:
        wreader["reader_go_back"].update(disabled=True)
    else:
        wreader["reader_go_back"].update(disabled=False)

    if page_index == len(images) - 1:
        wreader["reader_go_fwd"].update(disabled=True)
    else:
        wreader["reader_go_fwd"].update(disabled=False)

    vscroll_perc = 0.0
    #hscroll_perc = 0.0
    wreader["reader_page_img_col"].Widget.canvas.yview_moveto(vscroll_perc)
    #wreader["reader_page_img_col"].Widget.canvas.xview_moveto(hscroll_perc)
    wreader.write_event_value("opened_page", "")

def reader_get_images():
    global page_index, image_urls, images, chapter_index, wind, wreader, download_start_time
    page_index = 0
    
    image_urls = mangakatana.get_manga_chapter_images(info["chapters"][chapter_index]["url"])
    download_start_time = datetime.utcnow().timestamp()
    images = mangakatana.download_images(image_urls)

def open_reader():
    global wind, wreader
    wind.hide()
    if wreader is None: wreader = reader.reader_make_window()
    else: wreader.bring_to_front()

while True:
    w, e, v = sg.read_all_windows()
    print(e)
    if w == wind and e == sg.WIN_CLOSED: break
    if w == wreader and e == sg.WIN_CLOSED:
        wreader.close()
        wreader = None
        wind.refresh()
        wind.un_hide()
    
    if e == "search":
        #results.clear()
        query = v["search_bar"]
        mode = 0 if v["search_method"] == "Book name" else 1 if v["search_method"] == "Author" else 0
        if len(query) < 3:
            wind["search_status"].update("Try searching for 3 or more characters.")
            continue
        wind["search_status"].update("Searching...")
        wind.refresh()
        wind.perform_long_operation(lambda: mangakatana.search(query, mode), "search_got_results")
        
    if e == "search_got_results":
        results = v[e]
        #print(results)
        if results is None:
            wind["search_status"].update("Found nothing.")
            continue
        names = [textwrap.shorten(a["title"], width=50, placeholder="...") for a in results]
        l = len(results)
        wind["search_status"].update("Found {} result{}.".format(l, "s" if l > 1 else ""))
        wind["book_list"].update(names)

    if e == "book_list":
        try:
            ix = wind["book_list"].get_indexes()[0]
        except: continue
        url = results[ix]["url"]
        wind.perform_long_operation(lambda: mangakatana.get_manga_info(url), "book_list_got_info")

    if e == "book_list_got_info":
        info = v[e]
        im = Image.open(requests.get(info["cover_url"], stream=True).raw)
        im.thumbnail(size=(320, 320), resample=Image.BICUBIC)
        wind["preview_image"].update(data=ImageTk.PhotoImage(image=im))
        wind["preview_title"].update("\n".join(textwrap.wrap(info["title"], width=im.width//8)))
        wind["preview_title"].set_tooltip("\n".join(info["alt_names"]))
        #wind["preview_alt_names"].update("Alt names(s): " + ";\n                     ".join(info["alt_names"]))
        wind["preview_author"].update("Author:         " + info["author"])
        genres = ""
        for i, g in enumerate(info["genres"]):
            if i == len(info["genres"]) - 1:
                genres += g
                break
            genres += g + "," + ("\n                " if i % 3 == 2 else " ")
        wind["preview_genres"].update("Genres:         " + genres)
        wind["preview_status"].update("Status:         " + info["status"])
        wind["preview_latest"].update("Latest chapter: " + info["chapters"][-1]["name"])
        wind["preview_update"].update("Updated at:     " + info["chapters"][-1]["date"])
        wind["preview_desc"].update("\n".join(textwrap.wrap(info["description"], width=50)), visible=True)
        
        is_in_library, rows = library.is_in_lib(info["url"])
        if is_in_library:
            chapter_index = int(rows[1]) + (1 if int(rows[1]) < len(info["chapters"]) else 0)
            wind["read_continue"].update(
                text="[{}]".format(info["chapters"][chapter_index]["name"]),
                visible=True)
        else: wind["read_continue"].update(visible=False)
        wind["read_latest"].update(visible=True)
        wind["details"].update(visible=True)
        wind.refresh()

    if e == "details":
        wdetails = chapter_view.make_window()
        wdetails.TKroot.title(info["title"])
        chapters = [a["name"] for a in info["chapters"][::-1]]
        dates = [a["date"] for a in info["chapters"][::-1]]
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
        chapter_index = len(info["chapters"]) - ix - 1
        wind["search_statusbar"].update("Downloading chapter...")
        wind.refresh()
        wind.perform_long_operation(lambda: reader_get_images(), "open_reader")
        wdetails.close()

    if e == "read_latest":
        chapter_index = len(info["chapters"]) - 1
        wind["search_statusbar"].update("Downloading chapter...")
        wind.refresh()
        wind.perform_long_operation(lambda: reader_get_images(), "open_reader")
    
    if e == "read_continue":
        wind["search_statusbar"].update("Downloading chapter...")
        wind.refresh()
        wind.perform_long_operation(lambda: reader_get_images(), "open_reader")

    if e == "reader_go_next_ch":
        if chapter_index + 1 >= len(info["chapters"]): continue
        else: chapter_index += 1
        if page_index == len(images) - 1:
            if is_in_library: library.update(info["url"], chapter_index - 1, page_index)
            else: library.add(info["url"], chapter_index - 1, page_index)
        wind.perform_long_operation(lambda: reader_get_images(), "open_reader")

    if e == "reader_go_prev_ch":
        if chapter_index - 1 < 0: continue
        else: chapter_index -= 1
        wind.perform_long_operation(lambda: reader_get_images(), "open_reader")
    
    if e == "open_reader":
        download_end_time = datetime.utcnow().timestamp()
        wind["search_statusbar"].update(f"Downloaded chapter! {(download_end_time - download_start_time)/len(images)} sec./page")
        wind.refresh()
        open_reader()
        set_page()

    if e == "reader_page_num":
        max_page = int(wreader["reader_page_num"].get().split("/")[1])
        page = reader.jump(max_page)
        if page is None: continue
        page_index = page - 1
        set_page()
    
    if e == "reader_scroll_down":
        if vscroll_perc + 0.05 <= 1.0: vscroll_perc += 0.05
        else: continue
        vscroll_perc = myround(vscroll_perc, 2)
        print(vscroll_perc)
        wreader["reader_page_img_col"].Widget.canvas.yview_moveto(vscroll_perc)

    if e == "reader_scroll_up":
        if vscroll_perc - 0.05 >= 0.0: vscroll_perc -= 0.05
        else: continue
        vscroll_perc = myround(vscroll_perc, 2)
        print(vscroll_perc)
        wreader["reader_page_img_col"].Widget.canvas.yview_moveto(vscroll_perc)

    if e == "reader_scroll_left":
        if hscroll_perc - 0.05 >= 0: hscroll_perc -= 0.05
        else: continue
        hscroll_perc = myround(hscroll_perc, 2)
        print(hscroll_perc)
        wreader["reader_page_img_col"].Widget.canvas.xview_moveto(hscroll_perc)

    if e == "reader_scroll_right":
        if hscroll_perc + 0.05 >= 0: hscroll_perc += 0.05
        else: continue
        hscroll_perc = myround(hscroll_perc, 2)
        print(hscroll_perc)
        wreader["reader_page_img_col"].Widget.canvas.xview_moveto(hscroll_perc)

    if e == "reader_go_fwd":
        max_page = int(wreader["reader_page_num"].get().split("/")[1])
        if page_index + 1 > max_page - 1: continue
        page_index += 1
        set_page()
        if chapter_index == len(info["chapters"]) - 1 and page_index == max_page - 1:
            if is_in_library:
                library.update(info["url"], chapter_index - 1, page_index)
            else:
                library.add(info["url"], chapter_index - 1, page_index)

    if e == "reader_go_back":
        if page_index - 1 < 0: continue
        page_index -= 1
        set_page()

    if e == "reader_go_home":
        page_index = 0
        set_page()

    if e == "reader_go_end":
        page_index = len(images) - 1
        set_page()

    if e == "opened_page":
        im = Image.open(BytesIO(images[page_index]))
        print(wreader.size)
        wreader.TKroot.maxsize(im.width + 45, im.height + 70)
        im.close()
    
    if e == "Maximize window":
        wreader.Maximize()
    
    if e == "Save screenshot":
        filename = sg.popup_get_file(message="Please choose where to save the file", title="Save screenshot",
        default_extension="png", file_types=(("Image", "*.png png"),), save_as=True,
        default_path=f"{page_index + 1}.png")
        im = Image.open(BytesIO(images[page_index]))
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
    
    if e == "lib_tree":
        print(v[e])
    
    if w == wreadlist and e == sg.WIN_CLOSED:
        wreadlist.close()
        wreadlist = None
    
    if e == "reader_resized":
        # def_size = (845, 670) # 45 wpad, 70 hpad
        im = Image.open(BytesIO(images[page_index]))
        #print(wreader.size)
        #wreader.TKroot.maxsize(im.width + 45, im.height + 70)
        opts = {"width": wreader.size[0] - 45, "height": wreader.size[1] - 70}
        wreader["reader_page_img_col"].Widget.canvas.configure(**opts)
        
wind.close()