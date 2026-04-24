// swift-tools-version: 6.0
import PackageDescription

// CalendarCore — M1.
// Owner: Mori.
// Boundary: the local data layer. GRDB over SQLite (WAL), schema + migrations, record
// types, actor-isolated writer, DatabasePool reader, time-zone helpers.
// Depends on: GRDB.swift only.
// Does NOT depend on: any other Homunculus package.
//
// GRDB pin: 6.29.3 — latest stable on the 6.x line as of 2026-04. 6.x is the release
// train Homunculus ships v1 on; we pin exact so schema-migration behavior is reproducible
// across dev machines and CI.

let package = Package(
    name: "CalendarCore",
    platforms: [.iOS(.v26)],
    products: [
        .library(name: "CalendarCore", targets: ["CalendarCore"])
    ],
    dependencies: [
        .package(
            url: "https://github.com/groue/GRDB.swift.git",
            exact: "6.29.3"
        )
    ],
    targets: [
        .target(
            name: "CalendarCore",
            dependencies: [
                .product(name: "GRDB", package: "GRDB.swift")
            ],
            swiftSettings: [
                .enableExperimentalFeature("StrictConcurrency")
            ]
        ),
        .testTarget(
            name: "CalendarCoreTests",
            dependencies: ["CalendarCore"]
        )
    ]
)
