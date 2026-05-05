# IGEL OS 12 Test Cases - Beginner-Friendly Guide

## 📘 Introduction for Beginners

### What is IGEL?
**IGEL** is a Linux-based operating system specifically designed for thin client devices. Think of it as a secure, lightweight OS that sits on a device and allows users to connect to virtual desktops, cloud applications, or remote sessions (like RDP, Citrix, Azure Virtual Desktop).

### Key Concepts You Need to Know

#### 1. **IGEL Device (Thin Client)**
- Physical hardware (like a desktop computer but smaller)
- Runs IGEL OS 12 (the operating system)
- Managed centrally, not individually configured
- Examples: IGEL UD3, IGEL UD6, or converted PC

#### 2. **UMS (Universal Management Suite)**
- Central management server (like a control tower)
- Manages ALL IGEL devices from one place
- Web-based interface (accessible via browser)
- Think of it as "Mission Control" for your IGEL devices

#### 3. **Profile**
- A set of configurations/settings
- Can be assigned to one or many devices
- Examples:
  - **SSO Profile**: Enables Single Sign-On with Microsoft, Okta, etc.
  - **App Profile**: Installs applications like Chromium browser
  - **Session Profile**: Configures RDP or Citrix connections
  - **Wallpaper Profile**: Customizes desktop appearance

#### 4. **SSH (Secure Shell)**
- Remote command-line access to the IGEL device
- Like opening a terminal window on the device from your computer
- Used to run commands, check logs, verify installations

#### 5. **VNC (Virtual Network Computing) / Shadow Session**
- Remote desktop viewer for IGEL device
- See exactly what's on the device screen
- Can interact with the device remotely (click, type, etc.)

#### 6. **Device Reboot**
- Restart the IGEL device
- Required after profile changes to apply new settings
- Takes approximately 60-90 seconds

---

## 🎯 Test Execution Prerequisites

### What You Need Before Starting ANY Test:

1. **Access to UMS Server**
   - UMS Web URL (e.g., `https://ums.company.com`)
   - Username and password with admin rights
   - Bearer token (authentication key for API access)

2. **IGEL Device Information**
   - Device hostname (e.g., `IGEL-QA-001`)
   - Device IP address (e.g., `192.168.1.100`)
   - Device MAC address (for identification)
   - SSH credentials: username=`root`, password (configured in UMS)

3. **Testing Tools Setup**
   - Python environment with required libraries
   - VNC viewer or UMS Web App access for shadow sessions
   - SSH client (PuTTY, MobaXterm, or built-in terminal)

4. **Test Data Configuration Files**
   - `testdata/sso/api_config.yaml` - SSO credentials
   - `config/all_conf.yaml` - UMS and device credentials
   - Profile names configured in UMS

---

## 📋 Test Cases

---

### **TC-001: Entra ID SSO - Microsoft Single Sign-On Login**

#### **WHAT THIS TEST DOES**
This test verifies that an IGEL device can use Microsoft Entra ID (formerly Azure AD) for user login instead of local username/password. It's like enabling "Sign in with Microsoft" on the device.

#### **WHY IS THIS IMPORTANT**
- Organizations use Microsoft 365 need seamless login
- One set of credentials for everything (single sign-on)
- More secure with multi-factor authentication (MFA)

#### **BACKGROUND CONCEPTS**

**Entra ID (Microsoft)**: Microsoft's cloud identity service. Think of it as the "login system" for Microsoft 365, Azure, and other services.

**Kerberos Ticket**: A security token that proves you've logged in. Like a digital badge that says "this user is authenticated."

**TOTP/MFA**: Time-based One-Time Password - the 6-digit code from Microsoft Authenticator app.

---

#### **PRECONDITIONS (What Must Be Ready BEFORE Test)**

