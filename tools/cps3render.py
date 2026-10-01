#!/usr/bin/env python3
"""Re-render a CPS3 frame from a scripts/lua/cps3_vlog.lua dump, following MAME 0.289's cps3_state::screen_update
(MAME src/mame/capcom/cps3.cpp), and compare it with MAME's snapshot. Checks the decoding of the sprite list, the
tilemap entries, character RAM and colour RAM written in docs/CPS3.md.

    cps3render.py <dump prefix> [snapshot.png] [-o out.png] [--list]

Not covered: sprite zoom gaps (MAME's rounding is followed),
screen flip.
"""
import argparse
import struct
import sys

from PIL import Image

W, H = 384, 224


def be32(path):
    d = open(path, 'rb').read()
    return list(struct.unpack(f'>{len(d) // 4}I', d))


def load(prefix):
    D = {}
    D['spr'] = be32(prefix + '.spriteram')  # live sprite RAM: tilemap data and line scroll are read from it
    # the sprite list as copied by the sprite-list DMA, and the global scrolls buffered with it
    D['list'] = be32(prefix + '.spritelist')
    D['gscroll'] = be32(prefix + '.gscrollbuf')
    D['tmap'] = be32(prefix + '.tmap')
    D['crtc'] = be32(prefix + '.crtc')
    c = open(prefix + '.colour', 'rb').read()
    D['colour'] = struct.unpack(f'>{len(c) // 2}H', c)
    D['char'] = open(prefix + '.charram', 'rb').read()
    # SS RAM as the 0x05040000 window shows it: bits 16-23 and 0-7 of each word are SS RAM bytes 2k and 2k + 1
    D['ss'] = bytes(b for v in be32(prefix + '.ssram') for b in ((v >> 16) & 0xff, v & 0xff))
    D['ssregs'] = open(prefix + '.ssregs', 'rb').read()
    return D


