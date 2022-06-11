import sys
import struct
import os
from PIL import Image
from array import array
from collections import namedtuple
import rectpack
import configparser
import json

if len(sys.argv) < 3:
    exit()

def swapNibble(arr):
    return bytes(map(lambda x: ((x & 0xF) << 4) | ((x >> 4) & 0xF), arr))

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

def convert8to5(c):
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

def RGBA8888to5551(color):
    # Convert to 5551 with transparency bit awareness, using our logic
    alpha = (color >> 24) & 0xFF
    if alpha < MIN_ALPHA_THRESHOLD:
        # Fully transparent
        return 0
    
    r = convert8to5(color & 0xFF)
    g = convert8to5((color >> 8) & 0xFF)
    b = convert8to5((color >> 16) & 0xFF)

    has_transparency = alpha <= MAX_ALPHA_THRESHOLD
    return r | (g << 5) | (b << 10) | (has_transparency << 15)

def Palette5551to8888(palette):
    src_view = memoryview(palette).cast('H')

    dst = array('I')
    for color in src_view:
        dst.append(RGBA5551to8888(color))

    return dst.tobytes()

def Palette8888to5551(palette):
    src_view = memoryview(palette).cast('I')
    dst = array('H')
    for color in src_view:
        dst.append(RGBA8888to5551(color))

    return dst.tobytes()

