/// TodayView.swift
/// Shows today's calendar events pulled from GET /events?day=YYYY-MM-DD.
/// Also shows upcoming reminders for context.

import SwiftUI

struct TodayView: View {
    @Environment(BrainService.self) private var brain

    private var todayFormatted: String {
        let f = DateFormatter()
        f.dateStyle = .full
        f.timeStyle = .none
        return f.string(from: Date())
    }

    var body: some View {
        NavigationStack {
            List {
                // --- Today's events ---
                Section("Events") {
                    if brain.todayEvents.isEmpty {
                        Text("No events today")
                            .foregroundStyle(.secondary)
                            .font(.subheadline)
                    } else {
                        ForEach(brain.todayEvents) { event in
                            EventRow(event: event)
                        }
                    }
                }

                // --- Upcoming reminders ---
                Section("Upcoming Reminders") {
                    if brain.upcomingReminders.isEmpty {
                        Text("No reminders in the next 72 hours")
                            .foregroundStyle(.secondary)
                            .font(.subheadline)
                    } else {
                        ForEach(brain.upcomingReminders.prefix(10)) { row in
                            ReminderRowView(row: row)
                        }
                        if brain.upcomingReminders.count > 10 {
                            Text("+\(brain.upcomingReminders.count - 10) more")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
            .navigationTitle(todayFormatted)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        Task {
                            await brain.refreshTodayEvents()
                            await brain.refreshReminders()
                        }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                    .accessibilityLabel("Refresh")
                }
            }
            .refreshable {
                await brain.refreshTodayEvents()
                await brain.refreshReminders()
            }
        }
    }
}

struct EventRow: View {
    let event: CalendarEvent

    private var timeRange: String {
        let f = DateFormatter()
        f.timeStyle = .short
        f.dateStyle = .none
        return "\(f.string(from: event.startsAt)) – \(f.string(from: event.endsAt))"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(event.title)
                .font(.headline)
                .accessibilityAddTraits(.isHeader)
            HStack {
                Image(systemName: "clock")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text(timeRange)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                if !event.people.isEmpty {
                    Text("·")
                        .foregroundStyle(.secondary)
                    Text(event.people.joined(separator: ", "))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .combine)
    }
}

struct ReminderRowView: View {
    let row: ReminderRow

    private var fireAtFormatted: String {
        let f = DateFormatter()
        f.dateStyle = .short
        f.timeStyle = .short
        return f.string(from: row.fireAt)
    }

    var body: some View {
        HStack(spacing: 10) {
            Circle()
                .fill(row.kind.isUrgent ? Color.red : Color.blue)
                .frame(width: 8, height: 8)

            VStack(alignment: .leading, spacing: 2) {
                Text(row.body)
                    .font(.subheadline)
                    .lineLimit(2)
                Text(fireAtFormatted)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            Text(row.kind.rawValue.replacingOccurrences(of: "_", with: " "))
                .font(.caption2)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(
                    Capsule()
                        .fill(Color(.tertiarySystemBackground))
                )
        }
        .padding(.vertical, 2)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Reminder: \(row.body) at \(fireAtFormatted)")
    }
}

#Preview {
    TodayView()
        .environment(BrainService())
}