| # | Precondition | How to Verify | What It Means |
|---|--------------|---------------|---------------|
| 1 | IGEL OS 12 device registered in UMS | Login to UMS Web → Devices → Search for device name | Device appears in UMS device tree |
| 2 | Entra ID SSO profile exists in UMS | UMS → Profiles → Search "Entra-ID-SSO-Profile" | Profile is already created by admin |
| 3 | UMS bearer token available | Check `config/all_conf.yaml` has `bearer_token` value | Token exists and is valid (not expired) |
| 4 | SSH enabled on device | Try: `ssh root@device-ip` | Can connect without error |
| 5 | VNC/Shadow enabled | UMS Web → Device → Click "Shadow" button | Shadow session window opens |
| 6 | Test user credentials in Entra ID | Have valid Microsoft account username/password/OTP secret | Can login to portal.office.com with these credentials |

---

#### **TEST STEPS (Detailed Walkthrough)**

**STEP 1: Assign Entra ID Profile to Device**

| Sub-Step | Action | How to Do It | What Happens | Verification |
|----------|--------|--------------|--------------|--------------|
| 1.1 | Login to UMS via API | Python code: `UMS(base_url, username, password)` | Connect to UMS programmatically | No errors returned |
| 1.2 | Get device details | `ums.get_vm_details("IGEL-QA-001")` | Retrieve device ID and current state | Returns device object with `id` field |
| 1.3 | Get Entra ID profile | `ums.get_profile_details("Entra-ID-SSO-Profile")` | Retrieve profile ID from UMS | Returns profile object with `id` field |
| 1.4 | Assign profile to device | `wums.assign_object(device_id, profile_id, "profile")` | Link profile to device | UMS shows profile assigned in device view |
| 1.5 | Reboot device | `ums.device_reboot(device)` | Restart device to apply changes | Device goes offline then back online (90 sec) |

**STEP 2: Open Shadow Session and Verify Login Screen**

| Sub-Step | Action | How to Do It | What Happens | Verification |
|----------|--------|--------------|--------------|--------------|
| 2.1 | Wait for device reboot | `time.sleep(90)` | Ensure device fully rebooted | Device shows "online" in UMS |
| 2.2 | Open VNC shadow | UMS Web → Device → Shadow button | VNC viewer shows device screen | See device desktop or login screen |
| 2.3 | Verify Microsoft login screen | Look for text "Microsoft" or "Sign in" | Entra ID login page should appear | **EXPECTED**: Microsoft/Entra ID login screen visible |

![What you should see: Microsoft login screen with email/username field]

**STEP 3: Authenticate with Entra ID Credentials**

| Sub-Step | Action | How to Do It | What Happens | Verification |
|----------|--------|--------------|--------------|--------------|
| 3.1 | Enter username | Type: `testuser@company.com` → Press Enter | Microsoft checks username | Moves to password screen |
| 3.2 | Enter password | Type password → Press Enter | Microsoft verifies password | Moves to MFA screen (if enabled) |
| 3.3 | Enter MFA code (if required) | Use `OTPGenerator` to get 6-digit code → Type → Enter | Microsoft verifies time-based code | "Stay signed in?" prompt OR desktop loads |
| 3.4 | Verify desktop loads | Wait 5-10 seconds | Device desktop appears | **EXPECTED**: IGEL desktop visible with taskbar |

**STEP 4: Verify Kerberos Ticket (SSH Verification)**

| Sub-Step | Action | How to Do It | What Happens | Verification |
|----------|--------|--------------|--------------|--------------|
| 4.1 | SSH into device | `ssh root@device-ip` | Connect to device command line | Terminal prompt appears |
| 4.2 | Run klist command | Type: `klist` → Enter | Shows Kerberos tickets | **EXPECTED**: Output contains "Ticket cache" or "Credentials cache" |
| 4.3 | Verify ticket for user | Check output for `testuser@COMPANY.COM` | Confirms SSO authentication created ticket | Principal name matches logged-in user |

Example expected output:
```
Ticket cache: FILE:/tmp/krb5cc_1000
Default principal: testuser@COMPANY.COM

Valid starting     Expires            Service principal
04/27/26 10:00:00  04/27/26 20:00:00  krbtgt/COMPANY.COM@COMPANY.COM
```

**STEP 5: Cleanup (Return to Normal State)**

