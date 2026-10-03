-- MAME autoboot script (scripts/cps3_ttest.sh): src/ttest.c's results (tt_res at 0x02000000: magic 'TTST', passes
-- done, tests, values) written to $TTEST_OUT as "<index> <value hex>" once $TTEST_PASSES passes are done, with a
-- snapshot of the screen (tools/ttest_check.py reads it back as it reads a jtcps3 screenshot); then exit.
local machine = manager.machine
local sp = machine.devices[":maincpu"].spaces["program"]
local passes = tonumber(os.getenv("TTEST_PASSES") or "2")
emu.register_frame_done(function()
  if sp:read_u32(0x02000000) ~= 0x54545354 or sp:read_u32(0x02000004) < passes then return end
  local f = assert(io.open(os.getenv("TTEST_OUT"), "w"))
  local n = sp:read_u32(0x02000008)
  for i = 0, n - 1 do f:write(string.format("%d %08x\n", i, sp:read_u32(0x0200000c + 4 * i))) end
  f:close()
  machine.video:snapshot()
  machine:exit()
end)
