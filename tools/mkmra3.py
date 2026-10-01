#!/usr/bin/env python3
"""A homebrew CPS3 program as a MiSTer jtcps3 set: a zip holding the encrypted BIOS ROM and the SIMM chips (tools/mkcps3.py's
sfiii3na files) and an MRA copied from jtcps3's Street Fighter III 3rd Strike (Asia 990608, NO CD) MRA: the same
header (region starts: SIMM 1 0x80000, 3 0x880000, 4 0x1880000, 5 0x2880000, 2 0x3880000, 6 0x4080000; 3rd Strike's
keys), the same chip interleaves, jtbeta.zip (the user's jtcps3 beta key) and the EEPROM defaults.
    mkmra3.py <mame_set_dir> <out_dir> [name] [title]
"""
import os
import sys
import zipfile

HEADER = '00 08 00 88 01 88 02 88 03 88 04 08 00 00 00 00 A5 54 32 B4 0C 12 99 81 04 00 00 00 00 00 00 00'
EEPROM = '''01 01 00 00 00 00 01 00 02 00 00 01 00 00 01 02
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
01 01 01 07 00 01 01 00 08 23 05 95 20 44 32 53
01 01 00 00 00 00 01 00 02 00 00 01 00 00 01 02
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
01 01 01 07 00 01 01 00 08 23 05 95 20 44 32 53
01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00'''


def simm_parts():
    """the regions in the 3rd Strike MRA's order: 32-bit SIMMs 1 and 2 (4 chips), 16-bit pairs for SIMMs 3-6"""
    out = []
    for n in (1, 3, 4, 5, 2, 6):
        out.append(f'        <!-- simm{n} -->')
        if n in (1, 2):
            out.append('        <interleave output="32">')
            out += [f'            <part name="simm{n}.{k}" map="{m}"/>'
                    for k, m in ((1, '0001'), (0, '0010'), (3, '0100'), (2, '1000'))]
            out.append('        </interleave>')
        else:
            for j in range(4):
                out += ['        <interleave output="16">',
                        f'            <part name="simm{n}.{2 * j + 1}" map="01"/>',
                        f'            <part name="simm{n}.{2 * j}" map="10"/>',
                        '        </interleave>']
    return '\n'.join(out)


MRA = '''<misterromdescription>
    <about author="gmcnaught" source="cps3-testgame (homebrew; MRA layout from jotego jtcps3 sfiii3na)"/>
    <rotation>horizontal</rotation>
    <name>{title}</name>
    <setname>{name}</setname>
    <year>2026</year>
    <manufacturer>homebrew</manufacturer>
    <players>2</players>
    <rbf>jtcps3</rbf>
    <joystick>8</joystick>
    <rom index="0" zip="{name}.zip" md5="None" address="0x30000000">
        <part>{header}</part>
        <!-- bios 0x80000 (encrypted with the header's keys) -->
        <part name="bios.u2"/>
{simm}
    </rom>
    <rom index="17" zip="jtbeta.zip" md5="None">
        <part name="beta.bin" crc="8b6976d8"/>
    </rom>
    <rom index="2">
        <part>
{eeprom}
</part>
    </rom>
    <nvram index="2" size="128"/>
    <rom index="1">
        <part>00 80</part>
    </rom>
    <buttons names="A,B,C,D,E,F,Start,Coin,Core credits" default="A,B,X,Y,L,R,Start,Select,-" count="6"/>
</misterromdescription>
'''


def main():
    src, out = sys.argv[1], sys.argv[2]
    name = sys.argv[3] if len(sys.argv) > 3 else 'cps3test'
    title = sys.argv[4] if len(sys.argv) > 4 else 'CPS3 test game'
    os.makedirs(out, exist_ok=True)
    rd = os.path.join(src, 'sfiii3na')
    with zipfile.ZipFile(os.path.join(out, name + '.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('bios.u2', open(os.path.join(rd, 'sfiii3_asia_nocd.29f400.u2'), 'rb').read())
        for f in sorted(os.listdir(rd)):
            if f.startswith('sfiii3-simm'):
                z.writestr(f[len('sfiii3-'):], open(os.path.join(rd, f), 'rb').read())
    open(os.path.join(out, title + '.mra'), 'w').write(MRA.format(title=title, name=name, header=HEADER,
                                                                  eeprom=EEPROM, simm=simm_parts()))
    print('wrote', out)


if __name__ == '__main__':
    main()
