#!/usr/bin/env python3
"""A homebrew CPS3 program as a MiSTer jtcps3 set: a zip holding the encrypted BIOS ROM (tools/mkcps3.py's) and an MRA
copied from jtcps3's Red Earth (Asia, NO CD) MRA: same header (region starts, Red Earth's keys), the BIOS from our
zip, the SIMM regions filled with FF, jtbeta.zip (the user's jtcps3 beta key) and the EEPROM defaults.
    mkmra3.py <mame_set_dir> <out_dir> [name] [title]
"""
import os
import sys
import zipfile

HEADER = '00 08 00 88 01 88 02 88 02 C8 02 C8 00 00 00 00 9E 30 0A B1 A1 75 B8 2C 04 01 00 00 00 00 00 00'
EEPROM = '''01 01 00 00 00 00 01 00 02 00 00 01 00 00 01 02
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
01 01 01 07 00 01 01 00 08 23 05 95 20 44 32 53
01 01 00 00 00 00 01 00 02 00 00 01 00 00 01 02
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
01 01 01 07 00 01 01 00 08 23 05 95 20 44 32 53
01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00'''
# SIMM 1 holds the program when the set has one (tools/mkcps3.py's simm1 files): loaded as jtcps3's Red Earth MRA
# loads it; otherwise every SIMM region is FF
SIMM1 = '''        <!-- simm1 0x800000: the program (0x06000000) -->
        <interleave output="32">
            <part name="simm1.1" map="0001"/>
            <part name="simm1.0" map="0010"/>
            <part name="simm1.3" map="0100"/>
            <part name="simm1.2" map="1000"/>
        </interleave>
        <!-- simm3-5: 0x2400000 bytes, unused -->
        <part repeat="0x2400000"> FF</part>'''
NO_SIMM = '''        <!-- simm1, simm3-5: 0x2C00000 bytes, unused -->
        <part repeat="0x2C00000"> FF</part>'''
MRA = '''<misterromdescription>
    <about author="gmcnaught" source="cps3-testgame (homebrew; MRA layout from jotego jtcps3 redearthn)"/>
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
    rd = os.path.join(src, 'redearthn')
    s1 = os.path.join(rd, 'redearth-simm1.0')
    simm1 = os.path.exists(s1) and open(s1, 'rb').read(16) != b'\xff' * 16
    with zipfile.ZipFile(os.path.join(out, name + '.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('bios.u2', open(os.path.join(rd, 'redearth_asia_nocd.29f400.u2'), 'rb').read())
        if simm1:
            for k in range(4):
                z.writestr(f'simm1.{k}', open(os.path.join(rd, f'redearth-simm1.{k}'), 'rb').read())
    open(os.path.join(out, title + '.mra'), 'w').write(MRA.format(title=title, name=name, header=HEADER,
                                                                  eeprom=EEPROM, simm=SIMM1 if simm1 else NO_SIMM))
    print('wrote', out)


if __name__ == '__main__':
    main()
