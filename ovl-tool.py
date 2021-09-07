import sys
import struct
import gzip

if len(sys.argv) < 3:
    exit

mode = sys.argv[1].lower()
if mode == 'unpack':
    with open(sys.argv[2], 'rb') as ovl:
        header_size = struct.unpack('I', ovl.read(4))[0]
        ovl.seek(0)

        files = []
        current_offset = 0
        while current_offset < header_size:
            files.append(struct.unpack('II', ovl.read(8)))
            current_offset += 8
        
        file_num = 1
        for zipped_file in files:
            with open(f'gt2_{file_num:02}.exe', 'wb') as exe:
                ovl.seek(zipped_file[0])
                exe.write(gzip.decompress(ovl.read(zipped_file[1])))
            file_num += 1
elif mode == 'pack':
    with open('GT2.OVL', 'wb') as ovl:
        files = sys.argv[2:]
        header_bytes = bytearray()

        current_offset = 8 * len(files)
        ovl.seek(current_offset)
        for file in files:
            with open(file, 'rb') as exe:
                compressed_file = gzip.compress(exe.read())
                header_bytes.extend(struct.pack('II', current_offset, len(compressed_file)))
                current_offset += len(compressed_file)
                ovl.write(compressed_file)
        
        ovl.seek(0)
        ovl.write(header_bytes)
