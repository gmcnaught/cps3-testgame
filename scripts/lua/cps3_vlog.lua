-- MAME autoboot script (scripts/cps3_vlog.sh): logs a real CPS3 game's video set-up for docs/CPS3.md.
--   VLOG_OUT    output directory (writes.log, dump_<frame>.* and snapshots)
--   VLOG_DUMP   comma-separated frame numbers at which to dump sprite RAM, colour RAM, SS RAM, PPU registers and
--               take a snapshot
--   VLOG_END    frame at which to exit
--   VLOG_INPUT  "frame:port:field:frames,..." held inputs (e.g. "600::INPUTS:Coin 1:5")
--   VLOG_FROM   first frame from which register writes are logged (default 0)
-- writes.log: one line per write to the PPU registers (0x040c0000-0x040c00af), the SS registers, the IRQ
-- acknowledge registers and the cache-RAM area; the character DMA list is read out of character RAM when a
-- character DMA starts. Dumps: big-endian 32-bit words, except .colour (16-bit) and .charram (byte order as
-- MAME's m_char_ram on a little-endian host: the DMA writes byte n at n ^ 3). Each line starts with MAME's screen frame number and the scan lines since that frame's
-- frame-done callback.
local out = os.getenv("VLOG_OUT") or "vlog"
local dumps = {}
for f in string.gmatch(os.getenv("VLOG_DUMP") or "", "%d+") do dumps[tonumber(f)] = true end
local endf = tonumber(os.getenv("VLOG_END") or "3000")
local from = tonumber(os.getenv("VLOG_FROM") or "0")
local inputs = {}
for f, port, field, n in string.gmatch(os.getenv("VLOG_INPUT") or "", "(%d+):([^:]+):([^:]+):(%d+)") do
  inputs[#inputs + 1] = { f = tonumber(f), port = port, field = field, n = tonumber(n) }
end

local machine = manager.machine
local cpu = machine.devices[":maincpu"]
local space = cpu.spaces["program"]
local screen = machine.screens[":screen"]
local log = assert(io.open(out .. "/writes.log", "w"))
local function frame() return screen:frame_number() end
-- frame number and the time since the last frame-done callback, in scan lines (63.55 us)
local fstart = 0
local function pos()
  return string.format("%6d %5.1f", frame(), (machine.time:as_double() - fstart) * 15734.25)
end

local function w(name)
  return function(offset, data, mask)
    if frame() >= from then
      log:write(string.format("%s %-6s %08x %08x/%08x pc=%08x\n", pos(), name, offset, data, mask, cpu.state["PC"].value))
    end
  end
end

-- the character DMA list sits in character RAM, readable through the 0x04100000 window of the current bank
local chardma = { src = 0, other = 0 }
local function chardma_tap(offset, data, mask)
  if offset == 0x040c0094 then
    if mask & 0xff ~= 0 then chardma.src = data & 0xffff end
    return
  end
  if mask & 0xff000000 == 0 then return end
  chardma.other = data
  if (data >> 16) & 0x40 == 0 then return end
  local list = chardma.src | (data & 0x003f0000)   -- word address in character RAM
  local byte = list * 4
  log:write(string.format("%s CHRDMA list=%06x (byte %06x, bank %d, current bank %d)\n", pos(), list, byte,
    byte >> 20, chardma.bank or -1))
  if chardma.bank ~= byte >> 20 then
    log:write("  (list outside the current character RAM bank; not read)\n")
    return
  end
  local a = 0x04100000 + (byte & 0xfffff)
  for i = 0, 0x1000 - 3, 3 do
    local d1 = space:read_u32(a + i * 4)
    local d2 = space:read_u32(a + i * 4 + 4)
    local d3 = space:read_u32(a + i * 4 + 8)
    log:write(string.format("  cmd=%d len=%06x dst=%06x src=%07x  [%08x %08x %08x]\n", (d1 >> 21) & 7,
      ((d1 & 0x1fffff) + 1) << 3, d2 << 3, ((d3 << 1) - 0x400000) & 0xffffffff, d1, d2, d3))
    if d1 & 0x01000000 ~= 0 then break end
  end
end

-- logged on a change only (the RAM test and the games write it constantly)
local crambank_last = {}
local function crambank(o, d, m)
  if dumping then return end
  if m & 0xff ~= 0 then chardma.bank = d & 7 end
  if crambank_last[m] ~= d then crambank_last[m] = d; w("CRAMBK")(o, d, m) end
end
-- the sprite list as MAME's spritedma_w copies it (8 after 9 written to 0x040c0082): main list records up to the
-- end marker, each one's sublist, and the 8 global scroll registers; kept for the dumps (.spritelist, .gscrollbuf)
local splist = { words = {}, gscroll = {} }
local spdma_prev = 0
local function spritedma(o, d, m)
  if o ~= 0x040c0080 or m & 0xffff == 0 then return end
  local v = d & 0xffff
  if v & 9 == 8 and spdma_prev & 9 == 9 then
    local words, sr = {}, 0x04000000
    for i = 0, 0x2000 // 4 - 4, 4 do
      for k = 0, 3 do words[i + k] = space:read_u32(sr + (i + k) * 4) end
      local dat = words[i]
      if dat & 0x80000000 ~= 0 then break end
      local offs = (dat & 0x7fff) << 2
      local len = (dat >> 16) & 0x1ff
      for k = offs, offs + len * 4 - 1 do words[k] = space:read_u32(sr + k * 4) end
    end
    local g = {}
    local gs = machine.memory.shares[":ppu_gscroll_regs"]  -- write-only registers: read the share
    for k = 0, 7 do g[k] = gs:read_u32(k * 4) end
    splist = { words = words, gscroll = g, frame = frame() }
  end
  spdma_prev = v
end
-- SS registers: bytes 0x00-0x15 (umask 0x00ff00ff: each 32-bit word carries offsets 2k in bits 16-23 and 2k + 1 in
-- bits 0-7); kept for the dumps (.ssregs)
local ssregs = {}
local function ssreg(o, d, m)
  local k = (o - 0x05050000) // 4 * 2
  if m & 0x00ff0000 ~= 0 then ssregs[k] = (d >> 16) & 0xff end
  if m & 0x000000ff ~= 0 then ssregs[k + 1] = d & 0xff end
  w("SSREG")(o, d, m)
end
local function ppu(o, d, m)
  spritedma(o, d, m)
  w("PPU")(o, d, m)
end
-- per-frame counts of CPU writes to sprite RAM and colour RAM (accesses, and bytes by mask), logged as COUNT lines
local counts = { spr = 0, sprb = 0, col = 0, colb = 0 }
local function nbytes(m)
  local n = 0
  for k = 0, 3 do if (m >> (k * 8)) & 0xff ~= 0 then n = n + 1 end end
  return n
end
local tapdefs = {
  { "sprcount", 0x04000000, 0x0407ffff, function(o, d, m) counts.spr = counts.spr + 1; counts.sprb = counts.sprb + nbytes(m) end },
  { "colcount", 0x04080000, 0x040bffff, function(o, d, m) counts.col = counts.col + 1; counts.colb = counts.colb + nbytes(m) end },
  { "ppu", 0x040c0000, 0x040c0083, ppu },
  { "crambank", 0x040c0084, 0x040c0087, crambank },
  { "ppu2", 0x040c0088, 0x040c00af, w("PPU") },
  { "chardma", 0x040c0094, 0x040c009b, chardma_tap },
  { "ssregs", 0x05050000, 0x0505002b, ssreg },
  { "irqack", 0x05100000, 0x0513ffff, w("IRQACK") },
}
-- VLOG_TAPS: comma-separated subset of the tap names above (default all)
local only = os.getenv("VLOG_TAPS")
vlog_taps = {}  -- global: a tap whose handle is collected is removed (or crashes MAME)
for _, t in ipairs(tapdefs) do
  if not only or string.find("," .. only .. ",", "," .. t[1] .. ",", 1, true) then
    vlog_taps[#vlog_taps + 1] = space:install_write_tap(t[2], t[3], t[1], t[4])
  end
end

local function dump_share(name, file)
  local s = machine.memory.shares[name]
  if not s then log:write("no share " .. name .. "\n"); return end
  local f = assert(io.open(file, "wb"))
  for i = 0, s.size - 4, 4 do f:write(string.pack(">I4", s:read_u32(i))) end
  f:close()
end

local function dump_space(a0, a1, file, width)
  local f = assert(io.open(file, "wb"))
  if width == 2 then
    for a = a0, a1, 2 do f:write(string.pack(">I2", space:read_u16(a))) end
  else
    for a = a0, a1, 4 do f:write(string.pack(">I4", space:read_u32(a))) end
  end
  f:close()
end

local function dump(fr)
  local p = string.format("%s/dump_%06d", out, fr)
  dump_share(":spriteram", p .. ".spriteram")
  dump_share(":ppu_gscroll_regs", p .. ".gscroll")
  dump_share(":ppu_tmap_regs", p .. ".tmap")
  dump_share(":ppu_crtc_zoom", p .. ".crtc")
  dump_share(":mainram", p .. ".mainram")
  local f = assert(io.open(p .. ".spritelist", "wb"))
  for i = 0, 0x80000 // 4 - 1 do f:write(string.pack(">I4", splist.words[i] or 0)) end
  f:close()
  f = assert(io.open(p .. ".ssregs", "wb"))
  for k = 0, 0x15 do f:write(string.pack("B", ssregs[k] or 0)) end
  f:close()
  f = assert(io.open(p .. ".gscrollbuf", "wb"))
  for k = 0, 7 do f:write(string.pack(">I4", splist.gscroll[k] or 0)) end
  f:close()
  dump_space(0x04080000, 0x040bffff, p .. ".colour", 2)
  dump_space(0x05040000, 0x0504ffff, p .. ".ssram", 4)
  -- character RAM, 8 banks of 1 MB through the 0x04100000 window; the game's bank is restored afterwards
  -- (the bank writes are not logged)
  dumping = true
  local f = assert(io.open(p .. ".charram", "wb"))
  for b = 0, 7 do
    space:write_u32(0x040c0084, b)
    for a = 0x04100000, 0x041ffffc, 4 do f:write(string.pack("<I4", space:read_u32(a))) end
  end
  f:close()
  space:write_u32(0x040c0084, chardma.bank or 0)
  dumping = false
  machine.video:snapshot()
  log:write(string.format("%s DUMP %s\n", pos(), p))
end

local held = {}
emu.register_frame_done(function()
  local fr = frame()
  fstart = machine.time:as_double()
  for _, i in ipairs(inputs) do
    if i.f == fr then
      local field = machine.ioport.ports[":" .. i.port].fields[i.field]
      field:set_value(1)
      held[#held + 1] = { field = field, until_f = fr + i.n }
    end
  end
  for k = #held, 1, -1 do
    if held[k].until_f <= fr then held[k].field:clear_value(); table.remove(held, k) end
  end
  if fr >= from then
    log:write(string.format("%6d   0.0 COUNT  sprite RAM %d writes %d bytes, colour RAM %d writes %d bytes\n", fr,
      counts.spr, counts.sprb, counts.col, counts.colb))
  end
  counts = { spr = 0, sprb = 0, col = 0, colb = 0 }
  if dumps[fr] then dump(fr) end
  if fr >= endf then log:close(); machine:exit() end
end)
