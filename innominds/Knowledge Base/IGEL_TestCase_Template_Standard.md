# IGEL Test Case Template - Beginner-Friendly Format

**HOW TO USE THIS TEMPLATE**: Copy this entire template for each new test case. Fill in each section with detailed, beginner-friendly explanations. Assume the reader knows nothing about IGEL.

---

## **TC-XXX: [Test Case Title]**

---

### 📌 **QUICK SUMMARY**

**Test ID**: TC-XXX  
**Category**: [SSO / Session_Connection / App_Lifecycle / Device_Management]  
**Priority**: [High / Medium / Low]  
**Estimated Duration**: [X minutes]  
**Complexity**: [Beginner / Intermediate / Advanced]  
**Source Reference**: [QCL-XXXX / Documentation reference]  

**One-Sentence Description**:  
[What this test does in plain English - max 20 words]

Example: _"Verifies that device can log in users using Microsoft Entra ID instead of local passwords"_

---

### 🎯 **WHAT THIS TEST DOES**

[2-3 paragraphs explaining the test purpose in simple language]

**Format**:
- Paragraph 1: What is being tested (the feature/functionality)
- Paragraph 2: How it works (the technical process, explained simply)
- Paragraph 3: What outcome proves success

**Example**:
> This test verifies that an IGEL device can use Microsoft Entra ID (formerly Azure AD) for user authentication instead of local username/password combinations. This is called "Single Sign-On" (SSO) because users use the same credentials for all company services.
>
> When the test runs, we assign a special "Entra ID profile" to the device through UMS. This profile tells the device "instead of showing a local login screen, show Microsoft's login screen and authenticate users through Microsoft's cloud service." The device downloads these instructions, reboots, and reconfigures itself.
>
> Success is proven when: (1) Microsoft's login screen appears instead of local login, (2) users can successfully log in with their Microsoft credentials, and (3) the system creates a Kerberos security ticket proving authentication worked.

---

### 💡 **WHY IS THIS IMPORTANT**

[Explain business/practical value - why does anyone care about this test?]

**Answer these questions**:
- What problem does this feature solve?
- Who benefits from this (end users, IT admins, company)?
- What happens if this feature doesn't work?

**Example**:
> **Business Value**: Companies using Microsoft 365 need seamless integration with their IGEL devices. Employees want one set of credentials for everything (email, desktop, applications). SSO reduces password fatigue and support calls.
>
> **IT Admin Value**: Centralized identity management. Disable a Microsoft account once and user loses access to everything, including IGEL devices. No separate password management.
>
> **Security Value**: Multi-factor authentication (MFA) can be enforced at the Microsoft level. Stronger security than local passwords.
>
> **If This Fails**: Users would need separate login credentials for IGEL devices, creating security gaps, management overhead, and poor user experience.

---

### 📚 **BACKGROUND CONCEPTS FOR BEGINNERS**

[Define all technical terms used in this test. No assumptions!]

**Format**: Create a glossary of 3-8 key terms

#### **Term 1: [Concept Name]**
**Simple Definition**: [One sentence]  
**Detailed Explanation**: [2-3 sentences]  
**Real-World Analogy**: [Compare to something familiar]  
**Example**: [Concrete example]

**Template Examples**:

#### **Entra ID (Microsoft Identity Platform)**
**Simple Definition**: Microsoft's cloud-based login and identity management service.

**Detailed Explanation**: When you sign into Microsoft 365, Teams, Azure, or other Microsoft services, Entra ID verifies your identity. It's the central "gatekeeper" that checks if your username and password are correct, and optionally requires additional verification (like a code from your phone).

**Real-World Analogy**: Like a bouncer at a club who checks your ID and decides if you can enter. Once you're approved, you get a wristband (security token) that lets you access different areas (services) without showing ID again.

**Example**: When you type `john.doe@company.com` and your password to login to Outlook, Entra ID is the system verifying those credentials.

---

#### **Kerberos Ticket**
**Simple Definition**: A digital security token that proves you've been authenticated.

**Detailed Explanation**: After successful login, the system creates a "ticket" - a small encrypted file that says "this user has been verified." Applications and services check this ticket instead of asking for your password again. The ticket expires after a set time (usually 10-12 hours).

**Real-World Analogy**: Like a day pass at an amusement park. You show your ID once at the entrance, get a wristband (ticket), and then just show the wristband to enter different rides without showing ID repeatedly.