| Sub-Step | Action | How to Do It | What Happens | Verification |
|----------|--------|--------------|--------------|--------------|
| 5.1 | Unassign Entra ID profile | `wums.detach_profile(device_id, profile_id)` | Remove SSO profile from device | UMS shows profile removed |
| 5.2 | Reboot device | `ums.device_reboot(device)` | Apply changes | Device restarts (60 sec) |
| 5.3 | Verify local login restored | Open shadow session | Should see local login (username/password fields for local accounts) | **EXPECTED**: Local IGEL login screen, NOT Microsoft |

---

#### **EXPECTED RESULTS (Success Criteria)**

✅ **PASS if ALL of these are true:**

1. After profile assignment and reboot: Microsoft/Entra ID login screen appears in VNC
2. After entering valid credentials: Desktop loads successfully
3. SSH `klist` command shows valid Kerberos ticket for the user
4. After cleanup: Device returns to local login (no Microsoft screen)

❌ **FAIL if ANY of these occur:**

- Microsoft login screen does not appear after reboot
- Cannot enter credentials / keyboard not working
- Desktop does not load after authentication
- `klist` shows "No credentials cache" or error
- Device stuck at boot screen after profile assignment

---

#### **AUTOMATION NOTES**

**Functions Used:**
- `UMS()`: Connects to UMS API
- `UMSWUMSApi()`: Web-based UMS operations
- `get_vm_details()`: Retrieves device information
- `get_profile_details()`: Retrieves profile information
- `assign_object()`: Assigns profile to device
- `device_reboot()`: Reboots device
- `OcrUiInteractor().is_text_present_on_screen()`: Checks text on VNC screen
- `SSHClient()`: SSH connection to device
- `OTPGenerator()`: Generates TOTP codes for MFA

**Config Files:**
- `config/all_conf.yaml`: UMS credentials, device credentials
- `testdata/sso/api_config.yaml`: Entra username, password, OTP secret, profile name

---

### **TC-002: PingOne SSO - PingIdentity Single Sign-On Login**

#### **WHAT THIS TEST DOES**
Tests that an IGEL device can use PingOne (another SSO provider like Microsoft) for user authentication. PingOne is commonly used by enterprises for identity management.

#### **WHY IS THIS IMPORTANT**
- Alternative SSO provider (not everyone uses Microsoft)
- Tests IGEL's compatibility with different identity providers
- Validates error logging for troubleshooting

#### **BACKGROUND CONCEPTS**

**PingOne**: Identity-as-a-Service platform by Ping Identity (similar to Microsoft Entra ID).

**Auth Logs**: `/var/log/auth.log` - Linux system file that records all authentication attempts (successful and failed).

---

#### **PRECONDITIONS**

| # | Precondition | How to Verify | What It Means |
|---|--------------|---------------|---------------|
| 1 | IGEL OS 12 device registered in UMS | Login to UMS → Devices → Search device | Device visible in UMS |
| 2 | PingOne SSO profile in UMS | UMS → Profiles → "PingOne-SSO-Profile" | Profile exists |
| 3 | Test user in PingOne with valid credentials | Have username/password for PingOne account | Can login to PingOne portal |
| 4 | SSH enabled on device | `ssh root@device-ip` works | Can access device terminal |
| 5 | VNC enabled | Can open shadow session | Can see device screen |

---

#### **TEST STEPS**

**STEP 1: Assign PingOne Profile and Verify Login Screen**

| Sub-Step | Action | Expected Outcome |
|----------|--------|------------------|
| 1.1 | Assign PingOne profile to device via UMS API | Profile assigned, visible in UMS |
| 1.2 | Reboot device and wait 90 seconds | Device reboots and comes back online |
| 1.3 | Open VNC shadow session | Can see device screen |
| 1.4 | Check for PingOne login screen | **EXPECTED**: Screen shows "PingOne" or "Ping" text with username/password fields |

**STEP 2: Authenticate with PingOne Credentials**

