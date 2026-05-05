# IGEL Testing - Absolute Beginner's Quick Start Guide

## 🎓 You Know Nothing About IGEL? Start Here!

This guide assumes **ZERO prior knowledge** of IGEL, thin clients, or enterprise device management.

---

## 📚 Chapter 1: The Big Picture

### What Problem Does IGEL Solve?

**Scenario**: Your company has 500 employees who need computers. Traditional approach:
- Buy 500 Windows PCs (expensive!)
- Install software on each one (time-consuming!)
- Update each PC individually (nightmare!)
- Security patches on 500 machines (impossible to manage!)

**IGEL Approach**:
- Buy 500 lightweight IGEL devices (cheaper!)
- Manage ALL of them from ONE central server (easy!)
- Push updates to all 500 at once (efficient!)
- Users connect to virtual desktops or cloud apps (secure!)

**Analogy**: Think of IGEL like a TV (the device) + Netflix (the central server delivering content). The TV is simple and cheap, all the heavy work happens on Netflix's servers.

---

## 🖥️ Chapter 2: The Three Main Components

```
┌─────────────────────────────────────────────────────────┐
│                    YOUR COMPANY                         │
│                                                         │
│  [UMS Server] ◄──── Manages ────► [IGEL Device 1]     │
│  (The Brain)                       [IGEL Device 2]     │
│                                    [IGEL Device 3]     │
│                                    ... (500 devices)    │
│                                                         │
│  Users connect to:                                      │
│  • Windows Servers (RDP)                               │
│  • Azure Virtual Desktop (AVD)                         │
│  • Citrix Server                                       │
│  • Cloud Applications                                  │
└─────────────────────────────────────────────────────────┘
```

### Component 1: IGEL Device (The Hardware)
**What it is**: A small, quiet computer box (looks like a mini PC)
**What it does**: 
- Boots IGEL OS (Linux-based operating system)
- Shows a login screen
- Connects to remote desktops/applications
- Controlled entirely by the UMS server

**What it DOESN'T do**:
- Doesn't run Windows programs locally
- Doesn't store user data locally
- Doesn't need antivirus (minimal attack surface)

**Physical ports**:
- HDMI/DisplayPort (for monitor)
- USB (for keyboard, mouse)
- Ethernet (network connection)
- Power

### Component 2: UMS (Universal Management Suite) - The Management Server
**What it is**: A server application (web-based interface)
**What it does**:
- Registers and tracks all IGEL devices
- Pushes configurations (profiles) to devices
- Performs remote management (reboot, update, shadow)
- Monitors device status (online/offline)

**Think of it as**: The control room for all your devices

**You access it via**: Web browser at https://ums.yourcompany.com

### Component 3: Profiles (The Configuration Blueprints)
**What it is**: A saved set of configurations
**Types of profiles**:
1. **SSO Profile**: Enables login with Microsoft/Okta/PingOne
2. **Session Profile**: Configures RDP/Citrix/AVD connections
3. **App Profile**: Installs applications (Chromium, Firefox)
4. **Appearance Profile**: Wallpaper, screensaver, branding
5. **Certificate Profile**: Security certificates

**How it works**:
1. Admin creates profile in UMS (e.g., "Entra ID Login")
2. Admin assigns profile to device(s)
3. Device automatically downloads and applies profile
4. Device reboots to activate changes

**Analogy**: Think of profiles like template documents. Instead of configuring 500 devices individually, you create one "template" and apply it to all.

---

## 🔑 Chapter 3: Key Terms Explained Simply

| Term | Simple Explanation | Real-World Analogy |
|------|-------------------|-------------------|
| **Thin Client** | Cheap, simple computer that connects to a server | Like a Chromecast - the device is simple, the server does the work |
| **UMS** | Management software for all IGEL devices | Like a fleet management system for trucks |
| **Profile** | A set of settings/configurations | Like a recipe - follow it to get consistent results |
| **SSH** | Text-based remote access to device | Like command prompt on a remote computer |
| **VNC / Shadow** | Visual remote access (see the screen) | Like screen sharing or TeamViewer |
| **Reboot** | Restart the device | Turn it off and on again |
| **API** | A way for programs to talk to each other | Like a waiter (API) taking your order (request) to the kitchen (server) |
| **Bearer Token** | A password for API access | Like a VIP pass to enter a restricted area |

