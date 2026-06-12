/// ConfirmationSheet.swift
/// Shown when the brain returns action: "needs_confirmation".
///
/// Displays the brain's spoken_reply (which already ends with "Sound right?"
/// or "Save anyway?") and provides large accessible confirm / cancel buttons.
///
/// Per the spec, conflict info is displayed here too.

import SwiftUI

struct ConfirmationSheet: View {
    @Environment(BrainService.self) private var brain
    let onConfirm: () -> Void
    let onCancel: () -> Void

    var body: some View {
        NavigationStack {
            VStack(spacing: 32) {
                Spacer()

                // Brain's readback message
                if let response = brain.lastCaptureResponse {
                    VStack(spacing: 16) {
                        Image(systemName: "calendar.badge.plus")
                            .font(.largeTitle)
                            .foregroundStyle(.blue)

                        Text(response.spokenReply)
                            .font(.title3)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, 20)
                            .accessibilityLabel("Brain says: \(response.spokenReply)")

                        if let conflicts = response.conflicts,
                           (conflicts.hasDirectConflict || conflicts.hasFuzzyConflict) {
                            ConflictWarning(conflicts: conflicts)
                                .padding(.horizontal, 20)
                        }
                    }
                } else {
                    Text("Confirm the calendar entry?")
                        .font(.title3)
                }

                Spacer()

                // Action buttons — large targets for accessibility
                VStack(spacing: 12) {
                    Button(action: {
                        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
                        onConfirm()
                    }) {
                        Label("OK, save it", systemImage: "checkmark")
                            .font(.headline)
                            .frame(maxWidth: .infinity)
                            .frame(height: 56)
                    }
                    .buttonStyle(.borderedProminent)
                    .accessibilityLabel("Confirm and save the event")

                    Button(action: {
                        UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        onCancel()
                    }) {
                        Text("Cancel")
                            .font(.headline)
                            .frame(maxWidth: .infinity)
                            .frame(height: 56)
                    }
                    .buttonStyle(.bordered)
                    .accessibilityLabel("Cancel, don't save")
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 20)
            }
            .navigationTitle("Confirm")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel", action: onCancel)
                }
            }
        }
        .presentationDetents([.medium])
    }
}

#Preview {
    let brain = BrainService()
    return ConfirmationSheet(onConfirm: {}, onCancel: {})
        .environment(brain)
}