| Sub-Step | Action | Expected Outcome |
|----------|--------|------------------|
| 2.1 | Enter PingOne username | Username appears in field |
| 2.2 | Press Tab key to move to password field | Cursor moves to password field |
| 2.3 | Enter PingOne password | Password shows as dots/asterisks |
| 2.4 | Press Enter/Return | Authentication starts |
| 2.5 | Wait 5 seconds for login to complete | Login progress happening |
| 2.6 | Verify desktop visible | **EXPECTED**: IGEL desktop loads with "desktop" text visible |

**STEP 3: Check Authentication Logs for Errors**

| Sub-Step | Action | Expected Outcome |
|----------|--------|------------------|
| 3.1 | SSH into device | Connected to device terminal |
| 3.2 | Run command: `grep -i error /var/log/auth.log \| tail -3` | Shows last 3 error lines from auth log |
| 3.3 | Review output | **EXPECTED**: No critical errors related to PingOne authentication. Minor warnings OK. |

Example of acceptable output:
```
(No output means no errors - GOOD!)
```

Example of problematic output:
```
Apr 27 10:05:00 sshd[1234]: error: PAM: Authentication failure for testuser
```

**STEP 4: Cleanup**

| Sub-Step | Action | Expected Outcome |
|----------|--------|------------------|
| 4.1 | Unassign PingOne profile from device | Profile removed in UMS |
| 4.2 | Reboot device | Device restarts to default state |
| 4.3 | Verify local login restored | Local login screen (not PingOne) |

---

#### **EXPECTED RESULTS**

✅ **PASS:**
1. PingOne login screen appears after reboot
2. Valid credentials allow successful login
3. Desktop loads after authentication
4. No critical errors in `/var/log/auth.log`

❌ **FAIL:**
- PingOne screen does not appear
- Cannot login with valid credentials
- Desktop does not load
- Critical authentication errors in logs

---

### **TC-005: RDP Session - Windows Remote Desktop Connection**

#### **WHAT THIS TEST DOES**
Tests that an IGEL device can connect to a Windows server/desktop using the RDP (Remote Desktop Protocol). This is one of the most common use cases for IGEL devices.

#### **WHY IS THIS IMPORTANT**
- Primary use case: Users connect to Windows desktops from IGEL thin clients
- Tests basic session connectivity
- Validates profile-based session configuration

#### **BACKGROUND CONCEPTS**

**RDP (Remote Desktop Protocol)**: Microsoft's protocol for connecting to Windows machines remotely. Like using TeamViewer but built into Windows.

**Session Icon**: After profile assignment, an icon appears on IGEL desktop. Clicking it launches the RDP connection.

**Windows Desktop**: The full Windows interface (Start menu, taskbar, desktop icons) displayed on the IGEL device.

---

#### **PRECONDITIONS**

| # | Precondition | How to Verify | Details |
|---|--------------|---------------|---------|
| 1 | IGEL OS 12 device registered in UMS | Device visible in UMS | Device online and managed |
| 2 | RDP session profile in UMS | UMS → Profiles → "RDP-Session-Profile" | Profile contains Windows server IP, credentials |
| 3 | Windows RDP server accessible | Ping Windows server IP from network | Server reachable and RDP port 3389 open |
| 4 | Windows user credentials | Have valid Windows username/password | Can login to Windows server directly |
| 5 | SSH and VNC enabled on IGEL device | Can SSH and open shadow | Remote management working |

---

#### **TEST STEPS**

**STEP 1: Assign RDP Profile and Verify Session Icon**

| Sub-Step | Action | Details | Expected Outcome |
|----------|--------|---------|------------------|
| 1.1 | Assign RDP session profile via API | `wums.assign_object(device_id, profile_id, "profile")` | Profile assigned |
| 1.2 | Reboot device | Wait 90 seconds | Device applies profile changes |
| 1.3 | Open VNC shadow session | See device desktop | Can see IGEL desktop |
| 1.4 | Look for RDP session icon | Scan desktop for icon with session name (e.g., "RDP" or "Windows Desktop") | **EXPECTED**: Icon visible on desktop |

![What you should see: Desktop with an icon labeled "RDP" or configured session name]

**STEP 2: Launch RDP Session and Login to Windows**

