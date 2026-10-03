-- MAME autoboot script: snapshots at the frames in $SNAP_AT (comma-separated), then exit after the last.
local m = manager.machine
local at, last = {}, 0
for f in string.gmatch(os.getenv("SNAP_AT") or "120", "%d+") do at[tonumber(f)] = true; last = math.max(last, tonumber(f)) end
local n = 0
emu.register_frame_done(function()
  n = n + 1
  if at[n] then m.video:snapshot() end
  if n >= last then m:exit() end
end)