---

## 🛠️ Chapter 4: Your First Day - Setup

### Step 1: Get Your Credentials (Ask Your Admin)

Create a checklist and fill it in:

```
□ UMS Web URL: https://___________________________
□ UMS Username: _________________________________
□ UMS Password: _________________________________
□ UMS Bearer Token: _____________________________

□ Test Device Hostname: _________________________
□ Test Device IP Address: _______________________
□ Test Device SSH Password: _____________________

□ Test User Credentials (for SSO tests):
  - Username: ____________________________________
  - Password: ____________________________________
  - MFA/OTP Setup: Yes / No
```

### Step 2: Access UMS Web Interface

1. Open web browser (Chrome, Edge, Firefox)
2. Go to UMS URL (e.g., https://ums.company.com)
3. Login with your username/password
4. You should see:
   - Left sidebar: Device tree (folders with devices)
   - Center: Device list or dashboard
   - Top menu: File, Edit, Devices, Profiles, etc.

**SUCCESS MARKER**: You can see the list of devices.

### Step 3: Find Your Test Device

1. In UMS web interface
2. Left sidebar → Expand folders
3. Look for device name (e.g., "IGEL-QA-001")
4. Click on device name
5. Right panel shows device details:
   - Status: Online (green) / Offline (red)
   - IP Address: 192.168.x.x
   - MAC Address: 00:11:22:33:44:55
   - OS Version: IGEL OS 12.x.x

**Write down**:
- Device Name: ________________
- IP Address: ________________
- Current Status: Online / Offline

### Step 4: Test SSH Access

**What is SSH?**: It's a way to type commands directly on the device from your computer.

**On Windows**:
1. Open PowerShell or Command Prompt
2. Type: `ssh root@192.168.1.100` (replace with your device IP)
3. Press Enter
4. Type password when prompted
5. If successful, you see a prompt like: `root@IGEL-QA-001:~#`

**Test command**: Type `hostname` and press Enter
- Should return your device name

**Exit SSH**: Type `exit` and press Enter

**On Mac/Linux**: Open Terminal and do the same

**TROUBLESHOOTING**:
- "Connection refused" → SSH not enabled on device (enable in UMS)
- "Connection timeout" → Wrong IP or device offline
- "Permission denied" → Wrong password

### Step 5: Test VNC / Shadow Access

**What is Shadow?**: It's like screen sharing - you see exactly what's on the device screen.

1. In UMS web interface, with device selected
2. Click "Shadow" button (or right-click device → Shadow)
3. Accept any security prompts
4. A new window opens showing the device screen

**What you should see**:
- If logged out: Login screen
- If logged in: Desktop with taskbar at bottom

**Try this**: Move your mouse in the shadow window - you're controlling the device remotely!

**Close shadow**: Close the window when done

---

## 🧪 Chapter 5: Understanding a Test

Let's break down what happens in a typical test using **plain English**.

### Example: Testing Microsoft Login (Entra ID SSO)

**THE GOAL**: Make the device use Microsoft credentials instead of local password

**WHY?**: Companies want one password for everything (email, computer, apps)

**THE PROCESS** (in plain English):

1. **Tell UMS to configure the device for Microsoft login**
   - Like telling Netflix to set up a new device
   - UMS says "OK, I'll configure IGEL-QA-001 for Microsoft login"

2. **Device downloads the configuration**
   - Like downloading an app update
   - Device gets instructions on how to talk to Microsoft

3. **Device reboots to apply changes**
   - Like restarting phone after update
   - Takes about 90 seconds

4. **Device shows Microsoft login screen**
   - Instead of local "Username / Password"
   - Shows "Sign in with Microsoft" screen

5. **User logs in with Microsoft credentials**
   - Email address: user@company.com
   - Microsoft password
   - Maybe a 6-digit code from phone (MFA)

6. **Device desktop loads**
   - User is now logged in
   - Desktop shows with icons and taskbar

7. **Verify it worked behind the scenes**
   - Check if device got a "ticket" from Microsoft
   - Like checking if you got a stamp after entering an event

8. **Clean up (put device back to normal)**
   - Remove Microsoft login configuration
   - Device goes back to local login

**THE TEST PASSES IF**:
- Each step above works without errors
- Login screen changes to Microsoft
- User can log in successfully
- Desktop loads properly

**THE TEST FAILS IF**:
- Microsoft screen doesn't appear
- Login doesn't work
- Device gets stuck somewhere

---

## 📖 Chapter 6: Reading Test Steps

Test cases have standard sections. Here's how to read them:

### Section 1: WHAT THIS TEST DOES
**Purpose**: One-sentence summary
**How to use it**: Read this first to understand the goal

Example:
> "Tests that device can use Microsoft login instead of local password"

### Section 2: WHY IS THIS IMPORTANT
**Purpose**: Business reason for the test
**How to use it**: Understand why this matters to companies

Example:
> "Users want single sign-on - one password for everything"

### Section 3: PRECONDITIONS
**Purpose**: Things that must be ready BEFORE starting
**How to use it**: Checklist to verify before running test

**CRITICAL**: If preconditions aren't met, test will fail!

Example:
- Device must be registered in UMS ← If not, you can't manage it
- Profile must exist in UMS ← If not, you have nothing to assign
- SSH must be enabled ← If not, you can't verify results

### Section 4: TEST STEPS
**Purpose**: Detailed instructions for every action
**How to use it**: Follow step-by-step, don't skip!

**Format**:
```
STEP 1: [Main action]
  1.1 Sub-action
      Details: [Technical info]
      Expected: [What should happen]
  1.2 Next sub-action
      ...
```

**How to execute**:
1. Read entire step first
2. Do sub-step 1.1
3. Verify expected outcome happened
4. If OK → Continue to 1.2
5. If NOT OK → Stop, troubleshoot, do not continue!

### Section 5: EXPECTED RESULTS
**Purpose**: Clear pass/fail criteria
**How to use it**: After test, check if ALL conditions met

Format:
```
✅ PASS if:
  1. Condition A is true
  2. Condition B is true
  3. Condition C is true

❌ FAIL if:
  1. Condition X occurs
  2. Condition Y occurs
```

**Critical Rule**: MUST meet ALL pass conditions. If even one fails → entire test fails.

---

## 🎯 Chapter 7: Your First Test - Step by Step

Let's execute **TC-026: SSH and VNC Enablement** - the simplest test.

**Why start here?**: This test enables remote access. All other tests need this.

### BEFORE YOU START

Check off each item:
```
□ I have UMS access and can login
□ I know my test device name/IP
□ Device shows "Online" in UMS
□ I can open SSH with test network tools
□ I have this guide open on my screen
```

### THE TEST EXECUTION

**STEP 1: Login to UMS**
1. Open browser → Go to UMS URL
2. Login with credentials
3. SUCCESS: You see device tree

**STEP 2: Enable SSH and VNC**
1. Find your test device in left tree
2. Right-click device → "Properties" or "Settings"
3. Look for section "Remote Access" or "Security"
4. Find checkboxes:
   - ☑ Enable SSH
   - ☑ Enable VNC/Shadow
5. Click "OK" or "Apply"

**WHAT JUST HAPPENED**: You told UMS "enable remote access on this device"

**STEP 3: Send Command to Device**
1. Right-click device in UMS
2. Select "Send Settings" or "Update Device"
3. Confirm action
4. Wait 5-10 seconds

**WHAT JUST HAPPENED**: UMS contacted the device and sent the new configuration

**STEP 4: Test SSH**
1. Open PowerShell/Terminal
2. Type: `ssh root@YOUR-DEVICE-IP`
3. Enter password when prompted
4. SUCCESS: You see a command prompt

**TRY THIS**:
- Type: `hostname` → Should show device name
- Type: `uname -a` → Shows OS information
- Type: `exit` → Closes SSH

**STEP 5: Test VNC/Shadow**
1. In UMS, select your device
2. Click "Shadow" button
3. Wait for window to open (5-10 seconds)
4. SUCCESS: You see the device screen

**WHAT YOU SEE**:
- If nobody logged in: Login screen
- Device desktop: Taskbar at bottom, icons

**STEP 6: Record Results**
Fill out:
```
Test: TC-026 SSH and VNC Enablement
Date: [Today's date]

□ SSH connected successfully
□ Commands worked in SSH
□ Shadow window opened
□ Can see device screen

Result: PASS / FAIL
Notes: ________________________________
```

**CONGRATULATIONS!** You just executed your first IGEL test!

---

## 🔧 Chapter 8: Common Problems and Solutions

### Problem 1: "I can't login to UMS"
**Symptoms**: Wrong username/password, account locked
**Solutions**:
1. Verify credentials with admin
2. Check CAPS LOCK is off
3. Try password reset
4. Verify UMS server is running

### Problem 2: "Device shows Offline in UMS"
**Symptoms**: Can't manage device, can't shadow
**Solutions**:
1. Check physical device:
   - Is it powered on? (LED light on)
   - Is network cable connected?
   - Is monitor showing anything?
2. Can you ping the device? `ping device-ip`
   - If no reply → network issue
3. Check UMS server time vs device time (must be synchronized)

### Problem 3: "SSH Connection Refused"
**Symptoms**: `Connection refused` error when trying to SSH
**Solutions**:
1. Verify SSH is enabled in UMS for this device
2. Send settings update to device
3. Reboot device to apply settings
4. Try again after reboot

### Problem 4: "Shadow Window is Black"
**Symptoms**: Shadow opens but shows black screen
**Solutions**:
1. Wait 10-15 seconds (might be loading)
2. Device might be off - check in UMS
3. VNC might be disabled - check settings
4. Try closing and reopening shadow

### Problem 5: "Test Failed but I Don't Know Why"
**Symptoms**: Something didn't work, unclear what
**Solutions**:
1. Read error message carefully (screenshot it!)
2. Check which STEP failed (note the step number)
3. SSH to device and check logs:
   - `journalctl -xe` (system log)
   - `cat /var/log/auth.log` (authentication log)
4. Ask for help with:
   - Test case number
   - Step that failed
   - Error message
   - Screenshots

### Problem 6: "Device Stuck - Not Responding"
**Symptoms**: Device frozen, won't reboot
**Solutions**:
1. Try reboot from UMS: Device → Reboot
2. If no response, physically power cycle:
   - Unplug power cable
   - Wait 10 seconds
   - Plug back in
3. Wait 2-3 minutes for full boot
4. Check if online in UMS

---

## 📝 Chapter 9: Test Documentation

After each test, document results:

### Minimal Documentation (Quick Tests)
```
Test: TC-XXX [Name]
Date: [Date]
Device: [Device name]
Result: PASS / FAIL
Issues: [Any problems encountered]
```

### Full Documentation (Formal Tests)
```
┌─────────────────────────────────────────────┐
│        TEST EXECUTION REPORT                │
├─────────────────────────────────────────────┤
│ Test ID: TC-XXX                             │
│ Test Name: [Full name]                      │
│ Tester: [Your name]                         │
│ Date: [Date and time]                       │
│ Device: [Hostname] ([IP address])           │
├─────────────────────────────────────────────┤
│ PRE-TEST VERIFICATION                       │
│ □ Device online: YES / NO                   │
│ □ UMS accessible: YES / NO                  │
│ □ SSH working: YES / NO                     │
│ □ VNC working: YES / NO                     │
│ □ Preconditions met: YES / NO               │
├─────────────────────────────────────────────┤
│ TEST STEPS EXECUTION                        │
│ □ Step 1: PASS / FAIL - [Notes]             │
│ □ Step 2: PASS / FAIL - [Notes]             │
│ □ Step 3: PASS / FAIL - [Notes]             │
│ □ Step 4: PASS / FAIL - [Notes]             │
├─────────────────────────────────────────────┤
│ ISSUES ENCOUNTERED                          │
│ 1. [Description]                            │
│    - Impact: Minor / Major / Critical       │
│    - Workaround: [If found]                 │
├─────────────────────────────────────────────┤
│ SCREENSHOTS                                 │
│ □ Pre-test state                            │
│ □ Key steps                                 │
│ □ Final result                              │
│ □ Error screens (if failed)                 │
├─────────────────────────────────────────────┤
│ OVERALL RESULT                              │
│ [X] PASS  [ ] FAIL                          │
│                                             │
│ Comments:                                   │
│ ___________________________________________ │
│ ___________________________________________ │
└─────────────────────────────────────────────┘
```

---

## 🎓 Chapter 10: Learning Path

### Week 1: Foundation
- **Day 1-2**: Read this guide, understand concepts
- **Day 3**: Get access, explore UMS interface
- **Day 4**: Execute TC-026 (SSH/VNC) manually
- **Day 5**: Execute one simple test (TC-005 RDP Session)

### Week 2: Basic Tests
- Execute 3-5 basic tests manually
- Document each test
- Learn to troubleshoot common issues
- Understand profile assignment flow

### Week 3: Advanced Tests
- Execute SSO tests (TC-001, TC-002)
- Tests with multiple profiles
- Understand cleanup procedures
- Practice error recovery

### Week 4: Automation
- Read test automation code
- Understand how code maps to manual steps
- Run automated tests
- Compare manual vs automated execution

---

## 🔗 Quick Reference

### UMS Common Tasks
```
VIEW DEVICES:        Left sidebar → Device tree
FIND DEVICE:         Ctrl+F or Search box
DEVICE DETAILS:      Click device → Right panel
ASSIGN PROFILE:      Right-click device → Assign Profile
REBOOT DEVICE:       Right-click device → Reboot
SHADOW SESSION:      Select device → Shadow button
CHECK ONLINE/OFFLINE: Green icon = Online, Red = Offline
```

### SSH Common Commands
```
LOGIN:               ssh root@device-ip
CHECK HOSTNAME:      hostname
CHECK OS VERSION:    cat /etc/os-release
LIST APPS:           igelpkgctl list installed
CHECK KERBEROS:      klist
VIEW SYSTEM LOG:     journalctl -xe
VIEW AUTH LOG:       cat /var/log/auth.log
EXIT SSH:            exit
```

### Typical Test Flow
```
1. Verify preconditions
2. Assign profile via UMS
3. Reboot device (wait 90 sec)
4. Open VNC shadow
5. Verify changes visible
6. Test functionality
7. Check logs via SSH
8. Document results
9. Cleanup (unassign profile)
10. Reboot to default state
```

---

## 📞 Getting Help

When you need help, provide:
1. **Test ID**: TC-XXX
2. **Step**: Which step failed (e.g., "Step 3.2")
3. **What you expected**: "Should see Microsoft login screen"
4. **What you got**: "Blank screen" or "Error message: XYZ"
5. **Screenshots**: Always include!
6. **Device info**: Hostname, IP, OS version

**Example help request**:
```
"Testing TC-001 Entra ID SSO. Step 2.6 - expected to see 
Microsoft login screen after reboot, but device shows local 
login instead. Device: IGEL-QA-001 (192.168.1.100), 
OS 12.7.3. Profile 'Entra-ID-SSO-Profile' shows assigned 
in UMS. Screenshot attached."
```

---

## ✅ Next Steps

After mastering this guide:
1. Read detailed test cases in `IGEL_OS12_TestCases_Beginner_Friendly.md`
2. Explore UMS web interface independently
3. Practice executing tests manually
4. Learn test automation framework
5. Contribute improvements to test documentation

**Remember**: Everyone was a beginner once. Take your time, ask questions, and document everything!

---

**Document Version**: 1.0  
**Created**: April 27, 2026  
**Purpose**: Onboarding guide for new IGEL testers with zero experience  
**Next Document**: IGEL_OS12_TestCases_Beginner_Friendly.md (detailed test cases)