| Sub-Step | Action | Details | Expected Outcome |
|----------|--------|---------|------------------|
| 2.1 | Click RDP session icon | Use VNC mouse to click icon | RDP client starts |
| 2.2 | Wait for credential prompt (if not saved) | May take 3-5 seconds | Login window appears OR direct connection if credentials saved |
| 2.3 | Enter Windows username (if prompted) | Type username → Press Tab | Username entered |
| 2.4 | Enter Windows password (if prompted) | Type password → Press Enter | Authentication starts |
| 2.5 | Wait for Windows desktop to load | Can take 5-10 seconds | Windows loading screen |
| 2.6 | Verify Windows desktop visible | Look for Windows Start button, taskbar | **EXPECTED**: Full Windows desktop visible in IGEL's RDP session |

What you're seeing:
- The IGEL device is the physical hardware
- The IGEL desktop is the thin client OS
- The Windows desktop is inside a window/fullscreen running via RDP
- You're controlling Windows from IGEL

**STEP 3: Test Application Launch (Optional Validation)**

| Sub-Step | Action | Expected Outcome |
|----------|--------|------------------|
| 3.1 | In Windows session, click Start button | Start menu opens |
| 3.2 | Search for Notepad | Search results show Notepad |
| 3.3 | Click to launch Notepad | Notepad application opens inside Windows session |
| 3.4 | Type test text: "RDP connection working" | Text appears in Notepad |

This proves the session is fully functional and interactive.

**STEP 4: Disconnect RDP Session**

| Sub-Step | Action | Details | Expected Outcome |
|----------|--------|---------|------------------|
| 4.1 | Press Ctrl+Alt+Delete inside session | May need to use VNC control for this | Windows security screen appears |
| 4.2 | Click "Disconnect" option | DO NOT click "Sign out" - Disconnect keeps session alive | Windows session disconnects |
| 4.3 | Verify return to IGEL desktop | Should see IGEL desktop again, not Windows | **EXPECTED**: Back at IGEL desktop, RDP icon still visible |

**Alternative method:**
- Look for disconnect button in RDP toolbar
- Or simply close the RDP window

**STEP 5: Cleanup**

| Sub-Step | Action | Expected Outcome |
|----------|--------|------------------|
| 5.1 | Unassign RDP profile | Profile removed from device |
| 5.2 | Reboot device | Device restarts |
| 5.3 | Verify RDP icon no longer on desktop | Clean desktop, no session icons |

---

#### **EXPECTED RESULTS**

✅ **PASS:**
1. RDP session icon appears on IGEL desktop after profile assignment
2. Clicking icon launches RDP connection
3. Windows desktop loads and is fully interactive
4. Can launch applications inside Windows session
5. Can disconnect cleanly and return to IGEL desktop

❌ **FAIL:**
- No RDP icon appears
- Clicking icon does nothing
- Connection fails or times out
- Windows desktop does not load
- Black screen or error messages
- Cannot disconnect properly

---

#### **TROUBLESHOOTING TIPS FOR BEGINNERS**

| Issue | Possible Cause | How to Fix |
|-------|----------------|------------|
| No RDP icon appears | Profile not applied / device not rebooted | Check UMS - is profile assigned? Reboot again |
| Connection fails | Windows server unreachable | Ping server IP from device via SSH: `ping server-ip` |
| Black screen after connection | Wrong credentials | Check RDP profile has correct username/password |
| "Certificate error" message | RDP certificate not trusted | Add certificate to IGEL or disable cert verification in profile |
| Keyboard/mouse not working in session | VNC focus issue | Click inside VNC window to ensure focus |

---

### **TC-010: Chromium Browser - App Upgrade and Downgrade**

#### **WHAT THIS TEST DOES**
Tests the ability to install, upgrade, and downgrade applications on IGEL devices using UMS profiles. Uses Chromium browser as the example application.

#### **WHY IS THIS IMPORTANT**
- Applications need updates for security and features
- Must be able to roll back if new version has issues
- Tests app lifecycle management (install → upgrade → downgrade)

#### **BACKGROUND CONCEPTS**

