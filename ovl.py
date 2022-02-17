import struct
import gzip
import os

def unpack(file, output_dir='.'):
    with open(file, 'rb') as ovl:
        files = []
        current_offset = 0

        # Simulated do...while
        do = True
        while do:
            files.append(struct.unpack('II', ovl.read(8)))
            current_offset += 8
            do = current_offset < files[0][0]
     
        os.makedirs(output_dir, exist_ok=True)

        file_num = 1
        for cur_file in files:
            with open(os.path.join(output_dir, f'gt2_{file_num:02}.exe'), 'wb') as exe:
                ovl.seek(cur_file[0])
                exe.write(gzip.decompress(ovl.read(cur_file[1])))
            file_num += 1

def pack(files, output_file='GT2.OVL'):
    with open(output_file, 'wb') as ovl:
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

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="A script to unpack and repack Gran Turismo 2's OVL file.")
    subparsers = parser.add_subparsers(required=True, help='sub-command')

    parser_unpack = subparsers.add_parser('unpack', help='Unpack individual code overlays from the OVL')
    parser_unpack.add_argument('file', metavar='OVL', type=str, help='name of the OVL file')
    parser_unpack.add_argument('-o', '--output-dir', dest='output_dir', type=str, default='.', help='path to the output directory')
    parser_unpack.set_defaults(func=unpack)

    parser_pack = subparsers.add_parser('pack', help='Pack code overlays to an OVL')
    parser_pack.add_argument('files', nargs='+', help='files to pack')
    parser_pack.add_argument('-o', '--output-file', dest='output_file', type=str, default='GT2.OVL', help='name of the output file (default: %(default)s)')
    parser_pack.set_defaults(func=pack)

    args = parser.parse_args()

    func = args.func
    args_var = vars(args)
    del args_var['func']

    func(**args_var)