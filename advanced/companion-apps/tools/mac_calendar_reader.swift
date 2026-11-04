// Native calendar reader for the CrowPanel Mac bridge. Never modifies events.
import AppKit
import EventKit
import Foundation

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let args = CommandLine.arguments
func argument(_ name: String) -> String? {
    guard let i = args.firstIndex(of: name), i + 1 < args.count else { return nil }
    return args[i + 1]
}
guard let output = argument("--output"), let configPath = argument("--config") else { exit(2) }
let store = EKEventStore()

func finish(_ payload: [String: Any]) {
    var result = payload
    result["updated_at"] = Date().timeIntervalSince1970
    do {
        let data = try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
        let url = URL(fileURLWithPath: output)
        try data.write(to: url, options: .atomic)
        try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: output)
    } catch { exit(3) }
    exit(0)
}

func readNextMeeting() {
    guard EKEventStore.authorizationStatus(for: .event) == .fullAccess else {
        finish(["status": "permission_denied"]); return
    }
    store.refreshSourcesIfNecessary()
    let calendars = store.calendars(for: .event).filter { $0.source.sourceType == .exchange }
    let choices = calendars.map { ["id": $0.calendarIdentifier, "title": $0.title, "account": $0.source.title] }
    let config = (try? Data(contentsOf: URL(fileURLWithPath: configPath)))
        .flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] } ?? [:]
    let ids = config["calendar_ids"] as? [String] ?? []
    let selected: [EKCalendar]
    if !ids.isEmpty {
        selected = calendars.filter { ids.contains($0.calendarIdentifier) }
        guard selected.count == Set(ids).count else {
            finish(["status": "calendar_missing", "calendars": choices]); return
        }
    } else if calendars.count == 1 {
        selected = calendars
    } else {
        finish(["status": calendars.isEmpty ? "no_exchange_calendar" : "choose_calendar", "calendars": choices]); return
    }
    let now = Date()
    let end = now.addingTimeInterval(7 * 24 * 60 * 60)
    let predicate = store.predicateForEvents(withStart: now, end: end, calendars: selected)
    let events = store.events(matching: predicate).filter { event in
        guard !event.isAllDay, event.startDate > now, event.status != .canceled,
              event.availability != .free else { return false }
        return !(event.attendees ?? []).contains { $0.isCurrentUser && $0.participantStatus == .declined }
    }.sorted { $0.startDate < $1.startDate }
    guard let next = events.first else {
        finish(["status": "empty", "calendar_ids": selected.map { $0.calendarIdentifier }]); return
    }
    finish(["status": "ok", "title": next.title ?? "Meeting",
            "start": next.startDate.timeIntervalSince1970,
            "end": next.endDate.timeIntervalSince1970,
            "calendar_ids": selected.map { $0.calendarIdentifier }])
}

// LaunchServices does not terminate the app when its `open -W` caller stops.
// Bound each one-shot read so unanswered permission prompts cannot orphan readers.
DispatchQueue.global(qos: .utility).asyncAfter(deadline: .now() + 110) {
    finish(["status": "reader_timeout"])
}

if EKEventStore.authorizationStatus(for: .event) == .notDetermined {
    store.requestFullAccessToEvents { granted, _ in
        DispatchQueue.main.async {
            if granted { readNextMeeting() }
            else { finish(["status": "permission_denied"]) }
        }
    }
} else {
    DispatchQueue.main.async { readNextMeeting() }
}
app.run()