**Chromium Browser**: Open-source web browser (basis for Google Chrome). Available as an app package for IGEL OS.

**App Package**: Software bundled in a format IGEL can install. Think of it like an .exe file for Windows but for IGEL.

**igelpkgctl**: IGEL's package control tool (like "Add/Remove Programs" via command line). Lists installed apps and versions.

**Profile Version**: Each profile can specify which version of an app to install.

---

#### **PRECONDITIONS**

| # | Precondition | How to Verify | Explanation |
|---|--------------|---------------|-------------|
| 1 | IGEL OS 12 device registered in UMS | Device visible in UMS | Need manageable device |
| 2 | Two Chromium versions available in UMS | UMS → App Portal → Chromium shows multiple versions | Need Version A (older) and Version B (newer) |
| 3 | App profiles created for both versions | UMS → Profiles → "Chromium-VersionA-Profile" and "Chromium-VersionB-Profile" | Profiles specify different versions |
| 4 | SSH enabled on device | Can SSH to device | Need to verify installed version |

---

#### **TEST STEPS**

**STEP 1: Install Chromium Version A**

| Sub-Step | Action | Command/Details | Expected Outcome |
|----------|--------|-----------------|------------------|
| 1.1 | Assign Chromium Version A profile | `wums.assign_object(device_id, profile_a_id, "profile")` | Profile assigned in UMS |
| 1.2 | Reboot device | Wait 90 seconds | Device applies profile and installs app |
| 1.3 | SSH into device | `ssh root@device-ip` | Connected |
| 1.4 | List installed packages | `igelpkgctl list installed` | Shows all installed apps |
| 1.5 | Filter for Chromium | `igelpkgctl list installed \| grep chromium` | Shows Chromium entry |
| 1.6 | Verify version A is installed | Check version number in output | **EXPECTED**: Version A number visible (e.g., "chromium-91.0.4472") |

Example output:
```
chromium_91.0.4472-igel01_amd64
```

Understanding the output:
- `chromium` = package name
- `91.0.4472` = version number
- `igel01` = IGEL build number
- `amd64` = 64-bit architecture

**STEP 2: Upgrade to Chromium Version B**

| Sub-Step | Action | Details | Expected Outcome |
|----------|--------|---------|------------------|
| 2.1 | Assign Chromium Version B profile | This profile specifies newer version | Profile assigned |
| 2.2 | Reboot device | Wait 90 seconds | Device removes old version and installs new |
| 2.3 | SSH into device | Reconnect after reboot | Connected |
| 2.4 | Verify new version installed | `igelpkgctl list installed \| grep chromium` | **EXPECTED**: Version B number visible (e.g., "chromium-95.0.4638") |

Example output:
```
chromium_95.0.4638-igel02_amd64
```

Notice the version number changed from 91 to 95 (upgrade).

**STEP 3: Downgrade Back to Chromium Version A**

| Sub-Step | Action | Details | Expected Outcome |
|----------|--------|---------|------------------|
| 3.1 | Detach/unassign Version B profile | `wums.detach_profile(device_id, profile_b_id)` | Version B profile removed |
| 3.2 | Assign Version A profile again | Same profile as Step 1 | Version A profile assigned |
| 3.3 | Reboot device | Wait 90 seconds | Device downgrades to older version |
| 3.4 | Verify Version A restored | `igelpkgctl list installed \| grep chromium` | **EXPECTED**: Version A number back (91.0.4472) |

This proves you can roll back to previous versions if needed.

**STEP 4: Verify Application Functionality (Optional)**

| Sub-Step | Action | Expected Outcome |
|----------|--------|------------------|
| 4.1 | Open VNC shadow session | Can see device desktop |
| 4.2 | Double-click Chromium icon on desktop | Chromium browser launches |
| 4.3 | Navigate to a website (e.g., www.google.com) | Page loads correctly |
| 4.4 | Close Chromium | Application closes cleanly |

This verifies the installed version actually works.

**STEP 5: Cleanup (Uninstall All)**

