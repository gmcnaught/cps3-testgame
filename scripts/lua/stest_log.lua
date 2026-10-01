-- MAME autoboot script (scripts/cps3_stest.sh): every write to the CPS3 sound registers (0x040e0000-0x040e02ff)
-- logged to $STEST_LOG as "<machine time s> <frame> <word offset> <data hex>", frame = src/stest.c's st_frame
-- (0x02000000); MAME exits once st_frame reaches $STEST_END.
local machine = manager.machine
local sp = machine.devices[":maincpu"].spaces["program"]
local log = assert(io.open(os.getenv("STEST_LOG"), "w"))
local endf = tonumber(os.getenv("STEST_END") or "1440")
stest_tap = sp:install_write_tap(0x040e0000, 0x040e02ff, "stest", function(offset, data, mask)
  log:write(string.format("%.9f %d %d %08x\n", machine.time:as_double(), sp:read_u32(0x02000000),
    (offset - 0x040e0000) // 4, data))
end)
emu.register_frame_done(function()
  if sp:read_u32(0x02000000) >= endf then log:close(); machine:exit() end
end)
