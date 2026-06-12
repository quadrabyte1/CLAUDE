/// CaptureView.swift
/// Main capture screen.
///
/// v1 is text-only (voice STT deferred — see OPEN_QUESTIONS.md §OQ-2).
/// The large text field + Send button is functionally identical to voice capture
/// from the brain's perspective; voice can be layered on top later by replacing
/// the text input with a Talk button that fills the same field.
///
/// Capture flow:
///   1. User types text → taps Send.
///   2. POST /capture/text → CaptureResponse.
///   3. Based on action:
///      - wrote / inbox: show reply inline. Done.
///      - needs_confirmation: show ConfirmationSheet.
///      - needs_clarification: show clarifying question + re-arm text field.

import SwiftUI

struct CaptureView: View {
    @Environment(BrainService.self) private var brain

    @State private var inputText: String = ""
    @State private var showConfirmation: Bool = false

    // For needs_clarification: the question to display above the text field.
    @State private var clarifyingQuestion: String? = nil

    @FocusState private var fieldFocused: Bool

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {

                    // --- Last response display ---
                    if let response = brain.lastCaptureResponse {
                        ResponseCard(response: response)
                    }

                    // --- Clarifying question prompt ---
                    if let question = clarifyingQuestion {
                        ClarifyingQuestionBanner(question: question)
                    }

                    // --- Error display ---
                    if let error = brain.errorMessage {
                        ErrorBanner(message: error) {
                            brain.errorMessage = nil
                        }
                    }

                    // --- Input area ---
                    CaptureInputField(
                        text: $inputText,
                        isCapturing: brain.isCapturing,
                        placeholder: clarifyingQuestion != nil
                            ? "Type your answer…"
                            : "Capture something…",
                        onSend: sendCapture
                    )
                    .focused($fieldFocused)

                    // Quick hint for first-time use.
                    if brain.lastCaptureResponse == nil && !brain.isCapturing {
                        TipsCard()
                    }
                }
                .padding(16)
            }
            .navigationTitle("Homunculus")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    BrainStatusIndicator()
                }
            }
            .sheet(isPresented: $showConfirmation) {
                ConfirmationSheet(
                    onConfirm: {
                        showConfirmation = false
                        Task { await brain.confirmCapture() }
                    },
                    onCancel: {
                        showConfirmation = false
                        brain.cancelCapture()
                    }
                )
            }
            .onChange(of: brain.lastCaptureResponse) { _, response in
                guard let response else { return }
                handleResponse(response)
            }
        }
    }

    // MARK: - Actions

    private func sendCapture() {
        let text = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        // Haptic feedback
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
        inputText       = ""
        clarifyingQuestion = nil
        Task { await brain.capture(text: text) }
    }

    private func handleResponse(_ response: CaptureResponse) {
        switch response.action {
        case .needsConfirmation:
            showConfirmation = true
        case .needsClarification:
            clarifyingQuestion = response.clarifyingQuestion
            // Re-focus the text field for the follow-up answer.
            fieldFocused = true
        case .wrote, .inbox:
            clarifyingQuestion = nil
            showConfirmation   = false
        }
    }
}

// MARK: - Sub-views

struct CaptureInputField: View {
    @Binding var text: String
    let isCapturing: Bool
    let placeholder: String
    let onSend: () -> Void

