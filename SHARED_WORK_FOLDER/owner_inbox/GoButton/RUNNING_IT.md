# Running GoButton — Thomas's Walkthrough

Hey Thomas — here's how to get GoButton in front of you, two ways. Start with Path A. It takes two minutes and doesn't require your iPhone or any Apple account setup. Path B is where you'll learn what every iOS developer learns eventually: code signing, trust dialogs, and the fun of Apple's free provisioning limits.

---

## Path A — Run in the iOS Simulator (easiest, ~2 minutes, no iPhone needed)

### Option 1: Open in Xcode (the normal way)

**Step 1.** Open the project in Xcode. Run this in Terminal:

```bash
open /Users/fourierflight/GIT/CLAUDE-GitHub/SHARED_WORK_FOLDER/owner_inbox/GoButton/GoButton.xcodeproj
```

Xcode will launch and load the project.

**Step 2.** In the Xcode toolbar at the top — next to the ▶ Run button and the scheme name ("GoButton") — there's a destination picker showing a device or simulator name. Click it and select **"iPhone 17 Pro"** (or any iPhone simulator in the list).

**Step 3.** Press **⌘R** (or click the ▶ Run button). Xcode will build the app, the Simulator app will open, and GoButton will launch on the simulated iPhone.

**Step 4.** Click the big red button. Background goes light blue. Click it again — back to white. That's the whole app — it's a proof of concept, not a product.

**Step 5.** To stop: press **⌘.** in Xcode, or just close the Simulator window.

---

### Option 2: Terminal only (no Xcode UI needed — the way I verified the build)

This is how I confirmed the build works. It's useful to understand because `xcodebuild` is how CI/CD pipelines build apps without a human clicking buttons.

```bash
cd /Users/fourierflight/GIT/CLAUDE-GitHub/SHARED_WORK_FOLDER/owner_inbox/GoButton

# Build the app
xcodebuild -project GoButton.xcodeproj -scheme GoButton \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  CODE_SIGNING_ALLOWED=NO build

# Boot the simulator (safe to run even if already booted)
xcrun simctl boot "iPhone 17 Pro" 2>/dev/null

# Open the Simulator UI so you can see it
open -a Simulator

# Install the app onto the booted simulator
xcrun simctl install booted \
  ~/Library/Developer/Xcode/DerivedData/GoButton-*/Build/Products/Debug-iphonesimulator/GoButton.app

# Launch it
xcrun simctl launch booted com.example.GoButton
```

The `xcrun simctl` commands are Apple's command-line tools for controlling simulators. `simctl install` is doing the same thing Xcode does when it deploys to a device — just without the GUI.

---

## Path B — Install on your physical iPhone (~15 minutes first time)

**What you need:** your iPhone, a USB-C or Lightning cable, and a free Apple ID (your normal one is fine).

**Step 1 — Connect your iPhone to your Mac.** Plug it in with the cable. The first time you connect, your iPhone will pop up an alert: **"Trust This Computer?"** — tap **Trust** and enter your passcode. If you've connected this Mac before, it'll skip this.

**Step 2 — Enable Developer Mode on your iPhone.** This is required on iOS 16 and later. Apple hides it by default because most people don't need it.
- On your iPhone: **Settings → Privacy & Security → Developer Mode → toggle it On**
- iPhone will warn you about security — tap **Restart**
- After reboot, it'll ask you to confirm enabling Developer Mode — tap **Turn On** and enter your passcode

**Step 3 — Open the project in Xcode.** Same as Path A, Step 1:

```bash
open /Users/fourierflight/GIT/CLAUDE-GitHub/SHARED_WORK_FOLDER/owner_inbox/GoButton/GoButton.xcodeproj
```

**Step 4 — Set your Team (code signing).** Every app that runs on a real iPhone must be signed by a developer certificate. For personal testing, a free Apple ID is enough.

- In the left sidebar, click the **GoButton** project (the top item with the Xcode icon)
- In the main area, click the **GoButton** target (under "Targets")
- Click the **"Signing & Capabilities"** tab
- Check **"Automatically manage signing"**
- In the **Team** dropdown: if your Apple ID isn't there, click **"Add an Account…"**, sign in, then come back and select your account. It'll show as **"(Personal Team)"** — that's correct.

**Step 5 — Change the Bundle Identifier.** Apple requires every app to have a unique bundle ID. The current one (`com.example.GoButton`) is a placeholder that will be rejected. Change it to something that's yours.

- Still on the "Signing & Capabilities" tab, find **"Bundle Identifier"**
- Change `com.example.GoButton` to something like `com.fourierflight.GoButton`

**Step 6 — Select your iPhone as the destination.** In the Xcode toolbar destination picker (same place as Step 2 of Path A), your iPhone should now appear by name — something like "Thomas's iPhone." Select it.

If it doesn't appear: check that Developer Mode is on (Step 2), the cable is plugged in, and you tapped Trust on the phone.

**Step 7 — Hit ▶ Run (⌘R).** Xcode builds, signs the app with your personal certificate, and installs it on your iPhone. You'll see the progress in the Xcode status bar at the top.

**Step 8 — Trust yourself on the iPhone.** The first time you run an app signed with a personal (non-App Store) certificate, iOS blocks it with "Untrusted Developer." This is expected — Apple wants you to explicitly say "yes, I trust this developer."

On your iPhone: **Settings → General → VPN & Device Management → (your Apple ID) → Trust**

Then go back to the home screen and tap the GoButton icon. It'll open.

**Step 9 — It runs.** Same experience as the simulator — red button, blue background.

**One thing to know about free accounts:** Personal provisioning profiles expire after **7 days**. After a week, the app will stop launching on your phone with a "profile expired" error. To fix it: plug in your iPhone, hit ⌘R in Xcode again, and it re-signs with a fresh certificate. Paid Apple Developer Program accounts ($99/year) extend this to a year and are required to submit to the App Store.

---

## Which path should you start with?

**Path A first.** It's 2 minutes, no Apple account setup, no cable. It validates that the app works and gives you a feel for the build-and-run loop that iOS developers do dozens of times a day.

Path B is worth doing once because it teaches you what's actually happening under the hood when an app ships: code signing, provisioning, trust chains. Every iOS developer has hit every one of those friction points. Better to learn them on a 40-line demo app than on something you care about.

---

## Troubleshooting

| Problem | What's happening | Fix |
|---|---|---|
| "No devices available" in destination picker | iPhone trust or Developer Mode issue | Re-check Step 1 and Step 2 of Path B |
| "Failed to verify code signature" on phone | You haven't trusted your developer profile | Path B, Step 8 |
| "Bundle identifier is not available" | The ID `com.example.GoButton` is taken or blocked | Path B, Step 5 — change the bundle ID |
| Xcode complains about missing simulator runtime | iOS 26.4 simulator isn't installed | Xcode → Settings → Platforms → install iOS 26.4 |
| App worked, now won't launch after a week | Free provisioning profile expired | Plug in iPhone, hit ⌘R in Xcode to re-sign |

---

— Kit
