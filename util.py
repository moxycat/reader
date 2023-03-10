from PIL import Image, ImageOps
from io import BytesIO
import threading
import PySimpleGUI as sg
import unicodedata, re

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

cats = ["Reading", "Completed", "On-hold", "Dropped", "Plan to read"]
list2cat = {"books_cr": "Reading", "books_cmpl": "Completed", "books_idle": "On-hold", "books_drop": "Dropped", "books_ptr": "Plan to read"}
lists = ["Reading", "Completed", "On-hold", "Dropped", "Plan to read"]
tables = ["books_cr", "books_cmpl", "books_idle", "books_drop", "books_ptr"]

class BookList():
    READING = 1
    COMPLETED = 2
    ON_HOLD = 3
    DROPPED = 4
    PLAN_TO_READ = 5

class OrderBy():
    UPLOAD = 0,
    UPDATE = 1,
    TITLE = 2,
    SCORE = 3,
    CHAPTERS = 4,
    VOLUMES = 5,
    LEV = 6


DEFAULT_COVER = "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"

class ThreadThatReturns(threading.Thread):
    def __init__(self, group=None, target=None, name=None, args=(), kwargs={}, Verbose=None):
        threading.Thread.__init__(self, group, target, name, args, kwargs)
        self._return = None
    
    def run(self):
        print(type(self._target))
        if self._target is not None:
            self._return = self._target(*self._args, **self._kwargs)
    
    def join(self, *args):
        threading.Thread.join(self, *args)
        return self._return

# modded Tree class where right clicking on an element selects it before opening the right click menu
class TreeRtClick(sg.Tree):
    def _RightClickMenuCallback(self, event):
        tree = self.Widget
        item = tree.identify_row(event.y)
        tree.selection_set(item)
        super()._RightClickMenuCallback(event)
    
    def delete_selected(self):
        sel = self.Widget.selection()
        for item in sel:
            self.Widget.delete(item)

def popup_loading(text="Loading..."):
    return sg.Window("", layout=[
        [
            sg.Text(text, font=("Consolas", 14))
        ]
    ], modal=True, no_titlebar=True, finalize=True)

def pngify(data):
    try:
        inbuf = BytesIO(data)
        outbuf = BytesIO()
        im = Image.open(inbuf)
        im.save(outbuf, "png")
        im.close()
        return outbuf.getvalue()
    except: return None

def flatten(x):
    for e in x:
        if isinstance(e, list):
            yield from flatten(e)
        else:
            yield e


def slugify(value, allow_unicode=False):
    """
    Taken from https://github.com/django/django/blob/master/django/utils/text.py
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize("NFKC", value)
    else:
        value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-_")

def list_fsearch(l: list, f, first_only=False):
    result = []
    for x in l:
        if f(x):
            if first_only: return x
            result.append(x)
    return result


def outer_trim(data: bytes) -> bytes:
    """Try to remove superfluous whitespace around an image"""
    im = Image.open(BytesIO(data))
    im.load()
    im.convert("RGB")
    invim = ImageOps.invert(im)
    bbox = invim.getbbox()
    crop = im.crop(bbox)
    outbuf = BytesIO()
    crop.save(outbuf, "PNG")
    return outbuf.getvalue()

def uniq(values, key=None):
    return list(dict.fromkeys(values) if key is None else dict((key(value), value) for value in reversed(values)).values())

def sizeof_fmt(num, suffix="B"):
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"