mode = sys.argv[1].lower()
if mode == 'unpack':

    image_data = None
    clut_data = None

    with open(sys.argv[2], 'rb') as tim:
        tag, version = struct.unpack('<BB2x', tim.read(4))
        if tag == 0x10:
            if version != 0:
                sys.exit(f'Unknown TIM file version {version}!')
            
            flags = struct.unpack('<B3x', tim.read(4))[0]
            bpp = flags & 3
            clp = (flags & 8) != 0

            if clp:
                # Parse CLUT
                length, x, y, width, height = struct.unpack('<IHHHH', tim.read(12))
                clut_data = tim.read(length - 12)
            
            # Parse image
            length, x, y, width, height = struct.unpack('<IHHHH', tim.read(12))
            image_data = tim.read(length - 12)
            
            stride = width * 2
            image_width = width * 4
            image_height = height
    
    dir_name = os.path.splitext(sys.argv[2])[0]
    with open(os.path.join(dir_name, 'definitions.bin'), 'rb') as defs:
        definitions = defs.read()
        
    if image_data:
        # TODO: Configurable
        BASE_PAGE_INDEX = 12

        image = Image.frombytes('P', (image_width, image_height), swapNibble(image_data), 'raw', 'P;4')

        config = configparser.ConfigParser(allow_no_value=True)
        config['Settings'] = {'Texpage' : BASE_PAGE_INDEX, 'Num_W_Texpages' : (image_width + 255) // 256, 'Num_H_Texpages' : (image_height + 255) // 256}
        config['Files'] = {}

        # Unpack all textures from the atlas
        index = 1
        for offset in range(0, len(definitions), 12):
            x, y, palette, width, height, page_index = struct.unpack_from('<BBHHHH2x', definitions, offset)
            x += (page_index - BASE_PAGE_INDEX) * 256
            part = image.crop((x, y, x + width, y + height))

            pal_x, pal_y = unpackClutAttr(palette)

            clut_offset = ((pal_x - (BASE_PAGE_INDEX * 64)) * 2) + (pal_y * stride)
            clut = bytearray(image_data[clut_offset:clut_offset+32])

            filename = f'tex_{index}.png'
            part.putpalette(Palette5551to8888(clut), 'RGBA')
            part.convert('RGBA').save(os.path.join(dir_name, filename))

            config['Files'][filename] = None

            index += 1
        
        with open(os.path.join(dir_name, 'files.ini'), 'w') as f:
            config.write(f)

elif mode == 'pack':
    config = configparser.ConfigParser(allow_no_value=True)
    config.read(sys.argv[2])
    dir_name = os.path.dirname(sys.argv[2])

    texpage = int(config['Settings']['Texpage'])
    texpage_sizes = (
        int(config['Settings']['Num_W_Texpages']),
        int(config['Settings']['Num_H_Texpages'])
    )
    files = list(config['Files'].keys())
    
    # Get dimensions of all images
    dimensions = []
    for file in files:
        with Image.open(os.path.join(dir_name, file)) as im:
            dimensions.append((*im.size, file))
    
    texture_size = tuple(i * 256 for i in texpage_sizes)
    
    palette_bytes = len(dimensions) * 32
    palette_pixels = palette_bytes * 2

    palette_lines = ((palette_pixels + texture_size[0] - 1) // texture_size[0])
    
    # We set separate bins per texpage, but they must leave enough space for palette lines
    bin_size = (256, 256 - palette_lines)
    packer = rectpack.newPacker(rotation=False)
    packer.add_bin(*bin_size, count=texpage_sizes[0] * texpage_sizes[1])
    
    for rect in dimensions:
        packer.add_rect(*rect)
    
    packer.pack()

    # Get the height of the pile, it'll serve as the hint as to how many lines the resulting image should have
    used_height = 0
    for _, _, y, _, h, _ in packer.rect_list():
        used_height = max(used_height, y + h)
    
    # Data roughly matching ingame atlas definitions, with palette and filename embedded for ease of use
    AtlasEntryDef = namedtuple('AtlasEntryDef', ['x', 'y', 'w', 'h', 'texpage', 'palette', 'filename'])

    atlas_entries = []  
    image = Image.new('P', (texture_size[0], used_height))
    preview_image = Image.new('RGBA', image.size)
    # Composite the image
    for b, x, y, w, h, rid in packer.rect_list():

        with Image.open(os.path.join(dir_name, rid)).convert('RGBA') as org_im:
            # Warn if the image has too many colors
            if org_im.getcolors(maxcolors=16) is None:
                print(f'WARNING: {rid} has more than 16 unique colors! The image will be quantized down to 16 colors when packing, but quality may suffer.')

            area = (256 * b + x, y)
            im = org_im.quantize(colors=16)
            image.paste(im, area)
            preview_image.paste(org_im, area)
            atlas_entries.append(AtlasEntryDef(x, y, w, h, texpage + b, im.palette.getdata()[1], rid))
    
    preview_image.save(dir_name + '.png')
    with open(dir_name + '.tim', 'wb') as f:
        f.write(struct.pack('<BB2xB3x', 0x10, 0, 0)) # Tag, version, format

        x = 0
        y = 0
        tim_width = texture_size[0] // 4 # Width in halfwords
        tim_height = used_height + palette_lines
        image_size = ((2 * tim_width) * tim_height) + 12

        f.write(struct.pack('<IHHHH', image_size, x, y, tim_width, tim_height))

        # Write image data
        f.write(swapNibble(image.tobytes('raw', 'P;4')))

        # Write palettes
        palette_section_size = palette_lines * (2 * tim_width) # Size in bytes
        palettes = bytearray()
        for entry in atlas_entries:
            palettes.extend(Palette8888to5551(entry.palette))
        f.write(palettes.ljust(palette_section_size, b'\0'))
    
    # Dump atlas definitions
    with open(os.path.join(dir_name, 'definitions.json'), 'r') as f:
        definitions_file = json.load(f)

    atlas = {}
    pal_x = 0
    pal_y = used_height
    for entry in atlas_entries:
        fn = entry.filename
        atlas[entry.filename] = {
            'x' : entry.x, 'y' : entry.y,
            'palette' : packClutAttr(pal_x + (64 * texpage), pal_y),
            'width' : entry.w, 'height' : entry.h,
            'texture_page' : entry.texpage
        }

        pal_x += 16
        if pal_x >= tim_width:
            pal_x = 0
            pal_y += 1
    
    definitions_file['textures'] = atlas
    with open(os.path.join(dir_name, 'definitions.json'), 'w') as f:
        json.dump(definitions_file, f, sort_keys=True, indent=2)
