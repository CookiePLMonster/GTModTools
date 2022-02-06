import sys
import struct
import os
from PIL import Image

if len(sys.argv) < 3:
    exit

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
            if bpp == 0:
                # 4bit, groups of 4 pixels
                image_width = width * 4
                rawmode = 'P;4'
                mode = 'P'

                # TODO: This needs to be moved
                fake_palette = image_data[-0x600:]

                # TODO: Is there a better way to do it in Pillow? Order of nibbles needs to be swapped
                image_data = bytes(map(lambda x: ((x & 0xF) << 4) | ((x >> 4) & 0xF), image_data))
            elif bpp == 1:
                # 8bit, groups of 2 pixels
                image_width = width * 2
                rawmode = 'P'
                mode = 'P'
            elif bpp == 2:
                # 16bit, each pixel separate
                image_width = width
                rawmode = 'RGB;15' # TODO: Alpha?
                mode = 'RGB'
            elif bpp == 3:
                # 24bit, 3-byte groups
                # TODO: Verify this
                image_width = (width * 3) / 2
                rawmode = 'RGB'
                mode = 'RGB'
            else:
                sys.exit(f'Unknown BPP value: {bpp}!')
            image_height = height
        
        rest_of_file = tim.read()
        
    if image_data:
        image = Image.frombytes(mode, (image_width, image_height), image_data, 'raw', rawmode)

        for pal in range(48):
            index = pal * 32
            clut_data = fake_palette[index : index + 32]

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