import sys
import struct
import os
from PIL import Image
from array import array

if len(sys.argv) < 3:
    exit

def swapNibble(arr):
    return bytes(map(lambda x: ((x & 0xF) << 4) | ((x >> 4) & 0xF), arr))

BASE_PAGE_INDEX = 12

def packClutAttr(x, y):
    return (y & 0x1FF) << 6 | ((x // 16) & 0x3F)

def unpackClutAttr(attr):
    x = (attr & 0x3F) * 16
    y = (attr >> 6) & 0x1FF
    return x, y

# Taken from DuckStation:
# https://github.com/stenzek/duckstation/blob/master/src/core/gpu_types.h#L118-L142
def convert5to8(c):
    return ((c * 527) + 23) >> 6

def convert8to8(c):
    return ((c * 249) + 1014) >> 11

MIN_ALPHA_THRESHOLD = 0x20 # Below this alpha, pixel is fully transparent
MAX_ALPHA_THRESHOLD = 0xE0 # Above this alpha, pixel has transparency bit cleared

def RGBA5551to8888(color):
    # Convert to 8888 with transparency bit awareness
    # For pure black, set to transparent if transparency bit is clear
    # For other colors, transparency bit sets alpha to 128, else 255
    r = convert5to8(color & 31)
    g = convert5to8((color >> 5) & 31)
    b = convert5to8((color >> 10) & 31)
    is_black = r == 0 and g == 0 and b == 0
    if (color >> 15) != 0:
        # Transparency bit set
        a = 255 if is_black else 128
    else:
        # Transparency bit clear
        a = 0 if is_black else 255
    return r | (g << 8) | (b << 16) | (a << 24)


def Palete5551to8888(palette):
    src_view = memoryview(palette).cast('H')

    dst = array('I')
    for color in src_view:
        dst.append(RGBA5551to8888(color))

    return dst.tobytes()

mode = sys.argv[1].lower()
if mode == 'unpack':
    image_data = None
    clut_data = None

    with open(sys.argv[2], 'rb') as tim:
        tag, version = struct.unpack('BB2x', tim.read(4))
        if tag == 0x10:
            if version != 0:
                sys.exit(f'Unknown TIM file version {version}!')
            
            flags = struct.unpack('B3x', tim.read(4))[0]
            bpp = flags & 3
            clp = (flags & 8) != 0

            if clp:
                # Parse CLUT
                length, x, y, width, height = struct.unpack('IHHHH', tim.read(12))
                clut_data = tim.read(length - 12)
            
            # Parse image
            length, x, y, width, height = struct.unpack('IHHHH', tim.read(12))
            image_data = tim.read(length - 12)
            
            stride = width * 2
            image_width = width * 4
            image_height = height
    
    dirName = os.path.splitext(sys.argv[2])[0]
    with open(os.path.join(dirName, 'definitions'), 'rb') as defs:
        definitions = defs.read()
        
    if image_data:
        image = Image.frombytes('P', (image_width, image_height), swapNibble(image_data), 'raw', 'P;4')

        # Unpack all textures from the atlas
        index = 1
        for offset in range(0, len(definitions), 12):
            x, y, palette, width, height, page_index = struct.unpack_from('BBHHHH2x', definitions, offset)
            x += (page_index - BASE_PAGE_INDEX) * 256
            part = image.crop((x, y, x + width, y + height))

            pal_x, pal_y = unpackClutAttr(palette)

            clut_offset = ((pal_x - (BASE_PAGE_INDEX * 64)) * 2) + (pal_y * stride)
            clut = bytearray(image_data[clut_offset:clut_offset+32])

            part.putpalette(Palete5551to8888(clut), 'RGBA')
            part.save(os.path.join(dirName, f'tex_{index}.png'))

            index += 1

        for pal in range(48):
            index = pal * 32
            clut_data = image_data[index : index + 32]

        #clut_data = bytearray([0x07, 0xA5, 0x27, 0xA5, 0x28, 0xA5, 0x28, 0xA5, 0x28, 0xA9, 0xE6, 0x9C, 0x63, 0x8C, 0xE6, 0x9C, 0xA4, 0x94, 0xA4, 0x94,
        #0xA5, 0x98, 0xC5, 0x98, 0x00, 0x00, 0x21, 0x84, 0x00, 0x00, 0x00, 0x00])
            if clut_data:
                # TODO: This should probably be RGBA;15 to preserve alpha, see
                # https://github.com/python-pillow/Pillow/issues/6027
                image.putpalette(clut_data, 'RGB;15')
            else:
                # Fallback palette
                image.putpalette(Image.ADAPTIVE)

            name = os.path.splitext(sys.argv[2])[0]
            image.save(name + '_' + str(pal + 1) + '.png')