# TC-011: QA | Testcase | Zoom Native Client

## Key Details
| Field | Value |
|-------|-------|
| JIRA ID | QCAPPS-34 / TC-011 |
| Category | Collaboration |
| Priority | High |
| Type | Integration (UI + IGEL App) |
| Feature Area | App Validation — Collaboration |
| Product | IGEL OS 12 |
| Source | TC-003 QCAPPS-34 (reference image + IGEL Apps documentation) |

---

## Description
This test case validates the full lifecycle of Zoom Native Client on IGEL OS 12 — from UMS
profile assignment and app installation through sign-in, audio/video functionality, screen
sharing, meeting participation, and clean exit. It confirms that the Zoom Native Client
operates correctly as a managed thin client application without desktop crashes, missing
audio, or screen share failures.

---

## Additional Information

- Zoom Native Client is delivered as a managed app via the IGEL UMS App Portal (not
  pre-installed on IGEL OS 12 by default)
- Audio device presence is critical — the test will fail silently if no audio device
  is connected; verify with: `aplay -l` and `arecord -l` before starting
- Camera permissions must be explicitly enabled in the IGEL profile or the video feed
  will be blocked
- Zoom SSO requires a configured Identity Provider profile in UMS if enterprise login
  is used; for this test, direct email/password login is acceptable
- Log file location: `journalctl -u zoom --no-pager` or `/var/log/user/zoom*.log`
- If Zoom fails to launch, check app deployment status in UMS:
  `UMS > Devices > [device] > Apps > Zoom > Status = Installed`
- Zoom session config is stored on device at:
  `~/.config/zoomus.conf` (resync profile to reset)

---

## Requirements
- IGEL OS 12.2.0 or later
- UMS 12.x with App Portal access enabled
- Zoom Native Client available in UMS App Portal (confirm under Apps > Zoom)
- Zoom account (email + password) with access to scheduled test meeting
- Audio device: microphone + speaker connected and detected by IGEL OS
- Camera (optional for basic test, required for video step)
- Network: device must have internet access to reach `zoom.us` on port 443 and 8801

---

## Preconditions

- IGEL OS 12 device is online and registered in UMS (green status in UMS console)
- UMS App Portal shows Zoom Native Client as available (`Apps > Zoom` — status: Available)
- Zoom account credentials are available: `api_config["zoom_username"]` and `api_config["zoom_password"]`
- A test Zoom meeting has been scheduled (Meeting ID and Passcode available in `api_config["zoom_meeting_id"]`)
- Audio device (microphone + speaker) is physically connected and visible via `aplay -l`
- Device has internet connectivity — verify with `ping zoom.us` via SSH

---

## TC Setup — UMS Configuration Navigation Paths

```
TC Setup: Apps > Zoom Native Client > Enable = true
TC Setup: Apps > Zoom Native Client > Permissions > Microphone = Allow
TC Setup: Apps > Zoom Native Client > Permissions > Camera = Allow
TC Setup: Apps > Zoom Native Client > Permissions > Screen Share = Allow
TC Setup: Apps > Zoom Native Client > Sessions > New Session > Session Name = "Zoom_Native_Test"
TC Setup: Apps > Zoom Native Client > Sessions > Login URL = (leave blank for direct login)
TC Setup: System > Audio > Default Input Device = (auto-detect or set to connected mic)
TC Setup: System > Audio > Default Output Device = (auto-detect or set to connected speaker)
```

---

## TC Setup — Step-by-Step UMS Configuration

1. Log in to IGEL UMS Web App: `https://<UMS-SERVER>:8443/webapp`
2. Navigate to **Apps > Zoom**, confirm Zoom Native Client shows status **Available**
3. Assign Zoom Native Client to target device:
   `Devices > [hostname] > Apps > Assign App > Select Zoom Native Client > Apply`
4. Edit device profile: `Devices > [hostname] > Edit Profile`
5. Navigate to: `Apps > Zoom > Zoom Sessions > New Session`
6. Set Session Name: `"Zoom_Native_Test"`
7. Configure login: leave SSO URL blank to use direct login (email + password)
8. Enable permissions: `Apps > Zoom > Permissions > Microphone = Allow`, `Camera = Allow`
9. Enable screen share: `Apps > Zoom > Permissions > Screen Share = Allow`
10. Click **Apply** → **Deploy Profile** → confirm deployment status = **Success** in UMS

---

## Test Details