**Example**: After logging into Windows with a domain account, you get a Kerberos ticket. When you access a network file share, it checks your ticket instead of asking for your password again.

---

#### **Profile (UMS Profile)**
**Simple Definition**: A saved configuration template that can be applied to devices.

**Detailed Explanation**: Instead of manually configuring each device (imagine doing this for 500 devices!), you create a "profile" once in UMS with all the settings. Then you "assign" this profile to devices, and they automatically download and apply those settings. It's like mass-emailing a document instead of printing and hand-delivering 500 copies.

**Real-World Analogy**: Like a recipe. You write the recipe once, then anyone following it gets the same dish. Similarly, create a profile once, apply to many devices, all get same configuration.

**Example**: "Sales-Team-Profile" might include: Microsoft login, Edge browser installation, company wallpaper, and RDP connection to sales server. Assign this profile to all 50 sales team devices at once.

---

### ✅ **PRECONDITIONS** (What Must Be Ready BEFORE Test)

[List and explain everything that must be set up before starting]

**Format**: Table with verification steps and explanations

| # | Precondition | How to Verify | What It Means | If Not Met |
|---|--------------|---------------|---------------|------------|
| 1 | [Requirement] | [Steps to check] | [Why this matters] | [What happens if missing] |

**Example**:

| # | Precondition | How to Verify | What It Means | If Not Met |
|---|--------------|---------------|---------------|------------|
| 1 | IGEL OS 12 device registered in UMS | Login to UMS → Devices → Search for device name → Device appears in tree | Device is known to UMS and can be managed remotely. "Registered" means the device has contacted UMS and is accepted into management. | Test cannot proceed. Device won't receive profile assignments. Must register device first. |
| 2 | Entra ID SSO profile exists in UMS | UMS → Profiles → Search "Entra-ID-SSO-Profile" → Profile found | An administrator has already created this profile with Microsoft tenant details, authentication URLs, and configuration. This test doesn't create profiles; it tests applying existing ones. | Test will fail at assignment step. Admin must create profile first using Microsoft tenant information. |
| 3 | UMS bearer token available | Check `config/all_conf.yaml` → `bearer_token: "eyJhbG..."` entry exists and is recent (not expired) | API authentication key allowing test scripts to communicate with UMS programmatically. Like a password for scripts. Expires after 24 hours typically. | API calls will fail with "Unauthorized" error. Must generate new token from UMS Web → Admin → API Tokens. |
| 4 | SSH enabled on device | From command line: `ssh root@device-ip` → Able to login without "Connection refused" | Remote command-line access is enabled in device settings. Required to verify configurations, check logs, and validate test results. | Cannot verify Kerberos tickets, check logs, or troubleshoot. Must enable SSH via UMS profile or device local settings. |
| 5 | VNC/Shadow enabled | UMS → Select device → Click "Shadow" → Shadow window opens showing device screen | Remote desktop viewing is enabled. Allows seeing device screen to verify login screens, desktop loaded, etc. | Cannot visually verify test outcomes. Must enable VNC/Shadowing in UMS device settings. |
| 6 | Valid Entra ID test user credentials | Have: `testuser@company.com`, password, and MFA secret (if MFA required) → Can login at portal.office.com successfully | A real Microsoft account exists for testing. Password is not expired. MFA is configured and accessible. | Cannot complete authentication steps. Test will fail at login. Must coordinate with Microsoft admin for test account. |
| 7 | Device has network access to Microsoft | From device SSH: `ping login.microsoftonline.com` → Receives replies | Device can reach Microsoft authentication servers over the internet. No firewall blocking. | Authentication will fail with timeout. Device cannot contact Microsoft. Must check firewall rules and internet access. |

**Verification Checklist** (Use before starting test):
```
□ Precondition 1: Verified - [Date/Time]
□ Precondition 2: Verified - [Date/Time]
□ Precondition 3: Verified - [Date/Time]
□ Precondition 4: Verified - [Date/Time]
□ Precondition 5: Verified - [Date/Time]
□ Precondition 6: Verified - [Date/Time]
□ Precondition 7: Verified - [Date/Time]

All verified by: [Your Name]
Ready to proceed: YES / NO
```

---

### 🧪 **TEST ENVIRONMENT SETUP**

[Describe the physical and logical setup needed]

#### **Hardware Requirements**:
- IGEL Device: [Model or specs]
- Monitor: [Any special requirements?]
- Network: [Wired/Wireless/VPN needed?]

