from PIL import Image
from io import BytesIO

def pngify(data):
    inbuf = BytesIO(data)
    outbuf = BytesIO()
    im = Image.open(inbuf)
    im.save(outbuf, "png")
    im.close()
    return outbuf.getvalue()