| Sub-Step | Action | Expected Outcome |
|----------|--------|------------------|
| 5.1 | Detach all Chromium profiles | All profiles removed |
| 5.2 | Reboot device | Device uninstalls Chromium |
| 5.3 | Verify Chromium removed | `igelpkgctl list installed \| grep chromium` returns nothing |

---

#### **EXPECTED RESULTS**

✅ **PASS:**
1. Version A installs successfully and appears in `igelpkgctl` output
2. After upgrade assignment: Version B appears in output (A removed)
3. After downgrade: Version A appears in output again (B removed)
4. At each stage, only ONE version is installed (not multiple versions)
5. Application launches and works at each version

❌ **FAIL:**
- Package does not appear in installed list
- Wrong version number shows
- Multiple versions installed simultaneously (should only be one)
- Application doesn't launch after install
- Errors in `/var/log` during install/upgrade

---

#### **KEY COMMANDS FOR BEGINNERS**

```bash
# List all installed IGEL apps
igelpkgctl list installed

# Filter for specific app
igelpkgctl list installed | grep chromium

# View app details
igelpkgctl info chromium

# Check system logs for errors
journalctl -xe | tail -50

# View package installation log
cat /var/log/igelpkgctl.log
```

---

## 💡 RECOMMENDATIONS FOR BETTER BEGINNER UNDERSTANDING

### 1. **Add Visual Guides**
- Include screenshots for each major step
- Annotate images with arrows and labels
- Show "before" and "after" states

### 2. **Glossary of Terms**
Create a comprehensive glossary:
- **Thin Client**: Lightweight computer that relies on a server
- **Profile**: Configuration template applied to devices
- **Shadow Session**: Remote viewing of device screen
- **Bearer Token**: Authentication key for API access
- **SSH**: Secure command-line access
- **VNC**: Remote desktop viewing protocol
- **Kerberos**: Network authentication protocol
- **SSO**: Single Sign-On - one login for all services

### 3. **Pre-Test Validation Checklist**
Before running ANY test, verify:
```
□ UMS server is accessible (can login to web interface)
□ Device is online in UMS (green status indicator)
□ Device can be pinged from test machine
□ SSH works: ssh root@device-ip
□ VNC/Shadow opens successfully
□ Test credentials are valid and documented
□ Required profiles exist in UMS
```

### 4. **Common Error Messages and Solutions**

| Error | Meaning | Solution |
|-------|---------|----------|
| "Connection refused (port 22)" | SSH not enabled | Enable SSH via UMS profile |
| "Device not found" | Wrong hostname or not registered | Check device name in UMS |
| "Profile not found" | Wrong profile name | List profiles in UMS, copy exact name |
| "Authentication failed" | Wrong username/password | Verify credentials in config files |
| "Timeout waiting for reboot" | Device not rebooting or network issue | Check device power, network connection |

### 5. **Step-by-Step Setup Guide for New Testers**

**Day 1 - Environment Setup:**
1. Get UMS access credentials from admin
2. Identify test device and get hostname
3. Install Python and required packages
4. Configure config files with credentials
5. Test basic connectivity (ping, SSH, UMS login)

**Day 2 - First Test Execution:**
1. Start with simplest test (TC-026: SSH/VNC enablement)
2. Run test manually first, understand each step
3. Then run automated version
4. Compare manual vs automated results

**Day 3 - Understanding Profiles:**
1. Login to UMS web interface
2. Browse existing profiles
3. Understand profile types and structure
4. Create a simple test profile (e.g., wallpaper)

### 6. **Video Tutorials Structure**
Recommend creating video tutorials for:
- **Video 1**: "What is IGEL? - 5 Minute Overview"
- **Video 2**: "UMS Basics - Navigating the Interface"
- **Video 3**: "Your First Test - SSH and VNC Setup"
- **Video 4**: "Understanding Profiles and Assignment"
- **Video 5**: "SSO Testing - Complete Walkthrough"

### 7. **Hands-On Lab Exercises**
Create progressive exercises:

**Lab 1**: Device Discovery
- Find device in UMS
- Note MAC address, IP, hostname
- SSH to device and run `uname -a`

