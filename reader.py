import PySimpleGUI as sg
from io import BytesIO
from PIL import Image
from requests_html import HTMLSession
from threading import Thread
import imghdr

import mangakatana
import settings
import bluefilter

def popup_loading():
    return sg.Window("", layout=[
        [
            sg.Text("Loading...", font=("Consolas", 14))
        ]
    ], modal=True, no_titlebar=True, finalize=True)

class ThreadThatReturns(Thread):
    def __init__(self, group=None, target=None, name=None, args=(), kwargs={}, Verbose=None):
        Thread.__init__(self, group, target, name, args, kwargs)
        self._return = None
    
    def run(self):
        print(type(self._target))
        if self._target is not None:
            self._return = self._target(*self._args, **self._kwargs)
    
    def join(self, *args):
        Thread.join(self, *args)
        return self._return

class ReaderError(Exception): pass
class ReaderImageDownloadError(ReaderError): pass
class ReaderInfoError(ReaderError): pass

class Reader:
    window: sg.Window = None # window object
    popup_window: sg.Window = None # popup window object (for showing the loading popup)
    updated: bool = False # does this book get updated in the library
    images: list[bytes] = [] # array of each page's image data
    book_info: dict = {} # info about book
    chapter_index: int = 0 # current chapter's index
    max_chapter_index: int = 0 # ...
    max_page_index: int = 0 # ...
    page_index: int = 0 # current page's index
    vscroll: float = 0 # vertical scroll position
    hscroll: float = 0 # horizontal scroll position
    zoom_level: float = 1.0 # ...
    zoom_lock: bool = False

    def set_book_info(self, book_info: dict):
        self.book_info = book_info
        self.max_chapter_index = len(self.book_info["chapters"]) - 1

    def __init__(self, book_info: dict = {}):
        if book_info != {}: self.set_book_info(book_info)
        self.html_session = HTMLSession()
        self.html_session.browser

    # use perform_long_operation with this one or the UI will hang
    def set_chapter(self, chapter_index : int = -1, loop = None):
        if chapter_index != -1: self.chapter_index = chapter_index
        
        ttr = ThreadThatReturns(target=mangakatana.get_manga_chapter_images, args=(self.book_info["chapters"][self.chapter_index]["url"], self.html_session))
        ttr.start()
        image_urls = ttr.join()
        if None in image_urls: return False
        self.images = mangakatana.download_images(image_urls)
        if None in self.images: return False
        if int(settings.settings["reader"]["filter"]) > 0:
            self.images = bluefilter.bulk_bluefilter(self.images, int(settings.settings["reader"]["filter"]))
        self.max_page_index = len(self.images) - 1
        return True

    def check_if_mini(self, event):
        if self.window.TKroot.state() == "iconic":
            self.window.write_event_value("reader_mini", "")

    def mw_vscroll(self, ev):
        direction = int(-1 * (ev.delta / 120)) # 1 = down, -1 = up
        self.set_vscroll(direction * 0.05)
    
    def mw_hscroll(self, ev):
        direction = int(-1 * (ev.delta / 120)) # 1 = down, -1 = up
        self.set_hscroll(direction * 0.05)

    def zoom(self):
        im = Image.open(BytesIO(self.images[self.page_index]))

        im = im.resize((round(self.zoom_level * im.width), round(self.zoom_level * im.height)), resample=Image.BICUBIC)
        outbuf = BytesIO()
        im.save(outbuf, "png")
        self.refresh(outbuf.getvalue())

    def make_window(self):
        layout = [
            [sg.Menu([["&Tools", ["&Save screenshot"]]], key="reader_menu")],
            [sg.Column([
                [sg.Button("⌕+", key="reader_zoom_in", pad=0), sg.Text("x1.0", key="reader_zoom_level", pad=0), sg.Button("⌕-", key="reader_zoom_out", pad=0), sg.Text(), sg.Button("Cache next ch.", key="reader_cache")]
            ], key="reader_zoom_controls", element_justification="l", justification="l", vertical_alignment="l")],
            [sg.HSeparator()],
            [
                [
                    sg.Column([
                        [sg.Image(key="reader_page_img", enable_events=False, pad=0)]
                    ], size=(int(settings.settings["reader"]["w"]), int(settings.settings["reader"]["h"])), scrollable=True, key="reader_page_img_col", element_justification="c", justification="c", vertical_alignment="c")
                ],
                [sg.HSeparator()],
                [
                    sg.Button("prev ch.", key="reader_go_prev_ch"),
                    sg.Button("≪", key="reader_go_home"),
                    sg.Text(), sg.Text(),
                    sg.Button("<", key="reader_go_back"),
                    sg.Text("01/??", key="reader_page_num", enable_events=True),
                    sg.Button(">", key="reader_go_fwd"),
                    sg.Text(), sg.Text(),
                    sg.Button("≫", key="reader_go_end"),
                    sg.Button("next ch.", key="reader_go_next_ch")
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

        self.window["reader_page_img"].bind("<Button-1>", "_reader_go_back")
        self.window["reader_page_img"].bind("<Button-3>", "_reader_go_fwd")
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
        self.window["reader_go_prev_ch"].update(disabled=self.chapter_index == 0)
        self.window["reader_go_next_ch"].update(disabled=self.chapter_index == self.max_chapter_index)
        self.window["reader_go_back"].update(disabled=self.page_index == 0)
        self.window["reader_go_fwd"].update(disabled=self.page_index == self.max_page_index)
        self.window["reader_go_end"].update(disabled=self.page_index == self.max_page_index)
        self.window["reader_go_home"].update(disabled=self.page_index == 0)
        self.window["reader_page_img"].update(data=self.images[self.page_index])
        self.window["reader_zoom_level"].update("x" + str(self.zoom_level))
        self.window.refresh()
        self.window["reader_page_img_col"].contents_changed()
        self.window["reader_page_img_col"].Widget.canvas.yview_moveto(0.0)
        self.window["reader_page_img_col"].Widget.canvas.xview_moveto(0.0)
        im = Image.open(BytesIO(self.images[self.page_index]))
        print(im.width, im.height)
        self.window.TKroot.maxsize(im.width + 45, im.height + (105 if settings.settings["ui"]["theme"] == "Light" else 107))
        #self.window.TKroot.minsize((im.width + 45) // 2, (im.height + 70) // 2)
        im.close()

    def resized(self):
        print(self.window.TKroot.state())
        if self.window.TKroot.state() == "zoomed":
            self.window.normal()
        if self.window.TKroot.wm_state() == "iconic":
            self.window.hide()
        print(self.window.size)
        opts = {"width": self.window.size[0] - 45, "height": self.window.size[1] - (105 if settings.settings["ui"]["theme"] == "Light" else 107)}
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
    
    def set_hscroll(self, d):
        if self.hscroll + d >= 0 and self.hscroll + d <= 1.0:
            self.hscroll += d
            self.window["reader_page_img_col"].Widget.canvas.xview_moveto(self.hscroll)

    def set_vscroll(self, d):
        if self.vscroll + d >= 0 and self.vscroll + d <= 1.0:
            self.vscroll += d
            self.window["reader_page_img_col"].Widget.canvas.yview_moveto(self.vscroll)

    def next_chapter(self) -> None:
        if self.chapter_index + 1 > self.max_chapter_index: return
        self.chapter_index += 1
        self.popup_window = popup_loading()
        self.popup_window.read(timeout=0)
        self.window.perform_long_operation(lambda: self.set_chapter(self.chapter_index), "reader_loaded_chapter")
    
    def prev_chapter(self):
        if self.chapter_index - 1 < 0: return
        self.chapter_index -= 1
        self.popup_window = popup_loading()
        self.popup_window.read(timeout=0)
        self.window.perform_long_operation(lambda: self.set_chapter(self.chapter_index), "reader_loaded_chapter")

    def set_zoom(self, d):
        if self.zoom_level + d <= 0: return
        self.zoom_level += d
        self.zoom()

    def jump(self):
        layout = [
            [sg.Input(key="npage", size=(10, 1))],
            [sg.Button("Jump", key="jump"), sg.Button("Cancel", key="cancel")]
        ]
        w = sg.Window("Jump to page", layout, element_justification="c", modal=True)
        val = None
        while True:
            e, v = w.read()
            if e == "cancel" or e == sg.WIN_CLOSED: break
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
        if event == "reader_go_back" or event == "reader_page_img_reader_go_back": self.prev_page()
        if event == "reader_go_home" or event == "reader_page_img_reader_go_home": self.set_page(0)
        if event == "reader_go_end" or event == "reader_page_img_reader_go_end": self.set_page(self.max_page_index)
        if event == "reader_page_num": self.jump()
        if event == "reader_go_prev_ch": self.prev_chapter()
        if event == "reader_go_next_ch": self.next_chapter()
        if event == "reader_scroll_right": self.set_hscroll(0.05)
        if event == "reader_scroll_left": self.set_hscroll(-0.05)
        if event == "reader_scroll_down": self.set_vscroll(0.05)
        if event == "reader_scroll_up": self.set_vscroll(-0.05)
        if event == "reader_resized": self.resized()
        if event == "reader_loaded_chapter":
            self.popup_window.close()
            self.set_page(0)
            self.refresh()
        if event == "reader_zoom_in": self.set_zoom(0.25)
        if event == "reader_zoom_out": self.set_zoom(-0.25)
        if event == "reader_cache":
            pass