import SwiftUI

struct ContentView: View {
    @State private var tapped = false
    @State private var pressTime: String? = nil

    private let buttonDiameter: CGFloat = 140
    private let activatedBackground = Color(red: 0.7, green: 0.85, blue: 1.0)
    private let appVersion = "1.1"

    var body: some View {
        ZStack {
            (tapped ? activatedBackground : Color(UIColor.systemBackground))
                .ignoresSafeArea()
                .animation(.easeInOut(duration: 0.35), value: tapped)

            VStack(spacing: 24) {
                Button {
                    let now = Date()
                    pressTime = now.formatted(date: .omitted, time: .shortened)
                    withAnimation(.easeInOut(duration: 0.35)) {
                        tapped.toggle()
                    }
                } label: {
                    Circle()
                        .fill(Color.red)
                        .frame(width: buttonDiameter, height: buttonDiameter)
                        .overlay {
                            Text("Go")
                                .font(.system(size: 36, weight: .bold, design: .rounded))
                                .foregroundStyle(.white)
                        }
                }
                .accessibilityLabel("Go")
                .accessibilityHint(tapped ? "Tap to deactivate" : "Tap to activate")

                Text(pressTime ?? "—")
                    .font(.system(size: 22, weight: .semibold, design: .rounded))
                    .foregroundStyle(.primary)
                    .accessibilityLabel(pressTime.map { "Pressed at \($0)" } ?? "Not yet pressed")
            }

            VStack {
                Spacer()
                Text("v\(appVersion)")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .padding(.bottom, 12)
                    .accessibilityLabel("Version \(appVersion)")
            }
        }
    }
}

#Preview {
    ContentView()
}
