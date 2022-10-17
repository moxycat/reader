from PIL import Image
from io import BytesIO


def bulk_bluefilter(images, perc):
    def bluefilter(image, perc):
        im = Image.open(BytesIO(image)).convert("RGB")
        pixels = im.load()
        for y in range(im.height):
            for x in range(im.width):
                r, g, b = pixels[x, y]
                pixels[x, y] = (r, g, perc * b // 100)
        outbuf = BytesIO()
        im.save(outbuf, "png")
        return outbuf.getvalue()
    result = []
    for image in images:
        result.append(bluefilter(image, perc))
    return result
