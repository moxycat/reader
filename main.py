import PySimpleGUI as sg
from PIL import Image, ImageTk
import requests
import textwrap
import tempfile

import mangakatana
import reader, chapter_view

sg.theme("Default1")
sg.set_options(font=("Consolas", 10))

search_controls = [
    [
        sg.Menu([["&Library", ["Reading list", "Favourites"]], ["&Settings", ["&Preferences", "&Help"]]], key="menu")
    ],
    [
        sg.Combo(["Book name", "Author"], default_value="Book name", readonly=True, key="search_method", background_color="white", ),
        sg.Input("", key="search_bar", size=(90, 1), focus=True),
        sg.Button("🔍", key="search")
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
                    sg.Button("View chapters", key="details", visible=False),
                    sg.Button("Latest chapter", key="read_latest", visible=False),
                ]
                #[sg.Listbox([], key="preview_chapters", size=(50, 15), visible=False, horizontal_scroll=True)]
            ]
        )
    ]
]

layout = [
    [sg.Column(search_controls, visible=True)]
]

wind = sg.Window("Moxy's manga reader [alpha ver. 1]", layout=layout, element_justification="l", finalize=True)
wreader = None
wdetails = None
results = []
info = {}
images = []
image_urls = []
chapter_index = 0

while True:
    w, e, v = sg.read_all_windows()
    print(e)
    if w == wind and e == sg.WIN_CLOSED: break
    if w == wreader and e == sg.WIN_CLOSED:
        wreader.close()
        wind.un_hide()
    if e == "search":
        results.clear()
        query = v["search_bar"]
        mode = 0 if v["search_method"] == "Book name" else 1 if v["search_method"] == "Author" else 0
        if len(query) < 3:
            wind["search_status"].update("Try searching for 3 or more characters.")
            continue
        wind["search_status"].update("Searching...")
        wind.refresh()
        results = mangakatana.search(query, mode)
        if results is None:
            wind["search_status"].update("Found nothing.")
            continue
        names = [textwrap.shorten(a["title"], width=50, placeholder="...") for a in results]
        l = len(results)
        wind["search_status"].update("Found {} result{}.".format(l, "s" if l > 1 else ""))
        wind["book_list"].update(names)
    
    if e == "book_list":
        ix = wind["book_list"].get_indexes()[0]
        url = results[ix]["url"]
        info = mangakatana.get_manga_info(url)
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
        #wdetails["read"].update(visible=True)
        #wdetails["goto_chapter"].update(visible=True)
        wdetails["details_chapters"].Widget.configure(width = max([len(a) for a in chapter_and_date]))
        wdetails["details_chapters"].update(values=chapter_and_date, visible=True)
    
    if w == wdetails and e == sg.WIN_CLOSED:
        wdetails.close()
    
    if e == "details_chapters":
        ix = wdetails["details_chapters"].get_indexes()[0]
        nch = len(info["chapters"])
        print(nch)
        print(ix)
        chapter_index = nch - ix - 1
        wdetails.close()
        image_urls = mangakatana.get_manga_chapter_images(info["chapters"][chapter_index]["url"])
        images = [None] * len(image_urls)
        im = Image.open(requests.get(image_urls[0], stream=True).raw)
        #im.thumbnail((650, 650), resample=Image.BICUBIC)
        images[0] = ImageTk.PhotoImage(image=im)

        wind.hide()
        wreader = reader.reader_make_window()
        wreader["reader_page_num"].update("01/{}".format(str(len(image_urls))).zfill(2))
        wreader.TKroot.title(info["chapters"][chapter_index]["name"])
        wreader["reader_page_img"].update(data=images[0])
        wreader.refresh()
        wreader["reader_page_img_col"].contents_changed()

    if e == "read":
        chapter_index = 0
        image_urls = mangakatana.get_manga_chapter_images(info["chapters"][chapter_index]["url"])
        images = [None] * len(image_urls)
        im = Image.open(requests.get(image_urls[0], stream=True).raw)
        #im.thumbnail((650, 650), resample=Image.BICUBIC)
        images[0] = ImageTk.PhotoImage(image=im)

        wind.hide()
        wreader = reader.reader_make_window()
        wreader["reader_page_num"].update("01/{}".format(str(len(image_urls))).zfill(2))
        wreader.TKroot.title(info["chapters"][chapter_index]["name"])
        wreader["reader_page_img"].update(data=images[0])
        wreader.refresh()
        wreader["reader_page_img_col"].contents_changed()

    if e == "read_latest":
        chapter_index = len(info["chapters"]) - 1
        image_urls = mangakatana.get_manga_chapter_images(info["chapters"][chapter_index]["url"])
        images = [None] * len(image_urls)
        im = Image.open(requests.get(image_urls[0], stream=True).raw)
        #im.thumbnail((650, 650), resample=Image.BICUBIC)
        images[0] = ImageTk.PhotoImage(image=im)

        wind.hide()
        wreader = reader.reader_make_window()
        wreader["reader_page_num"].update("01/{}".format(str(len(image_urls)).zfill(2)))
        wreader.TKroot.title(info["chapters"][chapter_index]["name"])
        wreader["reader_page_img"].update(data=images[0])
        wreader.refresh()
        wreader["reader_page_img_col"].contents_changed()

    if e == "reader_page_num":
        max_page = int(wreader["reader_page_num"].get().split("/")[1])
        print(max_page)
        page = reader.jump(max_page)
        if page is None: continue
        if images[page - 1] is None:
            im = Image.open(requests.get(image_urls[0], stream=True).raw)
            images[page - 1] = ImageTk.PhotoImage(image=im)

        wreader["reader_page_num"].update("{}/{}".format(str(page).zfill(2), str(max_page).zfill(2)))
        wreader["reader_page_img"].update(data=images[page - 1])
        wreader.refresh()
        wreader["reader_page_img_col"].contents_changed()
        wreader["reader_page_img_col"].Widget.canvas.yview_moveto(0.0)
        wreader["reader_page_img_col"].Widget.canvas.xview_moveto(0.0)
    
    if e == "reader_go_fwd":
        current_page = int(wreader["reader_page_num"].get().split("/")[0])
        max_page = int(wreader["reader_page_num"].get().split("/")[1])
        if current_page + 1 > max_page: continue

        if images[current_page] is None:
            im = Image.open(requests.get(image_urls[current_page], stream=True).raw)
            images[current_page] = ImageTk.PhotoImage(image=im)

        wreader["reader_page_img"].update(data=images[current_page])
        wreader["reader_page_num"].update("{}/{}".format(str(current_page + 1).zfill(2), str(max_page).zfill(2)))
        wreader.refresh()
        wreader["reader_page_img_col"].contents_changed()
        wreader["reader_page_img_col"].Widget.canvas.yview_moveto(0.0)
        wreader["reader_page_img_col"].Widget.canvas.xview_moveto(0.0)

    if e == "reader_go_back":
        current_page = int(wreader["reader_page_num"].get().split("/")[0])
        max_page = int(wreader["reader_page_num"].get().split("/")[1])
        if current_page - 1 < 1: continue
        
        if images[current_page - 2] is None:
            im = Image.open(requests.get(image_urls[current_page - 2], stream=True).raw)
            images[current_page - 2] = ImageTk.PhotoImage(image=im)

        wreader["reader_page_img"].update(data=images[current_page - 2])
        wreader["reader_page_num"].update("{}/{}".format(str(current_page - 1).zfill(2), str(max_page).zfill(2)))
        wreader.refresh()
        wreader["reader_page_img_col"].contents_changed()
        wreader["reader_page_img_col"].Widget.canvas.yview_moveto(0.0)
        wreader["reader_page_img_col"].Widget.canvas.xview_moveto(0.0)

    if e == "reader_go_home":
        max_page = int(wreader["reader_page_num"].get().split("/")[1])
        wreader["reader_page_img"].update(data=images[0])
        wreader["reader_page_num"].update("01/{}".format(str(max_page).zfill(2)))
        wreader.refresh()
        wreader["reader_page_img_col"].contents_changed()
        wreader["reader_page_img_col"].set_vscroll_position(0.0)
        wreader["reader_page_img_col"].Widget.canvas.yview_moveto(0.0)
        wreader["reader_page_img_col"].Widget.canvas.xview_moveto(0.0)

    if e == "reader_go_end":
        max_page = int(wreader["reader_page_num"].get().split("/")[1])
        
        if images[max_page - 1] is None:
            im = Image.open(requests.get(image_urls[max_page - 1], stream=True).raw)
            images[max_page - 1] = ImageTk.PhotoImage(image=im)

        wreader["reader_page_img"].update(data=images[max_page - 1])
        wreader["reader_page_num"].update("{}/{}".format(str(max_page).zfill(2), str(max_page).zfill(2)))
        wreader.refresh()
        wreader["reader_page_img_col"].contents_changed()
        wreader["reader_page_img_col"].Widget.canvas.yview_moveto(0.0)
        wreader["reader_page_img_col"].Widget.canvas.xview_moveto(0.0)

    if e == "reader_go_next_ch":
        if chapter_index + 1 >= len(info["chapters"]):
            continue
        else: chapter_index += 1
        image_urls.clear()
        images.clear()
        
        image_urls = mangakatana.get_manga_chapter_images(info["chapters"][chapter_index]["url"])
        images = [None] * len(image_urls)
        im = Image.open(requests.get(image_urls[0], stream=True).raw)
        #im.thumbnail((650, 650), resample=Image.BICUBIC)
        images[0] = ImageTk.PhotoImage(image=im)
        wreader["reader_page_num"].update("01/{}".format(str(len(image_urls)).zfill(2)))
        wreader.TKroot.title(info["chapters"][chapter_index]["name"])
        wreader["reader_page_img"].update(data=images[0])
        wreader.refresh()
        wreader["reader_page_img_col"].contents_changed()
        wreader["reader_page_img_col"].Widget.canvas.yview_moveto(0.0)
        wreader["reader_page_img_col"].Widget.canvas.xview_moveto(0.0)

    if e == "reader_go_prev_ch":
        if chapter_index - 1 < 0:
            continue
        else: chapter_index -= 1
        image_urls.clear()
        images.clear()
        
        image_urls = mangakatana.get_manga_chapter_images(info["chapters"][chapter_index]["url"])
        images = [None] * len(image_urls)
        im = Image.open(requests.get(image_urls[0], stream=True).raw)
        images[0] = ImageTk.PhotoImage(image=im)
        wreader["reader_page_num"].update("01/{}".format(str(len(image_urls)).zfill(2)))
        wreader.TKroot.title(info["chapters"][chapter_index]["name"])
        wreader["reader_page_img"].update(data=images[0])
        wreader.refresh()
        wreader["reader_page_img_col"].contents_changed()
        wreader["reader_page_img_col"].Widget.canvas.yview_moveto(0.0)
        wreader["reader_page_img_col"].Widget.canvas.xview_moveto(0.0)

wind.close()