#### **Software Requirements**:
- IGEL OS Version: 12.x.x or higher
- UMS Version: 12.x.x or higher
- Test Tools: [Python, VNC viewer, SSH client, etc.]

#### **Network Requirements**:
- Device to UMS: [Port requirements]
- Device to Internet: [For cloud services]
- Tester to Device: [SSH port 22, VNC port 5900]

#### **Test Data Requirements**:
- Configuration files: [`testdata/sso/api_config.yaml`]
- Credentials: [What needs to be configured]
- Profile names: [Exact names in UMS]

**Configuration File Example**:
```yaml
# testdata/sso/api_config.yaml
igel:
  entra_id_profile: "Entra-ID-SSO-Profile"  # Must match UMS profile name exactly
  entra_username: "testuser@company.com"     # Test user email
  entra_password: "Test@Pass123"             # Test user password
  entra_otp_secret: "BASE32SECRET..."        # TOTP secret for MFA
```

---

### 📋 **TEST STEPS** (Detailed Walkthrough)

[Break down test into major steps, then sub-steps, with explanations]

**Format**: Each step should have:
1. Step number and title
2. Objective (what are we trying to achieve)
3. Sub-steps table with details
4. Expected outcome
5. Troubleshooting tips
6. Screenshot reference

---

#### **STEP 1: [Step Title]**

**Objective**: [What this step accomplishes]

**Time Required**: [Estimated minutes]

**Prerequisites for This Step**: [Anything specific needed before this step]

##### **Sub-Steps**:

| Sub-Step | Action | How to Perform | Technical Details | Expected Immediate Result | How to Verify |
|----------|--------|----------------|-------------------|---------------------------|---------------|
| 1.1 | [Action name] | [User instructions] | [What happens behind the scenes] | [What you see/get] | [How to confirm it worked] |

**Detailed Example**:

| Sub-Step | Action | How to Perform | Technical Details | Expected Immediate Result | How to Verify |
|----------|--------|----------------|-------------------|---------------------------|---------------|
| 1.1 | Initialize UMS API connection | In Python script: `ums = UMS(base_url, username, password)` | Creates authenticated session with UMS server using REST API. Sends credentials and receives session token. | No error message. Variable `ums` contains connection object. | Check: `print(ums)` shows object, not error. Or API call succeeds. |
| 1.2 | Retrieve device details | Call: `device = ums.get_vm_details("IGEL-QA-001")` | Queries UMS database for device matching hostname. Returns device object with ID, MAC, IP, status, etc. | Variable `device` is dictionary/object with device info. `device["id"]` exists. | Print: `print(device["id"])` shows numeric ID (e.g., 12345). Check: `device["online"]` is True. |
| 1.3 | Get Entra ID profile | Call: `profile = ums.get_profile_details("Entra-ID-SSO-Profile")` | Searches UMS profile database for profile matching exact name. Returns profile object with ID and settings. | Variable `profile` contains profile object. `profile["id"]` exists. | Print: `print(profile["name"])` shows "Entra-ID-SSO-Profile". Check profile type is correct. |
| 1.4 | Assign profile to device | Call: `wums.assign_object(device["id"], profile["id"], "profile")` | Sends API command to UMS: "Link profile to device". Creates assignment entry in database. Device will download on next check-in. | API returns success (True or HTTP 200). No error exception thrown. | Check in UMS Web: Device → Assigned Profiles shows profile name. Green checkmark indicates assignment. |
| 1.5 | Trigger device reboot | Call: `ums.device_reboot(device)` | Sends shutdown command to device via UMS. Device initiates clean shutdown and restart process. | API returns success. Device status in UMS changes to "Rebooting". | Wait 10 sec → UMS shows device "Offline". Wait 80 sec more → Device "Online" again. |

##### **Expected Outcome After Step 1**:
[What should be true after ALL sub-steps complete]

Example:
✅ After Step 1 completion:
- Profile is assigned to device (visible in UMS)
- Device has rebooted and is back online
- Device is ready to display new login screen
- Total time elapsed: ~100 seconds

##### **Visual Confirmation**:
[Describe what you should see in UMS or on device]

Example:
> In UMS Web Interface:
> - Device → Assigned Profiles → Shows "Entra-ID-SSO-Profile" with green checkmark
> - Device status: Green icon (Online)
> - Last Contact: Shows timestamp within last 60 seconds

##### **Troubleshooting This Step**:

