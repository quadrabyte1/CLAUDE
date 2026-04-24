# GoButton

A minimal SwiftUI demo. One screen, one round red button. Tap it — the background fades to light blue. Tap again to toggle back.

## What it does

- Red circular button (140pt) centered on screen, white bold "Go" label.
- Tapping toggles a light-blue background with a smooth 0.35s ease-in-out animation.
- VoiceOver-friendly: accessibility label and dynamic hint reflect the current state.

## Running on your iPhone (≈2 minutes)

1. **Open the project** — double-click `GoButton.xcodeproj`. Xcode opens with the GoButton scheme already selected.
2. **Set up signing** — click the **GoButton** project in the navigator (top of the left panel) → select the **GoButton** target → **Signing & Capabilities** tab → check **Automatically manage signing** → choose your **Team** (your Apple ID; add one in Xcode → Settings → Accounts if needed) → change the Bundle Identifier to something unique, e.g. `com.yourname.GoButton`.
3. **Run on your phone** — plug in your iPhone, select it in the device dropdown at the top of Xcode, then press **▶ (⌘R)**.
4. **Trust the certificate (first launch only)** — if iOS shows "Untrusted Developer", go to **Settings → General → VPN & Device Management** → tap your Apple ID → **Trust**.
5. **Free Apple ID note** — apps signed with a free account expire after 7 days. Just rebuild (⌘R) to refresh.

## Requirements

- Xcode 15 or later
- iOS 17.0+ deployment target
- No third-party dependencies
