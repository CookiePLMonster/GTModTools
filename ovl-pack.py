import sys
import struct

if len(sys.argv) < 2:
    exit

with open(sys.argv[1], 'rb') as f:
    header_size = struct.unpack('I', f.read(4))[0]
    f.seek(0)

    files = []
    current_offset = 0
    while current_offset < header_size:
        files.append(struct.unpack('II', f.read(8)))
        current_offset += 8
    
    file_num = 1
    for zipped_file in files:
        with open(f'gt2_{file_num:02}.exe.gz', 'wb') as exe:
            f.seek(zipped_file[0])
            exe.write(f.read(zipped_file[1]))
        file_num += 1