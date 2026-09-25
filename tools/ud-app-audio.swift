import Foundation
import ScreenCaptureKit
import CoreMedia
import AVFoundation

final class AudioOut: NSObject, SCStreamOutput {
    func stream(_ stream: SCStream, didOutputSampleBuffer sample: CMSampleBuffer, of type: SCStreamOutputType) {
        guard type == .audio, CMSampleBufferGetNumSamples(sample) > 0 else { return }
        try? sample.withAudioBufferList { list, _ in
            let n = Int(list.count)
            guard n > 0, let first = list[0].mData else { return }
            if n == 1 {
                FileHandle.standardOutput.write(Data(bytes: first, count: Int(list[0].mDataByteSize)))
                return
            }
            guard let second = list[1].mData else { return }
            let frames = min(Int(list[0].mDataByteSize), Int(list[1].mDataByteSize)) / 4
            var mixed = Data(count: frames * 8)
            mixed.withUnsafeMutableBytes { raw in
                let dst = raw.bindMemory(to: Float.self)
                let l = first.bindMemory(to: Float.self, capacity: frames)
                let r = second.bindMemory(to: Float.self, capacity: frames)
                for i in 0..<frames {
                    dst[i * 2] = l[i]
                    dst[i * 2 + 1] = r[i]
                }
            }
            FileHandle.standardOutput.write(mixed)
        }
    }
}

func listApps() async throws {
    let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: false)
    for app in content.applications where !app.applicationName.isEmpty && app.processID > 0 {
        print("\(app.processID)\t\(app.applicationName)")
    }
}

func record(pid: pid_t) async throws {
    let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
    guard let app = content.applications.first(where: { $0.processID == pid }) else {
        fputs("APP_NOT_FOUND\n", stderr)
        exit(2)
    }
    guard let display = content.displays.first else { exit(3) }
    let filter = SCContentFilter(display: display, including: [app], exceptingWindows: [])
    let config = SCStreamConfiguration()
    config.capturesAudio = true
    config.excludesCurrentProcessAudio = true
    config.sampleRate = 48000
    config.channelCount = 2
    config.width = 2
    config.height = 2
    let stream = SCStream(filter: filter, configuration: config, delegate: nil)
    let out = AudioOut()
    try stream.addStreamOutput(out, type: .audio, sampleHandlerQueue: DispatchQueue(label: "ud.audio"))
    try await stream.startCapture()
    dispatchMain()
}

let args = CommandLine.arguments
if args.count >= 2 && args[1] == "list" {
    Task {
        do { try await listApps() } catch { fputs("\(error)\n", stderr); exit(1) }
        exit(0)
    }
    dispatchMain()
} else if args.count >= 3 && args[1] == "record", let pid = Int32(args[2]) {
    Task {
        do { try await record(pid: pid) } catch { fputs("\(error)\n", stderr); exit(1) }
    }
    dispatchMain()
} else {
    fputs("usage: ud-app-audio list | record PID\n", stderr)
    exit(1)
}
