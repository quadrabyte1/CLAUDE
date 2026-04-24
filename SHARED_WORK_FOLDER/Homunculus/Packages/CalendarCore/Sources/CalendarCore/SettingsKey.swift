//  SettingsKey.swift
//  CalendarCore
//
//  The closed set of settings keys. The `settings` table uses TEXT keys so future
//  migrations don't need schema changes to introduce new settings, but every key the
//  app reads or writes is enumerated here. If you're adding a setting, add it here
//  first and everyone else gets it for free.

import Foundation

public enum SettingsKey: String, Sendable, CaseIterable {

    /// Wall-clock time of day (HH:mm in user's current zone) for the morning summary
    /// notification. Stored as a JSON string, e.g. `"07:00"`.
    case morningSummaryTime = "morning_summary_time"

    /// Hour (0-23) used when the NLP resolves "tomorrow morning" and the utterance
    /// gives no explicit time. JSON integer.
    case morningAnchorHour = "morning_anchor_hour"

    /// Half-width of the "close to a conflict" fuzzy window, in minutes. JSON integer.
    case conflictFuzzMinutes = "conflict_fuzz_min"

    /// The Talk button mode. v1 ships "press_hold" only; the key exists so v1.x can add
    /// "press_to_start" without a migration. JSON string.
    case talkMode = "talk_mode"

    /// The seeded default for each setting, encoded as the JSON string that will live in
    /// the `value` column.
    public var defaultValueJSON: String {
        switch self {
        case .morningSummaryTime:  return "\"07:00\""
        case .morningAnchorHour:   return "9"
        case .conflictFuzzMinutes: return "30"
        case .talkMode:            return "\"press_hold\""
        }
    }
}
