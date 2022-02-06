import sys
import struct
import os
from PIL import Image

if len(sys.argv) < 3:
    exit

mode = sys.argv[1].lower()
if mode == 'unpack':
    clut_data = None
    image_data = None
    image_width = 0
    image_height = 0

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
            length, x, y, image_width, image_height = struct.unpack('IHHHH', tim.read(12))
            image_data = tim.read(length - 12)
        
    if image_data:
        image = Image.frombytes('P', (image_width * 2, image_height), image_data, 'raw', 'P')
        # TODO: This should probably be RGBA;15 to preserve alpha, see
        # https://github.com/python-pillow/Pillow/issues/6027
        image.putpalette(clut_data, 'RGB;15')

        name = os.path.splitext(sys.argv[2])[0]
        image.save(name + '.png')