    var body: some View {
        HStack(alignment: .bottom, spacing: 12) {
            TextField(placeholder, text: $text, axis: .vertical)
                .textFieldStyle(.roundedBorder)
                .lineLimit(1...5)
                .disabled(isCapturing)
                .submitLabel(.send)
                .onSubmit(onSend)
                .accessibilityLabel("Capture text field")

            Button(action: onSend) {
                if isCapturing {
                    ProgressView()
                        .frame(width: 44, height: 44)
                } else {
                    Image(systemName: "arrow.up.circle.fill")
                        .resizable()
                        .frame(width: 44, height: 44)
                        .foregroundStyle(.blue)
                }
            }
            .disabled(isCapturing || text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            .accessibilityLabel(isCapturing ? "Sending" : "Send capture")
        }
    }
}

struct ResponseCard: View {
    let response: CaptureResponse

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: actionIcon)
                    .foregroundStyle(actionColor)
                Text(actionLabel)
                    .font(.caption.bold())
                    .foregroundStyle(actionColor)
                Spacer()
                Text(kindLabel)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }

            Text(response.spokenReply)
                .font(.body)
                .fixedSize(horizontal: false, vertical: true)

            if let conflicts = response.conflicts,
               (conflicts.hasDirectConflict || conflicts.hasFuzzyConflict) {
                ConflictWarning(conflicts: conflicts)
            }
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color(.secondarySystemBackground))
        )
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Brain reply: \(response.spokenReply)")
    }

    private var actionIcon: String {
        switch response.action {
        case .wrote:             return "checkmark.circle.fill"
        case .needsConfirmation: return "questionmark.circle.fill"
        case .needsClarification: return "bubble.left.fill"
        case .inbox:             return "tray.fill"
        }
    }
    private var actionColor: Color {
        switch response.action {
        case .wrote:             return .green
        case .needsConfirmation: return .orange
        case .needsClarification: return .blue
        case .inbox:             return .purple
        }
    }
    private var actionLabel: String {
        switch response.action {
        case .wrote:             return "Saved"
        case .needsConfirmation: return "Confirm?"
        case .needsClarification: return "Needs more info"
        case .inbox:             return "Filed to inbox"
        }
    }
    private var kindLabel: String {
        response.kind.rawValue.replacingOccurrences(of: "_", with: " ").capitalized
    }
}

struct ConflictWarning: View {
    let conflicts: ConflictReport

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(.orange)
            VStack(alignment: .leading, spacing: 2) {
                if conflicts.hasDirectConflict {
                    Text("Direct conflict with existing event")
                        .font(.caption)
                        .foregroundStyle(.orange)
                }
                if conflicts.hasFuzzyConflict {
                    Text("Overlaps with another event")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
    }
}

struct ClarifyingQuestionBanner: View {
    let question: String

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "bubble.left.fill")
                .foregroundStyle(.blue)
            Text(question)
                .font(.subheadline)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(Color.blue.opacity(0.08))
                .overlay(
                    RoundedRectangle(cornerRadius: 10)
                        .stroke(Color.blue.opacity(0.3), lineWidth: 1)
                )
        )
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Question: \(question)")
    }
}

struct ErrorBanner: View {
    let message: String
    let onDismiss: () -> Void

    var body: some View {
        HStack {
            Image(systemName: "xmark.octagon.fill")
                .foregroundStyle(.red)
            Text(message)
                .font(.caption)
            Spacer()
            Button("Dismiss", action: onDismiss)
                .font(.caption.bold())
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(Color.red.opacity(0.08))
        )
    }
}

struct BrainStatusIndicator: View {
    @Environment(BrainService.self) private var brain

    var body: some View {
        Circle()
            .fill(brain.isOnline ? Color.green : Color.red)
            .frame(width: 10, height: 10)
            .accessibilityLabel(brain.isOnline ? "Brain online" : "Brain offline")
    }
}

struct TipsCard: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Try saying:")
                .font(.caption.bold())
                .foregroundStyle(.secondary)
            ForEach(tips, id: \.self) { tip in
                HStack(spacing: 6) {
                    Image(systemName: "arrow.right")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Text(tip)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(Color(.tertiarySystemBackground))
        )
    }

    private let tips = [
        "\"Coffee with Jane Thursday at 10\"",
        "\"Remind me to call the dentist tomorrow\"",
        "\"Note: Festool track saw uses 55mm rail\"",
    ]
}

#Preview {
    CaptureView()
        .environment(BrainService())
}
