/// ContentView.swift
/// Root navigation container.
/// Uses NavigationStack with a tab-style bottom bar for:
///   - Capture (main)
///   - Today's events
///   - Settings

import SwiftUI

struct ContentView: View {
    @Environment(BrainService.self) private var brain

    var body: some View {
        TabView {
            CaptureView()
                .tabItem {
                    Label("Capture", systemImage: "mic.fill")
                }

            TodayView()
                .tabItem {
                    Label("Today", systemImage: "calendar")
                }

            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gear")
                }
        }
        .overlay(alignment: .top) {
            if !brain.isOnline && !brain.isCheckingHealth {
                OfflineBanner()
            }
        }
    }
}

// MARK: - Offline Banner

struct OfflineBanner: View {
    @Environment(BrainService.self) private var brain

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "wifi.slash")
            Text(brain.errorMessage ?? "Homunculus offline")
                .font(.caption)
            Spacer()
            Button("Retry") {
                Task { await brain.checkHealth() }
            }
            .font(.caption.bold())
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(.red.opacity(0.9))
        .foregroundStyle(.white)
    }
}

#Preview {
    ContentView()
        .environment(BrainService())
}
