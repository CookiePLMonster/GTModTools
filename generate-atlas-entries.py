import json
import sys
import struct
import os

if len(sys.argv) < 2:
    exit()

with open(sys.argv[1], 'r') as f:
    definitions_file = json.load(f)
    entries = definitions_file['entries']
    atlas = definitions_file['textures']

dir_name = os.path.dirname(sys.argv[1])
for lang, lang_entries in entries.items():
    with open(os.path.join(dir_name, lang + '.bin'), 'wb') as f:
        for entry in lang_entries:
            tex_def = atlas[entry]
            f.write(struct.pack('BBHHHH0l', tex_def['x'], tex_def['y'], tex_def['palette'], tex_def['width'], tex_def['height'], tex_def['texture_page']))