def fg_layer(D, img):
    """draw_fg_layer: the SS text layer, 64x32 8x8 4-bit tiles from SS RAM 0x4000, over the scaled frame."""
    ss, r, col = D['ss'], D['ssregs'], D['colour']
    vscroll = r[0x10] | (r[0x11] << 8)
    scrolly = (-vscroll) & 0x100
    palbase = r[0x12]
    px = img.load()
    for line in range(H):
        y = line // 8
        offset = ((line + scrolly) // 8 * 128) & 0x1fff
        rowscroll = ss[((line + scrolly - 1) & 0x1ff) * 2 + 0x2000]
        for x in range(64):
            data = ss[offset] | (ss[offset + 1] << 8)
            tile = data & 0x1ff
            pal = ((data >> 9) & 0x1f) + (palbase << 5)
            fy = (data >> 14) & 1
            fx = (data >> 15) & 1
            offset += 2
            row = (7 - (line - y * 8)) if fy else line - y * 8
            t = 0x4000 + tile * 32 + row * 4
            for sx in (x * 8 - rowscroll, 512 + x * 8 - rowscroll):
                for i in range(8):
                    X = sx + i
                    if not 0 <= X < W:
                        continue
                    p = 7 - i if fx else i
                    b = ss[t + p // 2]
                    c = (b >> 4) if p & 1 else (b & 0xf)
                    if c:
                        v = col[(pal * 16 + c) & 0x1ffff]
                        px[X, line] = ((v & 0x1f) << 3, ((v >> 5) & 0x1f) << 3, ((v >> 10) & 0x1f) << 3)


def tile_pixels(char, tileno):
    """16x16 8-bit tile: cps3_tiles16x16_layout, x offsets 3,2,1,0,7,6,5,4,... bytes, 16 bytes a row."""
    b = (tileno & 0x7fff) * 256
    return [[char[b + r * 16 + (x ^ 3)] for x in range(16)] for r in range(16)]


def drawgfxzoom(buf, clip, char, code, color, gran, flipx, flipy, sx, sy, scalex, scaley, blend):
    """cps3_drawgfxzoom with CPS3_TRANSPARENCY_PEN_INDEX(_BLEND), pen 0 transparent; buf holds colour indices."""
    if not scalex or not scaley:
        return
    palbase = (gran * color) & 0x1ffff
    src = tile_pixels(char, code)
    sh = (scaley * 16 + 0x8000) >> 16
    sw = (scalex * 16 + 0x8000) >> 16
    if not sw or not sh:
        return
    dx = (16 << 16) // sw
    dy = (16 << 16) // sh
    ex, ey = sx + sw, sy + sh
    xib = (sw - 1) * dx if flipx else 0
    if flipx:
        dx = -dx
    yi = (sh - 1) * dy if flipy else 0
    if flipy:
        dy = -dy
    x0, y0, x1, y1 = clip
    if sx < x0:
        xib += (x0 - sx) * dx
        sx = x0
    if sy < y0:
        yi += (y0 - sy) * dy
        sy = y0
    ex = min(ex, x1 + 1)
    ey = min(ey, y1 + 1)
    if ex <= sx:
        return
    for y in range(sy, ey):
        row = src[yi >> 16]
        xi = xib
        for x in range(sx, ex):
            c = row[xi >> 16]
            if c:
                if not blend:
                    buf[y][x] = c | palbase
                elif gran == 64:
                    buf[y][x] |= (c & 0xf) << 13
                else:
                    buf[y][x] |= ((c & 1) << 15) | ((color & 1) << 16)
            xi += dx
        yi += dy


def tilemap_line(D, buf, regs, drawline, clip):
    spr, char = D['spr'], D['char']
    if not regs[1] & 0x8000:
        return
    scrollx = (regs[0] >> 16) & 0xffff
    scrolly = regs[0] & 0xffff
    linescroll = regs[1] & 0x4000
    fx = (regs[1] >> 11) & 1
    fy = (regs[1] >> 10) & 1
    linebase = ((regs[2] >> 24) & 0x7f) << 10
    mapbase = ((regs[2] >> 16) & 0x7f) << 10
    scrolly += 4
    line = (drawline + scrolly) & 0x3ff
    if fy:
        line ^= 0x3ff
    xmask = 0x3f if fx else 0
    tileline = line // 16 + 1
    sub = line % 16
    if linescroll:
        scrollx += (spr[linebase + ((line + 16) & 0x3ff)] >> 16) & 0x3ff
    lclip = (clip[0], drawline, clip[2], drawline)
    for x in range(clip[0] // 16, clip[2] // 16 + 2):
        dat = spr[mapbase + (tileline & 63) * 64 + (((x + scrollx // 16) & 63) ^ xmask)]
        tileno = (dat >> 17) & 0x7fff
        xflip = ((dat >> 12) & 1) ^ (xmask & 1)
        yflip = (dat >> 11) & 1
        alpha = (dat >> 10) & 1
        bpp = (dat >> 9) & 1
        colour = dat & 0x1ff
        drawgfxzoom(buf, lclip, char, tileno, colour, 64 if bpp else 256, xflip, yflip,
                    x * 16 - scrollx % 16, drawline - sub, 0x10000, 0x10000, alpha)


def render(D, listing=False):
    spr, char, crtc = D['list'], D['char'], D['crtc']
    # full-screen zoom: the list is drawn into a render buffer of up to 1024x448, then scaled to the screen
    zx, zy = min(crtc[3] & 0xff, 0x80), min(crtc[7] & 0xff, 0x80)
    fszx, fszy = (zx << 16) // 0x40, (zy << 16) // 0x40
    buf = [[0] * (2 * 512) for _ in range(2 * 224)]
    if zx == 0x40 and zy == 0x40:
        clip = (0, 0, W - 1, H - 1)
    else:
        clip = (0, 0, ((W * fszx + 0x8000) >> 16) - 1, ((H * fszy + 0x8000) >> 16) - 1)
    tilestable = [8, 1, 2, 4]
    for i in range(0, 0x2000 // 4, 4):
        e0, e1, e2 = spr[i], spr[i + 1], spr[i + 2]
        if e0 & 0x80000000:
            break
        gs = (e0 >> 28) & 7
        length = (e0 >> 16) & 0x1ff
        start = ((e0 >> 4) & 0x7ff) * 0x100 >> 2
        xpos = (e1 >> 16) & 0x3ff
        ypos = e1 & 0x3ff
        whichbpp = (e2 >> 30) & 1
        whichpal = (e2 >> 29) & 1
        gfx_ = (e2 >> 28) & 1
        gfy = (e2 >> 27) & 1
        galpha = (e2 >> 26) & 1
        gbpp = (e2 >> 25) & 1
        gpal = (e2 >> 16) & 0x1ff
        gsx = (D['gscroll'][gs] >> 16) & 0x3ff
        gsy = D['gscroll'][gs] & 0x3ff
        if listing:
            print(f'main {i // 4:3d}: {e0:08x} {e1:08x} {e2:08x} {spr[i + 3]:08x}  gscroll {gs} ({gsx},{gsy}) '
                  f'len {length} sub@{start * 4:#07x} pos ({xpos},{ypos})')
        for j in range(0, length * 4, 4):
            v1, v2, v3 = spr[start + j], spr[start + j + 1], spr[start + j + 2]
            tileno = (v1 >> 17) & 0x7fff
            flipx = (v1 >> 12) & 1
            flipy = (v1 >> 11) & 1
            alpha = (v1 >> 10) & 1
            bpp = (v1 >> 9) & 1
            pal = v1 & 0x1ff
            xpos2 = (v2 >> 16) & 0x3ff
            ypos2 = v2 & 0x3ff
            ysd = ((v3 >> 24) & 0x7f) + 1
            xsd = ((v3 >> 16) & 0x7f) + 1
            ys = (v3 >> 2) & 3
            xs = v3 & 3
            if listing:
                kind = f'tilemap {(v3 >> 4) & 3}' if xs == 0 and ys else f'{tilestable[xs]}x{tilestable[ys]} tiles'
                print(f'    {v1:08x} {v2:08x} {v3:08x}  {kind} tile {tileno:#06x} pal {pal} pos ({xpos2},{ypos2}) '
                      f'size {xsd}x{ysd}{" bpp6" if bpp else ""}{" alpha" if alpha else ""}')
            if ys == 0:
                continue
            if xs == 0:
                regs = D['tmap'][((v3 >> 4) & 3) * 4:((v3 >> 4) & 3) * 4 + 4]
                for yy in range(ysd):
                    cy = (~(ypos2 + gsy - yy) - 18) & 0x3ff
                    if clip[1] <= cy <= clip[3]:
                        tilemap_line(D, buf, regs, cy, clip)
                continue
            ys, xs = tilestable[ys], tilestable[xs]
            xinc = (xsd << 16) // xs
            yinc = (ysd << 16) // ys
            xscale, yscale = xinc // 16, yinc // 16
            if xscale & 0xffff:
                xscale += (1 << 16) // 16
            if yscale & 0xffff:
                yscale += (1 << 16) // 16
            xs -= 1
            ys -= 1
            flipx ^= gfx_
            flipy ^= gfy
            xpos2 += -(xsd // 2) if flipx else xsd // 2
            ypos2 += ysd // 2
            if not flipx:
                xpos2 -= ((xs + 1) * xinc) >> 16
            else:
                xpos2 += (xs * xinc) >> 16
            if flipy:
                ypos2 -= (ys * yinc) >> 16
            apal = gpal if whichpal else pal
            gran = 64 if (gbpp if whichbpp else bpp) else 256
            blend = galpha or alpha
            count = 0
            for xx in range(xs + 1):
                cx = xpos + xpos2 + (-((xx * xinc) >> 16) if flipx else (xx * xinc) >> 16)
                cx = (cx + gsx + 1) & 0x3ff
                if cx & 0x200:
                    cx -= 0x400
                for yy in range(ys + 1):
                    cy = ypos + ypos2 + ((yy * yinc) >> 16 if flipy else -((yy * yinc) >> 16))
                    cy = (0x3ff - (cy + gsy) - 17) & 0x3ff
                    if cy & 0x200:
                        cy -= 0x400
                    drawgfxzoom(buf, clip, char, tileno + count, apal, gran, flipx, flipy, cx, cy, xscale, yscale,
                                blend)
                    count += 1
    col = D['colour']
    img = Image.new('RGB', (W, H))
    img.putdata([((v & 0x1f) << 3, ((v >> 5) & 0x1f) << 3, ((v >> 10) & 0x1f) << 3)
                 for y in range(H) for v in (col[buf[(y * fszy) >> 16][(x * fszx) >> 16] & 0x1ffff]
                                             for x in range(W))])
    fg_layer(D, img)
    return img, buf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('prefix')
    ap.add_argument('snap', nargs='?')
    ap.add_argument('-o')
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()
    D = load(a.prefix)
    img, buf = render(D, a.list)
    if a.o:
        img.save(a.o)
    if a.snap:
        ref = Image.open(a.snap).convert('RGB').crop((0, 0, W, H))
        diff = [p != q for p, q in zip(ref.getdata(), img.getdata())]
        n = sum(diff)
        print(f'{a.prefix}: {n} of {W * H} pixels differ from {a.snap} ')
        if n:
            idx = [i for i, d in enumerate(diff) if d]
            xs, ys = [i % W for i in idx], [i // W for i in idx]
            print(f'  differing area x {min(xs)}-{max(xs)}, y {min(ys)}-{max(ys)}')
            m = Image.new('L', (W, H))
            m.putdata([255 if d else 0 for d in diff])
            m.save(a.prefix + '.diff.png')
        return 1 if n else 0


if __name__ == '__main__':
    sys.exit(main())