**Lab 2**: Profile Assignment (No Code)
- Manually assign wallpaper profile in UMS
- Reboot device via UMS
- Open shadow and verify wallpaper changed

**Lab 3**: First Automation Script
- Run existing test script
- Observe what happens in UMS and on device
- Read code line by line with explanations

### 8. **Quick Reference Card**
Create a one-page reference:

```
╔══════════════════════════════════════════════════════╗
║           IGEL TESTING QUICK REFERENCE               ║
╠══════════════════════════════════════════════════════╣
║ UMS WEB:    https://ums.company.com                  ║
║ Device IP:  192.168.1.100                            ║
║ SSH:        ssh root@192.168.1.100                   ║
║                                                      ║
║ COMMON COMMANDS:                                     ║
║ • igelpkgctl list installed    (list apps)          ║
║ • klist                        (check Kerberos)     ║
║ • df -h                        (disk space)         ║
║ • journalctl -xe               (system logs)        ║
║                                                      ║
║ REBOOT TIMES:                                        ║
║ • Normal reboot: ~60 seconds                        ║
║ • After profile change: ~90 seconds                 ║
║ • After app install: ~120 seconds                   ║
╚══════════════════════════════════════════════════════╝
```

### 9. **Test Execution Checklist Template**

```markdown
## Test Execution Log - TC-XXX

**Tester**: _________________
**Date**: _________________
**Device**: _________________

### Pre-Test Checks
- [ ] Device online in UMS
- [ ] SSH accessible
- [ ] VNC accessible
- [ ] Required profiles exist
- [ ] Test credentials documented

### Test Steps
- [ ] Step 1: [Description] - Result: ________
- [ ] Step 2: [Description] - Result: ________
- [ ] Step 3: [Description] - Result: ________

### Issues Encountered
1. _______________________________________________
2. _______________________________________________

### Screenshots Captured
- [ ] Before state
- [ ] After profile assignment
- [ ] Login screen
- [ ] Desktop loaded
- [ ] After cleanup

### Overall Result: PASS / FAIL
**Notes**: ________________________________
```

### 10. **Comparison with Familiar Concepts**

Help beginners by comparing to familiar technology:

| IGEL Concept | Like... | Explanation |
|--------------|---------|-------------|
| UMS | Microsoft SCCM / Intune | Central management for all devices |
| Profile | Group Policy | Settings that get applied to devices |
| Shadow Session | TeamViewer / Remote Desktop | See and control device remotely |
| SSH | Command Prompt / PowerShell | Terminal access to device |
| IGEL Device | Chromebook | Lightweight device for remote work |
| Profile Assignment | Installing an app via MDM | Push settings to device centrally |

---

## 📝 SUMMARY

### What Makes a Good Beginner-Friendly Test Case:

1. **Context First**: Explain WHAT and WHY before HOW
2. **No Assumptions**: Define every term, acronym, and concept
3. **Visual Aids**: Include screenshots, diagrams, expected outputs
4. **Step Granularity**: Break complex steps into sub-steps
5. **Verification at Each Step**: Don't wait until the end
6. **Common Pitfalls**: Warn about typical mistakes
7. **Troubleshooting Section**: "What if it doesn't work?"
8. **Real Examples**: Actual commands, outputs, screenshots
9. **Progressive Complexity**: Start simple, build to advanced
10. **Hands-On Practice**: Theory + practical exercises

### Key Improvements from Original Test Cases:

| Original | Improved |
|----------|----------|
| "Assign profile via UMS API" | Detailed table showing exact API calls, parameters, return values |
| "Verify login screen" | Screenshot + text description + what it means |
| "SSH enabled" | How to enable, how to test, what it does |
| "Reboot device" | How long it takes, what happens during reboot |
| Technical jargon | Plain language + technical term + explanation |

---

**Document Version**: 1.0  
**Last Updated**: April 27, 2026  
**For Questions Contact**: QA Team / Automation Team  
**Related Documents**: 
- IGEL_OS12_Test_Cases.csv (original test cases)
- config/all_conf.yaml (configuration reference)
- Framework documentation (API reference)