| Problem | Symptoms | Possible Cause | Solution |
|---------|----------|----------------|----------|
| API connection fails | Error: "Connection refused" or "Unauthorized" | Invalid credentials or token expired | Verify UMS URL is correct. Check username/password. Regenerate bearer token. |
| Device not found | Error: "Device 'IGEL-QA-001' not found" | Wrong hostname or device not registered | Check exact device name in UMS (case-sensitive). Verify device is registered. |
| Profile not found | Error: "Profile not found" | Wrong profile name or doesn't exist | List all profiles in UMS. Copy exact name (case-sensitive). Verify profile type. |
| Assignment fails | Error: "Assignment failed" or no error but not assigned | Permission issue or UMS busy | Check user has assignment rights. Wait 30 sec and retry. Check UMS server load. |
| Device won't reboot | Device stays online, no reboot | Reboot command failed or device hung | Try manual reboot from UMS Web. If fails, physical power cycle. |

##### **Screenshots for Step 1**:
- `TC-XXX-Step1-Before.png`: UMS showing device before assignment
- `TC-XXX-Step1-Assignment.png`: Profile assignment dialog
- `TC-XXX-Step1-After.png`: Device with profile assigned
- `TC-XXX-Step1-Rebooting.png`: Device status during reboot

---

#### **STEP 2: [Next Step Title]**

[Repeat same detailed format for each step]

---

### ✅ **EXPECTED RESULTS** (Success Criteria)

[Define clear pass/fail conditions]

#### **Test Passes IF AND ONLY IF ALL of These Are True**:

| # | Criterion | How to Verify | Why This Matters |
|---|-----------|---------------|------------------|
| 1 | [Specific measurable condition] | [Verification method] | [Importance] |

**Example**:

| # | Criterion | How to Verify | Why This Matters |
|---|-----------|---------------|------------------|
| 1 | Microsoft login screen appears after device reboot | Open VNC shadow → Look for text "Microsoft", "Sign in", or Entra ID logo | Proves profile was applied and device reconfigured for Entra ID auth |
| 2 | User can successfully login with Microsoft credentials | Enter username/password/MFA → Desktop loads without errors | Proves authentication flow works end-to-end |
| 3 | Kerberos ticket is present after login | SSH to device → Run `klist` → Output shows "Ticket cache" with user principal | Proves SSO integration is complete and secure authentication established |
| 4 | No critical errors in authentication logs | SSH → `grep -i error /var/log/auth.log` → No "authentication failed" errors for test user | Proves no backend authentication issues |
| 5 | Desktop loads within 30 seconds of login | Time from pressing Enter on password to seeing desktop | Proves performance is acceptable |
| 6 | After cleanup: local login restored | Unassign profile → Reboot → VNC shows local login (not Microsoft) | Proves cleanup successful and device not left in invalid state |

**CRITICAL RULE**: If ANY criterion is not met → **TEST FAILS**. Document which criterion failed and why.

---

#### **Test FAILS IF ANY of These Occur**:

| # | Failure Condition | Severity | What It Indicates |
|---|-------------------|----------|-------------------|
| 1 | [Specific failure scenario] | [Critical/Major/Minor] | [Root cause / Concern] |

**Example**:

| # | Failure Condition | Severity | What It Indicates |
|---|-------------------|----------|-------------------|
| 1 | Microsoft login screen does NOT appear | Critical | Profile not applied OR device not communicating with Entra ID OR network blocked |
| 2 | Cannot enter credentials (keyboard frozen) | Critical | VNC/Shadow issue OR device frozen |
| 3 | Login succeeds but desktop never loads | Critical | User profile corruption OR session startup failure |
| 4 | `klist` shows "No credentials cache" | Major | Kerberos integration broken OR SSO not properly configured |
| 5 | Login takes more than 60 seconds | Minor | Performance issue OR network latency, but functionality works |
| 6 | Device does not return to local login after cleanup | Major | Cleanup procedure incomplete OR profile remnants remain |

**Failure Triage**:
- **Critical**: Test completely fails, feature doesn't work. Stop testing, escalate.
- **Major**: Feature partially works but missing key functionality. Document and continue.
- **Minor**: Feature works but has issues (performance, cosmetic). Note and continue.

---

### 📊 **TEST METRICS** (Optional but Recommended)

[Measurable aspects of the test]

