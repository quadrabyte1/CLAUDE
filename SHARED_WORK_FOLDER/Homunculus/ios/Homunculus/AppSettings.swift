/// AppSettings.swift
/// @AppStorage-backed settings.  Centralises all UserDefaults keys.
///
/// The brain host defaults to a placeholder so the boss knows where to look.
/// On first launch, the Settings screen prompts for the real tailnet hostname.

import Foundation
import SwiftUI

enum AppSettings {
    // MARK: - Keys (keep alphabetical)

    static let brainHostKey = "brain_host"
    static let brainPortKey = "brain_port"

    // MARK: - Defaults

    /// Placeholder the boss should replace with his Tailscale hostname.
    /// Tailscale typically assigns hostnames in the form:
    ///   mac-mini.<tailnet-name>.ts.net
    /// Find it with `tailscale status` on the Mac or in the Tailscale iOS app.
    static let defaultBrainHost = "mac-mini.REPLACEME.ts.net"
    static let defaultBrainPort = 8765
}

// MARK: - AppStorage Helpers

/// Convenience struct that owns all @AppStorage bindings.
/// Inject into the environment with .environment(\.appSettings, AppStorageSettings())
/// or access via @Environment(\.appSettings).
struct AppStorageSettings {
    @AppStorage(AppSettings.brainHostKey)
    var brainHost: String = AppSettings.defaultBrainHost

    @AppStorage(AppSettings.brainPortKey)
    var brainPort: Int = AppSettings.defaultBrainPort
}
