import PySimpleGUI as sg
from io import BytesIO
from PIL import Image
import mangakatana

def popup_loading():
    return sg.Window("", layout=[
        [
            sg.Text("Loading...")
        ]
    ], modal=True, no_titlebar=True, finalize=True)

class ReaderError(Exception): pass
class ReaderImageDownloadError(ReaderError): pass
class ReaderInfoError(ReaderError): pass

class Reader:
    window = None
    popup_window = None
    images = []
    book_info = {}
    chapter_index = 0
    max_chapter_index = 0
    max_page_index = 0
    page_index = 0
    current_image = None
    vscroll = 0
    hscroll = 0

    def set_book_info(self, book_info: dict):
        self.book_info = book_info
        self.max_chapter_index = len(self.book_info["chapters"]) - 1

    def __init__(self, book_info: dict = {}):
        if book_info != {}: self.set_book_info(book_info)

    # use perform_long_operation with this one or the UI will hang
    def set_chapter(self, chapter_index : int = -1):
        if chapter_index != -1: self.chapter_index = chapter_index
        image_urls = mangakatana.get_manga_chapter_images(self.book_info["chapters"][self.chapter_index]["url"])
        self.images = mangakatana.download_images(image_urls)
        self.max_page_index = len(self.images) - 1

    def make_window(self):
        layout = [
            [sg.Menu([["&Tools", ["&Save screenshot", "&Maximize window", "&Exit"]]], key="reader_menu")],
            [
                [
                    sg.Column([
                        [sg.Image(key="reader_page_img", enable_events=True, pad=0)]
                    ], size=(800, 600), scrollable=True, key="reader_page_img_col")
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
        self.window.bind("<Right>", "reader_scroll_right")
        self.window.bind("<Left>", "reader_scroll_left")
        self.window.bind("<Down>", "reader_scroll_down")
        self.window.bind("<Up>", "reader_scroll_up")
        self.window.bind("<Configure>", "reader_resized")
    
    def refresh(self) -> None:
        self.hscroll = 0
        self.vscroll = 0
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
        self.window.refresh()
        self.window["reader_page_img_col"].contents_changed()
        self.window["reader_page_img_col"].Widget.canvas.yview_moveto(0.0)
        self.window["reader_page_img_col"].Widget.canvas.xview_moveto(0.0)
        im = Image.open(BytesIO(self.images[self.page_index]))
        self.window.TKroot.maxsize(im.width + 45, im.height + 70)
        #self.window.TKroot.minsize((im.width + 45) // 2, (im.height + 70) // 2)
        im.close()

    def resized(self):
        print(self.window.size)
        opts = {"width": self.window.size[0] - 45, "height": self.window.size[1] - 70}
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
        if event == "reader_go_fwd": self.next_page()
        if event == "reader_go_back": self.prev_page()
        if event == "reader_go_home": self.set_page(0)
        if event == "reader_go_end": self.set_page(self.max_chapter_index)
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
"""
sg.theme("Default1")
sg.set_options(font=("Consolas", 10))

info = mangakatana.get_manga_info("https://mangakatana.com/manga/komi-san-wa-komyushou-desu.1921")
rdr = Reader(info)
rdr.set_chapter(375)
rdr.make_window()
rdr.set_page(0)
while True:
    e, v = rdr.window.read()
    print(e)
    if e == None: break
    rdr.handle(e)
"""