| Metric | Target | How to Measure | Acceptable Range |
|--------|--------|----------------|------------------|
| Reboot time after profile assignment | 90 sec | Time from reboot command to device online in UMS | 60-120 seconds |
| Login screen appearance time | 3 sec | Time from device boot complete to login screen rendered | 1-10 seconds |
| Authentication time | 5 sec | Time from pressing Enter on password to "authenticating" disappears | 2-15 seconds |
| Desktop load time | 10 sec | Time from successful auth to desktop fully rendered | 5-30 seconds |
| Kerberos ticket validity | 10 hours | `klist` output shows expiration time | Must be > 8 hours |
| SSH command response time | 1 sec | Time from Enter to command output | < 3 seconds |

---

### 🧹 **CLEANUP PROCEDURE** (Return to Normal State)

[Detailed steps to undo test changes]

**Why Cleanup Matters**: Tests should not leave devices in modified state. Next test should start with "clean slate."

**Cleanup Verification Checklist**:
```
□ All test profiles unassigned from device
□ Device rebooted to default configuration
□ Device shows local login (not test SSO provider)
□ No test data remains on device
□ Device back online in UMS
□ Ready for next test
```

**Detailed Cleanup Steps**:

| Step | Action | Verification |
|------|--------|--------------|
| 1 | Unassign test profile(s) | UMS shows no profile assigned to device |
| 2 | Reboot device | Device goes offline then online again |
| 3 | Verify default state | Open VNC → See local login screen |
| 4 | Clear test data (if any) | SSH → Remove test files from `/tmp/` or `/wfs/` |
| 5 | Check logs for cleanup errors | `journalctl -xe` shows no errors during cleanup |
| 6 | Verify device usable | Quick test: SSH works, Shadow works |

**If Cleanup Fails**:
1. Retry cleanup steps manually via UMS Web
2. If still failing, perform factory reset (last resort)
3. Re-register device in UMS
4. Document cleanup failure in test report

---

### 🔧 **TROUBLESHOOTING GUIDE**

[Common issues and solutions specific to this test]

#### **Issue 1: [Common Problem]**

**Symptoms**:
- [What you observe]
- [Error messages]

**Possible Causes**:
1. [Root cause option 1]
2. [Root cause option 2]

**Diagnostic Steps**:
1. [How to investigate]
2. [What to check]

**Solutions**:
1. **If cause is X**: [Detailed fix]
2. **If cause is Y**: [Detailed fix]

**Prevention**:
[How to avoid this issue in future]

---

### 📷 **VISUAL GUIDE** (Screenshots and Diagrams)

[Include or reference visual aids]

**Required Screenshots**:
1. **Pre-Test State**: Device before test (UMS view + VNC)
2. **Profile Assignment**: UMS showing profile being assigned
3. **Key Test Moments**: Login screen, authentication in progress, desktop loaded
4. **Verification**: SSH output showing verification commands
5. **Post-Test State**: Device after cleanup (back to normal)

**Helpful Diagrams**:
- Flow diagram: Step-by-step test flow
- Network diagram: Components and connections
- Decision tree: Troubleshooting flowchart

---

### 🤖 **AUTOMATION NOTES**

[Technical details for test automation]

#### **Python Functions Used**:
- `UMS()`: [What it does]
- `UMSWUMSApi()`: [What it does]
- `get_vm_details()`: [What it does]
- [List all functions with brief explanations]

