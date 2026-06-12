/// SettingsView.swift
/// Settings screen — brain URL, port, and connectivity test.
///
/// The brain host and port are persisted via @AppStorage (UserDefaults).
/// Changing them rebuilds the BrainService's baseURL immediately.

import SwiftUI
import UserNotifications

struct SettingsView: View {
    @Environment(BrainService.self) private var brain

    @AppStorage(AppSettings.brainHostKey) private var brainHost = AppSettings.defaultBrainHost
    @AppStorage(AppSettings.brainPortKey) private var brainPort = AppSettings.defaultBrainPort

    @State private var editingHost: String = ""
    @State private var editingPort: String = ""
    @State private var isEditing: Bool = false
    @State private var showHealthResult: Bool = false
    @State private var healthResult: String = ""

    var body: some View {
        NavigationStack {
            Form {
                // --- Brain connection ---
                Section {
                    if isEditing {
                        TextField("Brain host", text: $editingHost)
                            .autocapitalization(.none)
                            .disableAutocorrection(true)
                            .keyboardType(.URL)
                            .accessibilityLabel("Brain hostname")

                        TextField("Port", text: $editingPort)
                            .keyboardType(.numberPad)
                            .accessibilityLabel("Brain port")
                    } else {
                        LabeledContent("Host", value: brainHost)
                        LabeledContent("Port", value: String(brainPort))
                    }
                } header: {
                    Text("Brain Connection")
                } footer: {
                    Text("Tailscale hostname of your Mac mini, e.g. mac-mini.frosty-llama.ts.net\nFind it with `tailscale status` on the Mac or in the Tailscale iOS app.")
                        .font(.caption)
                }

                // --- Edit / Save ---
                Section {
                    if isEditing {
                        Button("Save") {
                            saveSettings()
                        }
                        .bold()

                        Button("Cancel", role: .cancel) {
                            isEditing = false
                        }
                    } else {
                        Button("Edit connection") {
                            editingHost = brainHost
                            editingPort = String(brainPort)
                            isEditing   = true
                        }
                    }
                }

                // --- Connectivity test ---
                Section {
                    Button {
                        Task { await testConnection() }
                    } label: {
                        HStack {
                            Label("Test connection", systemImage: "network")
                            Spacer()
                            if brain.isCheckingHealth {
                                ProgressView()
                            }
                        }
                    }
                    .disabled(brain.isCheckingHealth)

                    if showHealthResult {
                        Text(healthResult)
                            .font(.caption)
                            .foregroundStyle(brain.isOnline ? .green : .red)
                    }
                } header: {
                    Text("Connectivity")
                }

                // --- Notification status ---
                Section {
                    NotificationStatusRow()
                } header: {
                    Text("Notifications")
                }

                // --- About ---
                Section {
                    LabeledContent("Design version", value: "1.2")
                    LabeledContent("iOS client", value: "1.0 (first draft)")
                    LabeledContent("Brain port", value: "8765")
                } header: {
                    Text("About")
                } footer: {
                    Text("Homunculus v1.0 — Mac-as-brain architecture.\nBrain: Qwen 2.5 7B via Ollama. Vault: ~/vault/.")
                        .font(.caption)
                }
            }
            .navigationTitle("Settings")
        }
    }

    // MARK: - Actions

    private func saveSettings() {
        guard !editingHost.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        let host = editingHost.trimmingCharacters(in: .whitespacesAndNewlines)
        let port = Int(editingPort) ?? AppSettings.defaultBrainPort
        brainHost    = host
        brainPort    = port
        brain.brainHost = host
        brain.brainPort = port
        isEditing    = false
        Task { await brain.checkHealth() }
    }

    private func testConnection() async {
        await brain.checkHealth()
        healthResult    = brain.isOnline
            ? "Connected ✓ — brain is online."
            : (brain.errorMessage ?? "Unreachable.")
        showHealthResult = true
    }
}

// MARK: - Notification status row

struct NotificationStatusRow: View {
    @State private var status: String = "Checking…"
    @State private var statusColor: Color = .secondary

    var body: some View {
        HStack {
            Label("Permission", systemImage: "bell.fill")
            Spacer()
            Text(status)
                .font(.caption)
                .foregroundStyle(statusColor)
        }
        .task { await checkPermission() }
    }

    private func checkPermission() async {
        let settings = await UNUserNotificationCenter.current().notificationSettings()
        switch settings.authorizationStatus {
        case .authorized, .provisional:
            status      = "Granted"
            statusColor = .green
        case .denied:
            status      = "Denied — open iOS Settings to allow"
            statusColor = .red
        case .notDetermined:
            status      = "Not requested yet"
            statusColor = .orange
        case .ephemeral:
            status      = "Ephemeral"
            statusColor = .secondary
        @unknown default:
            status      = "Unknown"
            statusColor = .secondary
        }
    }
}

#Preview {
    SettingsView()
        .environment(BrainService())
}
