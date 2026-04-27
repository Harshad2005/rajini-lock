# 🆘 Rajini-Lock Recovery Guide

Things go wrong. Here's how to get out of any state.

## Tier 1 — I'm logged in but want the lock off

```bash
touch ~/.rajini_disable
```

Next login skips the lock. Or fully remove:

```bash
bash ~/Library/Application\ Support/RajiniLock/app/scripts/uninstall.sh
```

## Tier 2 — Lock screen is stuck or my voice isn't matching

The lock screen is a regular GUI app — not a system login replacement —
so you can always drop to a TTY or use SSH.

**Option A — SSH from another device** (if Remote Login is enabled):

```bash
ssh harshadmahajan@<your-mac-ip>
touch ~/.rajini_disable
killall Python   # closes the lock window
```

**Option B — Force-quit from the keyboard** (no escape keys work
inside the lock by design, but macOS-level shortcuts still do):

- ⌃⌥⌘⏏ (Control+Option+Command+Eject) → restart
- Hold power button for 5s → hard shutdown
- Boot, then immediately log into another admin account if you have one

## Tier 3 — Recovery Mode (last resort)

1. Shut down the Mac.
2. **Apple Silicon:** hold the power button until "Loading startup
   options" appears, click **Options → Continue**.
3. Choose **Utilities → Terminal**.
4. Run:

   ```bash
   touch /Users/harshadmahajan/.rajini_disable
   # or fully unload the agent:
   rm /Users/harshadmahajan/Library/LaunchAgents/com.rajinilock.unlocker.plist
   ```

5. Reboot. You'll come back into normal macOS with the lock disabled.

## Re-enroll your voice

Voice changed (cold, etc.)? Re-record:

```bash
~/Library/Application\ Support/RajiniLock/app/venv/bin/rajini-enroll
```
