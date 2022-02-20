import struct
import mmap
import os

class PSEXE:
    def __init__(self, filename, readonly=True, *, headless=False, baseAddress=None):
        self.readonly = readonly
        self.filename = filename
        if not headless:
            with open(filename, "rb") as f:
                with mmap.mmap(f.fileno(), 0x800, None, mmap.ACCESS_READ) as header:
                    fileSize = os.path.getsize(filename)
                    if header[:8] == b'PS-X EXE' and (struct.unpack_from('<I', header, 0x1C)[0] + 0x800) <= fileSize:
                        self.loadAddress = struct.unpack_from('<I', header, 0x18)[0] - 0x800
                        return
        elif baseAddress is not None:
            self.loadAddress = baseAddress
            return

        raise ValueError()

    def __enter__(self):
        with open(self.filename, "rb" if self.readonly else "r+b") as f:
            self.map = mmap.mmap(f.fileno(), 0, None, mmap.ACCESS_READ if self.readonly else mmap.ACCESS_WRITE)
            return self

    def __exit__(self, *args):
        if not self.readonly:
            self.map.flush()
        self.map.close()

    def addr(self, vaddr):
        return vaddr - self.loadAddress

    def vaddr(self, addr):
        return addr + self.loadAddress

    def readS16(self, vaddr):
        addr = self.addr(vaddr)
        return struct.unpack_from('<h', self.map, addr)[0]

    def readU16(self, vaddr):
        addr = self.addr(vaddr)
        return struct.unpack_from('<H', self.map, addr)[0]

    def readU32(self, vaddr):
        addr = self.addr(vaddr)
        return struct.unpack_from('<I', self.map, addr)[0]

    def readString(self, vaddr, encoding='utf-8'):
        addr = self.addr(vaddr)
        return self.map[addr:].split(b'\x00', 1)[0].decode(encoding)

    def readAddress(self, vaddr):
        return self.readU32(vaddr)

    def readIndirectPtr(self, high, low):
        return (self.readU16(high) << 16) + self.readS16(low)

    def writeS16(self, vaddr, val):
        addr = self.addr(vaddr)
        struct.pack_into('<h', self.map, addr, val)

    def writeU16(self, vaddr, val):
        addr = self.addr(vaddr)
        struct.pack_into('<H', self.map, addr, val)

    def writeU32(self, vaddr, val):
        addr = self.addr(vaddr)
        struct.pack_into('<I', self.map, addr, val)

    def writeString(self, vaddr, str, encoding='utf-8'):
        addr = self.addr(vaddr)
        b = str.encode(encoding)
        l = len(b)
        self.map[addr : addr+l] = b
        self.map[addr + l] = 0

    def writeAddress(self, vaddr, val):
        self.writeU32(vaddr, val)

    def writeIndirectRef(self, vhigh, vlow, val):
        def sign_extend(value, bits):
            sign_bit = 1 << (bits - 1)
            return (value & (sign_bit - 1)) - (value & sign_bit)

        low = sign_extend(val & 0xffff, 16)
        high = (val - low) >> 16
        self.writeS16(vlow, low)
        self.writeU16(vhigh, high)