| # | STEP | TEST DATA | EXPECTED RESULT |
|---|------|-----------|-----------------|
| 1 | **Verify app installation and launch Zoom** | 1. Confirm app deployed via UMS: `Devices > [device] > Apps > Zoom > Status`<br>2. On device via SSH: `ps ax \| grep zoom` (should show no running process before launch)<br>3. On device screen: locate Zoom icon in IGEL session bar or launch from Apps menu<br>4. Click the Zoom session `"Zoom_Native_Test"` | • UMS shows Zoom status = **Installed**<br>• Zoom Native Client window opens — sign-in screen displayed<br>• No crash dialog or error popup on launch<br>• `ps ax \| grep zoom` shows Zoom process running |
| 2 | **Sign in to Zoom** | 1. On Zoom sign-in screen: click **Sign In**<br>2. Enter credentials: `api_config["zoom_username"]` in email field<br>3. Enter password: `api_config["zoom_password"]`<br>4. Click **Sign In** button<br>5. If MFA/SSO prompt appears: complete authentication flow<br>6. Wait up to 15 seconds for home screen to load | • Zoom home screen displayed with tabs: **Home**, **Chat**, **Meetings**, **Contacts**<br>• Username visible in top-right profile area<br>• No "Invalid credentials" or network error message<br>• Sign-in completes within 15 seconds |
| 3 | **Validate audio devices (microphone + speaker)** | 1. In Zoom: click profile icon > **Settings > Audio**<br>2. Note the **Microphone** device listed — should match device from `aplay -l`<br>3. Click **Test Mic** — speak into microphone<br>4. Click **Test Speaker** — listen for test tone<br>5. Via SSH: `aplay -l \| grep -i card` to confirm ALSA device<br>6. Via SSH: `arecord -l \| grep -i card` to confirm capture device | • Zoom Settings > Audio shows correct microphone and speaker devices<br>• Microphone meter (green bar) moves in response to voice input<br>• Speaker test plays audible tone through speaker<br>• `aplay -l` and `arecord -l` both show at least 1 card<br>• No "No audio device found" warning in Zoom |
| 4 | **Join test meeting and verify media** | 1. In Zoom: click **Meetings** tab → find pre-scheduled meeting<br>2. Click **Join** — enter `api_config["zoom_meeting_id"]` if prompted<br>3. Enter passcode: `api_config["zoom_passcode"]` if prompted<br>4. Click **Join with Computer Audio**<br>5. Unmute microphone (bottom toolbar)<br>6. Enable camera (bottom toolbar > Start Video)<br>7. Second participant joins from external device to verify audio/video | • Meeting joins successfully — participant list shows device as connected<br>• Remote participant confirms they can hear microphone audio<br>• Camera feed visible in local preview (green border around video tile)<br>• Remote participant confirms webcam feed visible on their screen<br>• Meeting toolbar shows: Unmute, Stop Video, Share Screen, Chat, Participants |
| 5 | **Screen share validation** | 1. In meeting: click **Share Screen** in toolbar<br>2. Select **Desktop** (entire screen) in share dialog<br>3. Click **Share** — confirm sharing started (green border around screen)<br>4. On remote participant device: verify screen content is visible<br>5. Open a window (e.g., file manager) and move it — verify remote sees live update<br>6. Stop sharing: click **Stop Share** in floating toolbar | • Screen share starts — green **"You are sharing your screen"** banner appears<br>• Remote participant sees IGEL OS desktop without black areas or artifacts<br>• Moving windows is reflected live on remote screen without major lag<br>• Stopping share removes banner — returns to normal meeting view<br>• `journalctl \| grep -i zoom \| grep -i error` shows no share-related errors |
| 6 | **Leave meeting and verify clean exit** | 1. Click **Leave** button (bottom right of meeting toolbar)<br>2. Select **Leave Meeting** (not End for all)<br>3. Wait for Zoom to return to home screen<br>4. Close Zoom: File > Exit or close window<br>5. Via SSH: `ps ax \| grep zoom` — verify no zombie process<br>6. Via SSH: `journalctl --no-pager \| grep -iE 'zoom.*error\|zoom.*crash\|zoom.*segfault' \| tail -20` | • Meeting leaves cleanly — Zoom returns to home screen within 5 seconds<br>• Zoom closes without crash dialog<br>• `ps ax \| grep zoom` shows NO running Zoom processes after exit<br>• `journalctl` grep shows **no** crash, segfault, or fatal error entries for Zoom<br>• Audio device released — other audio apps can use microphone after Zoom exits |

---

## Cleanup

| Step | Action | Command / Navigation | Verification |
|------|--------|-----------------------|-------------|
| 1 | Detach Zoom profile from device | `UMS > Devices > [device] > Apps > Zoom > Unassign` | UMS shows Zoom status = Unassigned |
| 2 | Remove Zoom session config | `UMS > Profile > Apps > Zoom > Zoom Sessions > Delete "Zoom_Native_Test"` | Session no longer listed in profile |
| 3 | Reboot device | SSH: `reboot` or UMS: `Devices > [device] > Reboot` | Device comes back online in UMS (green status) within 90 seconds |
| 4 | Verify Zoom removed | SSH: `ps ax \| grep zoom` | No Zoom process running; `~/.config/zoomus.conf` absent or reset |

---

## Troubleshooting

| # | Issue | Symptoms | Root Cause | Diagnostic Command | Fix |
|---|-------|----------|------------|-------------------|-----|
| 1 | Zoom fails to launch | No window appears after clicking session; UMS shows Zoom status = Error | App not deployed or deployment failed | `UMS > Devices > [device] > Apps > Zoom > Status` | Re-assign Zoom app in UMS and redeploy profile; check UMS app portal for app availability |
| 2 | No microphone input in Zoom | Zoom Settings > Audio shows mic but meter doesn't move; remote can't hear audio | Audio device not properly mapped in IGEL profile or ALSA config issue | SSH: `arecord -l` and `arecord -d 3 test.wav && aplay test.wav` | Set explicit audio device in `TC Setup > System > Audio > Default Input Device`; reboot device |
| 3 | Screen share shows black screen | Remote participant sees black/blank screen during screen share | X display permissions not granted for screen capture in IGEL session | SSH: `echo $DISPLAY` (should be `:0`); `xhost +local:` to test | Enable screen share permission explicitly: `TC Setup > Apps > Zoom > Permissions > Screen Share = Allow`; redeploy profile |
| 4 | Zoom crashes on join | Zoom closes unexpectedly when joining meeting | Memory limit or missing dependency on IGEL OS | SSH: `journalctl \| grep -i zoom \| grep -iE 'crash\|segfault\|oom'` | Update Zoom to latest version in UMS App Portal; verify IGEL OS meets minimum version requirement (12.2.0+) |
| 5 | Sign-in fails with network error | "Unable to connect" or "Network error" on sign-in screen | Device cannot reach `zoom.us` on port 443 | SSH: `curl -I https://zoom.us` and `ping -c 4 zoom.us` | Verify network route; check ICG configuration if device is behind ICG proxy; confirm port 443 and 8801 are open |
