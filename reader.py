import PySimpleGUI as sg
from io import BytesIO
from PIL import Image
from requests_html import HTMLSession
import os

import mangakatana
import settings
import bluefilter
import library

from util import ThreadThatReturns, outer_trim

class Reader:
    window: sg.Window = None # window object
    popup_window: sg.Window = None # popup window object (for showing the loading popup)
    updated: bool = False # does this book get updated in the library
    images: list[bytes] = [] # array of each page's image data
    cache: list[bytes] = [] # next chapter's images
    book_info: dict = {} # info about book
    chapter_index: int = 0 # current chapter's index
    max_chapter_index: int = 0 # ...
    max_page_index: int = 0 # ...
    page_index: int = 0 # current page's index
    vscroll: float = 0 # vertical scroll position
    hscroll: float = 0 # horizontal scroll position
    zoom_level: float = 1.0 # ...
    zoom_lock: bool = False
    downloading: bool = False
    zoom_to_fit: bool = False
    zoom_to_fit_mode: str = "b"
    zoom_size: tuple[int, int] = (None, None)
    last_size = (0, 0)

    def get_frame_size(self):
        return (self.window.size[0] - 45, self.window.size[1] - (105 if settings.settings["ui"]["theme"] == "Light" else 107))

    def set_book_info(self, book_info: dict):
        self.book_info = book_info.copy()
        self.max_chapter_index = len(self.book_info["chapters"]) - 1

    def __init__(self, book_info: dict = {}):
        if book_info != {}: self.set_book_info(book_info)
        else:
            self.book_info = {
            "url": "",
            "cover_url": "",
            "title": "",
            "alt_names": [],
            "author": "",
            "genres": [],
            "status": "",
            "description": "",
            "chapters": []
            }
            self.max_chapter_index = 0
        self.html_session = HTMLSession()
        self.html_session.browser

    def cache_chapter(self, chapter_index: int) -> list[bytes]:
        if chapter_index > self.max_chapter_index: return False

        ttr = ThreadThatReturns(target=mangakatana.get_manga_chapter_images, args=(self.book_info["chapters"][chapter_index]["url"], self.html_session))
        ttr.start()
        image_urls = ttr.join()
        if None in image_urls: return False
        self.cache = mangakatana.download_images(image_urls)
        if None in self.cache: return False
        if int(settings.settings["reader"]["filter"]) > 0:
            self.cache = bluefilter.bulk_bluefilter(self.cache, int(settings.settings["reader"]["filter"]))
        return True

    # use perform_long_operation with this one or the UI will hang
    def set_chapter(self, chapter_index: int =-1):
        if chapter_index != -1: self.chapter_index = chapter_index
        self.downloading = True

        chapter_url = self.book_info["chapters"][chapter_index]["url"]
        
        images = library.get_pages(chapter_url)
        if images != []:
            self.images.clear()
            self.images = images
            self.max_page_index = len(self.images) - 1
            self.downloading = False
            return True

        ttr = ThreadThatReturns(target=mangakatana.get_manga_chapter_images, args=(chapter_url, self.html_session))
        ttr.start()
        image_urls = ttr.join()
        if None in image_urls: return False
        images = mangakatana.download_images(image_urls)
        if None in images: return False
        if int(settings.settings["reader"]["filter"]) > 0:
            images = bluefilter.bulk_bluefilter(images, int(settings.settings["reader"]["filter"]))

        self.images.clear()
        self.images = images
        self.max_page_index = len(self.images) - 1
        self.downloading = False
        if self.window is not None:
            library.set_pages(chapter_url, None, self.images)
            self.window.refresh()
        return True

    def check_if_mini(self, event):
        if self.window.TKroot.state() == "iconic":
            self.window.write_event_value("reader_mini", "")

    def mw_vscroll(self, ev):
        direction = int(-1 * (ev.delta / 120)) # 1 = down, -1 = up
        self.inc_vscroll(direction * 0.05)
    
    def mw_hscroll(self, ev):
        direction = int(-1 * (ev.delta / 120)) # 1 = down, -1 = up
        self.inc_hscroll(direction * 0.05)

    def zoom(self):
        im = Image.open(BytesIO(self.images[self.page_index]))

        im = im.resize((round(self.zoom_level * im.width), round(self.zoom_level * im.height)), resample=Image.BICUBIC)
        outbuf = BytesIO()
        im.save(outbuf, "png")
        self.refresh(outbuf.getvalue())
    
    def autoscroll_frame(self):
        _, view_h = self.get_frame_size()
        _, total_h = Image.open(BytesIO(self.images[self.page_index])).size
        scroll = ((self.vscroll * total_h) + view_h) / total_h
        if scroll > 1.0:
            self.window.write_event_value("reader_go_fwd", None)
        else:
            self.set_vscroll(scroll)
        
        
        

    # resize an image to fit the dimensions of the current window size (keeps AR)
    def zoom_fit(self, image: bytes, mode: str="b"):
        "modes: b - both; h - horizontal; v - vertical"
        im = Image.open(BytesIO(image))
        iw, ih = im.size
        ww, wh = self.get_frame_size()
        w, h = 0, 0
        #print(ww, wh)
        match mode:
            case "b":
                w, h = ww, wh
            case "h":
                w, h = ww, ih
            case "v":
                w, h = iw, wh
        #print(ww, wh)
        try:
            im.thumbnail((w, h), Image.BICUBIC)
        except Exception as e:
            return None
        outbuf = BytesIO()
        im.save(outbuf, "png")
        return outbuf.getvalue()

    def make_window(self):
        layout = [
            [sg.Menu([["&File", ["Save &screenshot", "Save &chapter"]], ["&Tools", ["Page scaling", ["Default", "Horizontal", "Vertical", "Both"], "Zoom", ["+", "-"]]]], key="reader_menu")],
            [sg.Column([
                [sg.Button("⌕+", key="reader_zoom_in", pad=0, font=("Consolas", 10)), sg.Text("x1.0", key="reader_zoom_level", pad=0, font=("Consolas", 10)), sg.Button("⌕-", key="reader_zoom_out", pad=0, font=("Consolas", 10)), sg.Button("Fit", key="reader_zoom_fit", pad=0, font=("Consolas", 10)), sg.Button("Cache next ch.", key="reader_cache", pad=0, font=("Consolas", 10))]
            ], key="reader_zoom_controls", element_justification="l", justification="l", vertical_alignment="l")],
            [sg.HSeparator()],
            [
                [
                    sg.Column([
                        [sg.Image(key="reader_page_img", enable_events=False, pad=0)]
                    ], size=(int(settings.settings["reader"]["w"]), int(settings.settings["reader"]["h"])), scrollable=True, key="reader_page_img_col", element_justification="c",
                    background_color="white")
                ],
                [sg.HSeparator()],
                [
                    sg.Button("prev ch.", key="reader_go_prev_ch", font=("Consolas", 10)),
                    sg.Button("≪", key="reader_go_home", font=("Consolas", 10)),
                    sg.Text(font=("Consolas", 10)), sg.Text(font=("Consolas", 10)),
                    sg.Button("<", key="reader_go_back", font=("Consolas", 10)),
                    sg.Text("01/??", key="reader_page_num", enable_events=True, font=("Consolas", 10)),
                    sg.Button(">", key="reader_go_fwd", font=("Consolas", 10)),
                    sg.Text(font=("Consolas", 10)), sg.Text(font=("Consolas", 10)),
                    sg.Button("≫", key="reader_go_end", font=("Consolas", 10)),
                    sg.Button("next ch.", key="reader_go_next_ch", font=("Consolas", 10))
                ]
            ]
        ]

        self.window = sg.Window("", layout, element_justification="c", finalize=True, resizable=True)
        self.window.bind("<Shift-Right>", "reader_go_fwd")
        self.window.bind("<Shift-Left>", "reader_go_back")
        self.window.bind("<Shift-Home>", "reader_go_home")
        self.window.bind("<Shift-End>", "reader_go_end")
        self.window.bind("<Right>", "reader_scroll_right")
        self.window.bind("<Left>", "reader_scroll_left")
        self.window.bind("<Down>", "reader_scroll_down")
        self.window.bind("<Up>", "reader_scroll_up")
        self.window.TKroot.bind("<MouseWheel>", self.mw_vscroll)
        self.window.TKroot.bind("<Shift-MouseWheel>", self.mw_hscroll)
        self.window.bind("<Shift-Prior>", "reader_go_prev_ch")
        self.window.bind("<Shift-Next>", "reader_go_next_ch")
        self.window.bind("<Configure>", "reader_resized")
        self.window.TKroot.bind("<Unmap>", self.check_if_mini)
        self.window.bind("<Map>", "reader_shown")
        self.window.TKroot.bind("<Prior>", lambda _: self.set_vscroll(0.0))
        self.window.TKroot.bind("<Next>", lambda _: self.set_vscroll(1.0))
        self.window.TKroot.bind("<Home>", lambda _: self.set_hscroll(0.0))
        self.window.TKroot.bind("<End>", lambda _: self.set_hscroll(1.0))
        self.window.TKroot.bind("<space>", lambda _: self.autoscroll_frame())

        self.window["reader_page_img"].bind("<Button-3>", "_reader_go_back")
        self.window["reader_page_img"].bind("<Button-1>", "_reader_go_fwd")
        
        self.window.TKroot.minsize(45, (105 if settings.settings["ui"]["theme"] == "Light" else 107))
        print(self.window["reader_go_prev_ch"].get_size(),
              self.window["reader_go_home"].get_size(),
              self.window["reader_page_num"].get_size(),
              self.window["reader_go_back"].get_size(),
              self.window["reader_go_next_ch"].get_size(),
              "white space", sg.Text().get_size()
            )
        #self.window["reader_page_img"].bind("<Double-Button-1>", "_reader_go_home")
        #self.window["reader_page_img"].bind("<Double-Button-3>","_reader_go_end")
    
    def refresh(self, image = None) -> None:
        if image is not None:
            self.window["reader_page_img"].update(data=image)
            self.window["reader_zoom_level"].update("x" + str(self.zoom_level))
            self.window.refresh()
            self.window["reader_page_img_col"].contents_changed()
            return
        self.hscroll = 0
        self.vscroll = 0
        self.zoom_level = 1.0
        self.window["reader_page_num"].update(
            f"{str(self.page_index + 1).zfill(2)}/{str(self.max_page_index + 1).zfill(2)}")
        self.window.TKroot.title(self.book_info["chapters"][self.chapter_index]["name"])
        self.window["reader_go_prev_ch"].update(disabled=settings.settings["general"]["offline"])
        if self.chapter_index - 1 >= 0 and self.book_info["chapters"][self.chapter_index - 1]["url"] in library.get_downloaded_chapters():
            self.window["reader_go_prev_ch"].update(disabled=False)
        self.window["reader_go_prev_ch"].update(disabled=self.downloading or (self.chapter_index == 0))

        self.window["reader_go_next_ch"].update(disabled=settings.settings["general"]["offline"])
        if self.chapter_index + 1 <= self.max_chapter_index and self.book_info["chapters"][self.chapter_index + 1]["url"] in library.get_downloaded_chapters():
            self.window["reader_go_next_ch"].update(disabled=False)
        self.window["reader_go_next_ch"].update(disabled=self.downloading or (self.chapter_index == self.max_chapter_index))

        self.window["reader_go_back"].update(disabled=self.page_index == 0)
        self.window["reader_go_fwd"].update(disabled=self.page_index == self.max_page_index)
        self.window["reader_go_end"].update(disabled=self.page_index == self.max_page_index)
        self.window["reader_go_home"].update(disabled=self.page_index == 0)
        self.window["reader_cache"].update(disabled=settings.settings["general"]["offline"] or (self.cache != [] or self.chapter_index == self.max_chapter_index))
        
        if self.zoom_to_fit:
            theimage = self.zoom_fit(self.images[self.page_index], self.zoom_to_fit_mode)
        else:
            theimage = self.images[self.page_index]

        if self.cache == []:
            self.window["reader_cache"].update("cache next ch.")
        self.window["reader_page_img"].update(data=theimage)
        self.window["reader_zoom_level"].update("x" + str(self.zoom_level))
        self.window.refresh()
        self.window["reader_page_img_col"].contents_changed()
        self.window["reader_page_img_col"].Widget.canvas.yview_moveto(0.0)
        self.window["reader_page_img_col"].Widget.canvas.xview_moveto(0.0)
        im = Image.open(BytesIO(theimage))
        if not self.zoom_to_fit:
            w, h = im.width, im.height
            self.window.TKroot.maxsize(w + 45, h + (105 if settings.settings["ui"]["theme"] == "Light" else 107))
            self.zoom_size = (None, None)
        else:
            if self.zoom_to_fit_mode == "h": w, h = self.window.size[0], im.height
            elif self.zoom_to_fit_mode == "v": w, h = im.width, self.window.size[1]
            elif self.zoom_to_fit_mode == "b": w, h = self.get_frame_size()
            if not self.zoom_size: self.zoom_size = (w, h)
            self.window.TKroot.maxsize(*self.zoom_size)
        
        
        im.close()

    def set_window_size(self, w, h):
        minw, minh = self.window.TKroot.minsize()
        maxw, maxh = self.window.TKroot.maxsize()
        self.window.TKroot.minsize(w, h)
        self.window.TKroot.maxsize(w, h)
        self.window.refresh()
        self.window.TKroot.minsize(minw, minh)
        self.window.TKroot.maxsize(maxw, maxh)
        self.window.refresh()

    def resized(self):
        #print(self.window.TKroot.state())
        if self.window.TKroot.state() == "normal":
            if self.window.size != self.last_size: self.refresh()
        if self.window.TKroot.state() == "zoomed":
            self.window.maximize()
        if self.window.TKroot.wm_state() == "iconic":
            self.window.hide()
        self.last_size = self.window.size
        #print(self.window.size)
        w, h = self.get_frame_size()
        opts = {"width": w, "height": h}
        self.window["reader_page_img_col"].Widget.canvas.configure(**opts)

    def set_page(self, n):
        if n >= 0 and n <= self.max_page_index:
            self.page_index = n
            self.refresh()
    
    def next_page(self) -> None:
        if self.page_index + 1 <= self.max_page_index:
            self.page_index += 1
            self.refresh()
    
    def prev_page(self) -> None:
        if self.page_index - 1 >= 0:
            self.page_index -= 1
            self.refresh()
    
    def inc_hscroll(self, d):
        if self.hscroll + d >= 0 and self.hscroll + d <= 1.0:
            self.hscroll += d
            self.window["reader_page_img_col"].Widget.canvas.xview_moveto(self.hscroll)

    def inc_vscroll(self, d):
        if self.vscroll + d >= 0 and self.vscroll + d <= 1.0:
            self.vscroll += d
            self.window["reader_page_img_col"].Widget.canvas.yview_moveto(self.vscroll)
    
    def set_vscroll(self, val):
        if val >= 0 and val <= 1:
            self.vscroll = val
            self.window["reader_page_img_col"].Widget.canvas.yview_moveto(val)

    def set_hscroll(self, val):
        if val >= 0 and val <= 1:
            self.hscroll = val
            self.window["reader_page_img_col"].Widget.canvas.xview_moveto(val)

    def next_chapter(self) -> None:
        if self.chapter_index + 1 > self.max_chapter_index: return
        url = self.book_info["chapters"][self.chapter_index]["url"]
        library.unsetas_opened(url)
        self.chapter_index += 1
        url = self.book_info["chapters"][self.chapter_index]["url"]
        autodownload = url not in library.get_downloaded_chapters()
        library.setas_opened(self.book_info["url"], url, autodownload)
        self.window["reader_go_next_ch"].update(disabled=True)
        self.window["reader_go_prev_ch"].update(disabled=True)
        if self.cache == []:
            self.window.perform_long_operation(lambda: self.set_chapter(self.chapter_index), "reader_loaded_chapter")
        else:
            self.images = self.cache.copy()
            self.cache.clear()
            self.max_page_index = len(self.images) - 1
            self.window.write_event_value("reader_loaded_chapter", "")
    
    def prev_chapter(self):
        if self.chapter_index - 1 < 0: return
        url = self.book_info["chapters"][self.chapter_index]["url"]
        library.unsetas_opened(url)
        self.chapter_index -= 1
        url = self.book_info["chapters"][self.chapter_index]["url"]
        autodownload = url not in library.get_downloaded_chapters()
        library.setas_opened(self.book_info["url"], url, autodownload)
        self.window["reader_go_next_ch"].update(disabled=True)
        self.window["reader_go_prev_ch"].update(disabled=True)
        self.window.perform_long_operation(lambda: self.set_chapter(self.chapter_index), "reader_loaded_chapter")

    def set_zoom(self, d):
        if self.zoom_level + d <= 0: return
        self.zoom_level += d
        self.zoom()

    def jump(self):
        layout = [
            [sg.Input(key="npage", size=(len(str(self.max_page_index + 1)), 1), focus=True), sg.Text("/", pad=(0, 0)), sg.Input(self.max_page_index + 1, readonly=True, disabled_readonly_background_color="white", size=(len(str(self.max_page_index + 1)), 1))],
            [sg.Button("Jump", key="jump", bind_return_key=True), sg.Button("Cancel", key="cancel")]
        ]
        w = sg.Window("Jump to page", layout, element_justification="c", modal=True, disable_minimize=True)
        val = None
        while True:
            e, v = w.read()
            if e == "cancel" or e == sg.WIN_CLOSED:
                w.close()
                return
            if e == "jump":
                val = v["npage"]
                try: val = int(val)
                except:
                    w["npage"].update("")
                    continue
                if val <= self.max_page_index + 1 and val >= 1: break
        w.close()
        self.page_index = val - 1
        self.refresh()

    # does not handle close events
    def handle(self, event):
        if event == "reader_go_fwd" or event == "reader_page_img_reader_go_fwd": self.next_page()
        elif event == "reader_go_back" or event == "reader_page_img_reader_go_back": self.prev_page()
        elif event == "reader_go_home" or event == "reader_page_img_reader_go_home": self.set_page(0)
        elif event == "reader_go_end" or event == "reader_page_img_reader_go_end": self.set_page(self.max_page_index)
        elif event == "reader_page_num": self.jump()
        elif event == "reader_go_prev_ch": self.prev_chapter()
        elif event == "reader_go_next_ch": self.next_chapter()
        elif event == "reader_scroll_right": self.inc_hscroll(0.01)
        elif event == "reader_scroll_left": self.inc_hscroll(-0.01)
        elif event == "reader_scroll_down": self.inc_vscroll(0.01)
        elif event == "reader_scroll_up": self.inc_vscroll(-0.01)
        elif event == "reader_resized": self.resized()
        elif event == "reader_loaded_chapter":
            self.window["reader_cache"].update(disabled=False)
            self.set_page(0)
            self.refresh()
        elif event == "reader_zoom_in": self.set_zoom(0.25)
        elif event == "reader_zoom_out": self.set_zoom(-0.25)
        elif event == "reader_cache":
            if self.chapter_index + 1 <= self.max_chapter_index:
                self.window["reader_cache"].update(disabled=True)
                self.window["reader_cache"].update("caching...")
                self.window.perform_long_operation(lambda: self.cache_chapter(self.chapter_index + 1), "reader_cached_next")
        elif event == "reader_cached_next":
            self.window["reader_cache"].update("cached")
        
        elif event == "Save screenshot":
            files = os.listdir()
            defpath = f"{self.page_index + 1}.png"
            n = 1
            while defpath in files:
                defpath = f"{self.page_index + 1}_{n}.png"
                n += 1
            filename = sg.popup_get_file(message="Please choose where to save the file", title="Save screenshot",
            default_extension="png", file_types=(("Image", "*.png png"),), save_as=True,
            default_path=defpath)
            if filename is None: return
            im = Image.open(BytesIO(self.images[self.page_index]))
            im.save(filename, "png")
            im.close()
        
        if event == "Save chapter":
            library.save_opened(self.book_info["chapters"][self.chapter_index]["url"])
        
        if event == "Both":
            self.zoom_to_fit_mode = "b"
            self.zoom_to_fit = True
            self.refresh()
        
        if event == "Horizontal":
            self.zoom_to_fit_mode = "h"
            self.zoom_to_fit = True
            self.refresh()
        
        if event == "Vertical":
            self.zoom_to_fit_mode = "v"
            self.zoom_to_fit = True
            self.refresh()

        if event == "Default":
            self.zoom_to_fit = False
            self.refresh()