#### **Configuration Files**:
- `config/all_conf.yaml`: [What's needed in this file]
- `testdata/sso/api_config.yaml`: [What's needed here]

#### **External Dependencies**:
- Libraries: [List Python packages]
- Services: [External services test depends on]

#### **Automation Challenges**:
[Things to be aware of when automating]
1. [Challenge 1 and workaround]
2. [Challenge 2 and workaround]

#### **Manual Steps (Cannot Be Automated)**:
[Steps that require human interaction]
1. [Step and reason why manual]

---

### 📝 **TEST EXECUTION LOG TEMPLATE**

[Template for documenting test run]

```
╔══════════════════════════════════════════════════════╗
║           TEST EXECUTION REPORT                      ║
╠══════════════════════════════════════════════════════╣
║ Test ID: TC-XXX                                      ║
║ Test Name: [Full Name]                               ║
║ Tester: [Your Name]                                  ║
║ Execution Date: [YYYY-MM-DD HH:MM]                   ║
║ Device: [Hostname] ([IP Address])                    ║
║ Device OS: IGEL OS [Version]                         ║
║ UMS Version: [Version]                               ║
╠══════════════════════════════════════════════════════╣
║ PRE-TEST VERIFICATION                                ║
║ □ Precondition 1: [Status] - Notes: [...]           ║
║ □ Precondition 2: [Status] - Notes: [...]           ║
║ [... all preconditions ...]                          ║
║                                                      ║
║ All Preconditions Met: YES / NO                      ║
║ If NO, test should not proceed.                      ║
╠══════════════════════════════════════════════════════╣
║ TEST STEPS EXECUTION                                 ║
║                                                      ║
║ STEP 1: [Title]                                      ║
║   Started: [HH:MM]                                   ║
║   Result: PASS / FAIL / BLOCKED                      ║
║   Duration: [X minutes]                              ║
║   Notes: [Any observations]                          ║
║                                                      ║
║ STEP 2: [Title]                                      ║
║   Started: [HH:MM]                                   ║
║   Result: PASS / FAIL / BLOCKED                      ║
║   Duration: [X minutes]                              ║
║   Notes: [Any observations]                          ║
║                                                      ║
║ [... all steps ...]                                  ║
╠══════════════════════════════════════════════════════╣
║ EXPECTED RESULTS VERIFICATION                        ║
║ □ Criterion 1: MET / NOT MET - [Details]            ║
║ □ Criterion 2: MET / NOT MET - [Details]            ║
║ [... all criteria ...]                               ║
╠══════════════════════════════════════════════════════╣
║ ISSUES / DEFECTS FOUND                               ║
║                                                      ║
║ Issue #1:                                            ║
║   Description: [What went wrong]                     ║
║   Severity: Critical / Major / Minor                 ║
║   Steps to Reproduce: [How to see the issue]        ║
║   Screenshot: [Filename]                             ║
║   Workaround: [If found]                             ║
║                                                      ║
║ [... additional issues ...]                          ║
║                                                      ║
║ Total Issues Found: [#]                              ║
╠══════════════════════════════════════════════════════╣
║ PERFORMANCE METRICS                                  ║
║ Reboot Time: [X sec] (Target: 90 sec)               ║
║ Login Time: [X sec] (Target: 5 sec)                 ║
║ [... other metrics ...]                              ║
╠══════════════════════════════════════════════════════╣
║ CLEANUP                                              ║
║ □ Profiles unassigned: YES / NO                      ║
║ □ Device rebooted: YES / NO                          ║
║ □ Default state verified: YES / NO                   ║
║ Cleanup Successful: YES / NO                         ║
╠══════════════════════════════════════════════════════╣
║ OVERALL TEST RESULT                                  ║
║                                                      ║
║   [X] PASS  [ ] FAIL  [ ] BLOCKED                    ║
║                                                      ║
║ Confidence Level: High / Medium / Low                ║
║                                                      ║
║ Additional Comments:                                 ║
║ ________________________________________________     ║
║ ________________________________________________     ║
║ ________________________________________________     ║
╠══════════════════════════════════════════════════════╣
║ ATTACHMENTS                                          ║
║ □ Screenshots: [List filenames]                      ║
║ □ Log files: [List filenames]                        ║
║ □ Video recording: [Filename]                        ║
╠══════════════════════════════════════════════════════╣
║ SIGN-OFF                                             ║
║ Tested By: ________________ Date: __________         ║
║ Reviewed By: ______________ Date: __________         ║
╚══════════════════════════════════════════════════════╝
```

---

### 🔗 **RELATED INFORMATION**

**Related Test Cases**:
- [TC-XXX]: [Relationship]
- [TC-XXX]: [Relationship]

**Related Documentation**:
- [Document name]: [What it covers]
- [KB article]: [Relevant section]

**Jira/Issue Tracking**:
- QCL-XXXX: [Original requirement]
- BUG-XXXX: [Known issues]

**Training Materials**:
- [Video link]: [Description]
- [Document]: [Tutorial]

---

### 📧 **QUESTIONS AND SUPPORT**

**For Questions About This Test**:
- Contact: [Test Owner Name]
- Email: [email]
- Slack: [channel]

**For IGEL Environment Issues**:
- UMS Admin: [Name/Contact]
- Device Support: [Name/Contact]

**For Test Framework Issues**:
- Automation Team: [Contact]
- Documentation: [Link]

---

**Template Version**: 1.0  
**Last Updated**: April 27, 2026  
**Maintained By**: QA Team  
**Template Source**: IGEL_Testing_QuickStart_Guide.md
