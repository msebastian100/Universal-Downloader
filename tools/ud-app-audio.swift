import Foundation
import ScreenCaptureKit
import CoreMedia
import CoreAudio
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

var heldStream: SCStream?
var heldProc: AudioDeviceIOProcID?
var ioCallbacks = 0
let heldOutput = AudioOut()

func start(filter: SCContentFilter) async throws {
    let config = SCStreamConfiguration()
    config.capturesAudio = true
    config.excludesCurrentProcessAudio = true
    config.sampleRate = 48000
    config.channelCount = 2
    config.width = 2
    config.height = 2
    let stream = SCStream(filter: filter, configuration: config, delegate: nil)
    try stream.addStreamOutput(heldOutput, type: .audio, sampleHandlerQueue: DispatchQueue(label: "ud.audio"))
    try await stream.startCapture()
    heldStream = stream
}

func recordSystem() async throws {
    let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
    guard let display = content.displays.first else { exit(3) }
    let filter = SCContentFilter(display: display, excludingApplications: [], exceptingWindows: [])
    try await start(filter: filter)
}

func audioProcesses(matching pid: pid_t) -> [AudioObjectID] {
    let bundle = NSRunningApplication(processIdentifier: pid)?.bundleIdentifier
    var listAddress = AudioObjectPropertyAddress(
        mSelector: kAudioHardwarePropertyProcessObjectList,
        mScope: kAudioObjectPropertyScopeGlobal,
        mElement: kAudioObjectPropertyElementMain)
    var dataSize: UInt32 = 0
    guard AudioObjectGetPropertyDataSize(AudioObjectID(kAudioObjectSystemObject), &listAddress, 0, nil, &dataSize) == noErr,
          dataSize > 0 else { return [] }
    var ids = [AudioObjectID](repeating: 0, count: Int(dataSize) / MemoryLayout<AudioObjectID>.size)
    guard AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &listAddress, 0, nil, &dataSize, &ids) == noErr else {
        return []
    }
    var matched: [AudioObjectID] = []
    for id in ids {
        var pidAddress = AudioObjectPropertyAddress(
            mSelector: kAudioProcessPropertyPID,
            mScope: kAudioObjectPropertyScopeGlobal,
            mElement: kAudioObjectPropertyElementMain)
        var processPID: pid_t = 0
        var size = UInt32(MemoryLayout<pid_t>.size)
        guard AudioObjectGetPropertyData(id, &pidAddress, 0, nil, &size, &processPID) == noErr else { continue }
        let sameBundle = bundle != nil && NSRunningApplication(processIdentifier: processPID)?.bundleIdentifier == bundle
        if processPID == pid || sameBundle {
            matched.append(id)
        }
    }
    return matched
}

func defaultOutputUID() -> String? {
    var deviceAddress = AudioObjectPropertyAddress(
        mSelector: kAudioHardwarePropertyDefaultOutputDevice,
        mScope: kAudioObjectPropertyScopeGlobal,
        mElement: kAudioObjectPropertyElementMain)
    var device = AudioObjectID(kAudioObjectUnknown)
    var deviceSize = UInt32(MemoryLayout<AudioObjectID>.size)
    guard AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &deviceAddress, 0, nil, &deviceSize, &device) == noErr else {
        return nil
    }
    var uidAddress = AudioObjectPropertyAddress(
        mSelector: kAudioDevicePropertyDeviceUID,
        mScope: kAudioObjectPropertyScopeGlobal,
        mElement: kAudioObjectPropertyElementMain)
    var value: CFString?
    var size = UInt32(MemoryLayout<CFString?>.size)
    let status = withUnsafeMutablePointer(to: &value) { pointer in
        AudioObjectGetPropertyData(device, &uidAddress, 0, nil, &size, UnsafeMutableRawPointer(pointer))
    }
    guard status == noErr, let value else { return nil }
    return value as String
}

func tapUID(_ tap: AudioObjectID) -> String? {
    var address = AudioObjectPropertyAddress(
        mSelector: kAudioTapPropertyUID,
        mScope: kAudioObjectPropertyScopeGlobal,
        mElement: kAudioObjectPropertyElementMain)
    var value: CFString?
    var size = UInt32(MemoryLayout<CFString?>.size)
    let status = withUnsafeMutablePointer(to: &value) { pointer in
        AudioObjectGetPropertyData(tap, &address, 0, nil, &size, UnsafeMutableRawPointer(pointer))
    }
    guard status == noErr, let value else { return nil }
    return value as String
}

func recordApp(pid: pid_t, mute: Bool) throws {
    let processes = audioProcesses(matching: pid)
    guard !processes.isEmpty else {
        fputs("APP_NOT_FOUND\n", stderr)
        exit(2)
    }
    let description = CATapDescription(stereoMixdownOfProcesses: processes)
    description.muteBehavior = mute ? CATapMuteBehavior.muted : CATapMuteBehavior.unmuted
    description.isPrivate = true
    description.name = "UD Tonspur"
    var tap = AudioObjectID(kAudioObjectUnknown)
    let created = AudioHardwareCreateProcessTap(description, &tap)
    guard created == noErr else {
        fputs("TAP_FAILED \(created)\n", stderr)
        exit(4)
    }
    guard let uid = tapUID(tap), let clock = defaultOutputUID() else {
        fputs("TAP_UID_FAILED\n", stderr)
        exit(4)
    }
    let aggregate: [String: Any] = [
        kAudioAggregateDeviceNameKey: "UD Tonspur",
        kAudioAggregateDeviceUIDKey: "de.plertanix.ud-tap-\(UUID().uuidString)",
        kAudioAggregateDeviceMainSubDeviceKey: clock,
        kAudioAggregateDeviceIsPrivateKey: true,
        kAudioAggregateDeviceTapAutoStartKey: true,
        kAudioAggregateDeviceSubDeviceListKey: [[kAudioSubDeviceUIDKey: clock]],
        kAudioAggregateDeviceTapListKey: [[kAudioSubTapUIDKey: uid]],
    ]
    var aggregateID = AudioObjectID(kAudioObjectUnknown)
    let aggregated = AudioHardwareCreateAggregateDevice(aggregate as CFDictionary, &aggregateID)
    guard aggregated == noErr else {
        fputs("AGGREGATE_FAILED \(aggregated)\n", stderr)
        exit(4)
    }
    var streamFormat = AudioStreamBasicDescription()
    var formatAddress = AudioObjectPropertyAddress(
        mSelector: kAudioDevicePropertyStreamFormat,
        mScope: kAudioDevicePropertyScopeInput,
        mElement: kAudioObjectPropertyElementMain)
    var formatSize = UInt32(MemoryLayout<AudioStreamBasicDescription>.size)
    AudioObjectGetPropertyData(aggregateID, &formatAddress, 0, nil, &formatSize, &streamFormat)
    var frameSize: UInt32 = 512
    var frameAddress = AudioObjectPropertyAddress(
        mSelector: kAudioDevicePropertyBufferFrameSize,
        mScope: kAudioObjectPropertyScopeGlobal,
        mElement: kAudioObjectPropertyElementMain)
    AudioObjectSetPropertyData(aggregateID, &frameAddress, 0, nil, UInt32(MemoryLayout<UInt32>.size), &frameSize)
    let started = AudioDeviceCreateIOProcIDWithBlock(&heldProc, aggregateID, DispatchQueue.global()) { _, inputData, _, _, _ in
        let buffers = UnsafeMutableAudioBufferListPointer(UnsafeMutablePointer(mutating: inputData))
        ioCallbacks += 1
        guard let first = buffers.first, let data = first.mData, first.mDataByteSize > 0 else { return }
        if streamFormat.mChannelsPerFrame >= 2 && buffers.count >= 2, let second = buffers[1].mData {
            let frames = min(Int(first.mDataByteSize), Int(buffers[1].mDataByteSize)) / 4
            var mixed = Data(count: frames * 8)
            mixed.withUnsafeMutableBytes { raw in
                let dst = raw.bindMemory(to: Float.self)
                let left = data.bindMemory(to: Float.self, capacity: frames)
                let right = second.bindMemory(to: Float.self, capacity: frames)
                for i in 0..<frames {
                    dst[i * 2] = left[i]
                    dst[i * 2 + 1] = right[i]
                }
            }
            FileHandle.standardOutput.write(mixed)
        } else {
            FileHandle.standardOutput.write(Data(bytes: data, count: Int(first.mDataByteSize)))
        }
    }
    guard started == noErr, let heldProc else { exit(4) }
    guard AudioDeviceStart(aggregateID, heldProc) == noErr else { exit(4) }
    dispatchMain()
}

func record(pid: pid_t) async throws {
    let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
    guard let app = content.applications.first(where: { $0.processID == pid }) else {
        fputs("APP_NOT_FOUND\n", stderr)
        exit(2)
    }
    guard let display = content.displays.first else { exit(3) }
    let filter = SCContentFilter(display: display, including: [app], exceptingWindows: [])
    try await start(filter: filter)
}

let args = CommandLine.arguments
if args.count >= 2 && args[1] == "list" {
    Task {
        do { try await listApps() } catch { fputs("\(error)\n", stderr); exit(1) }
        exit(0)
    }
    dispatchMain()
} else if args.count >= 3 && args[1] == "record", args[2] == "system" {
    Task {
        do { try await recordSystem() } catch { fputs("\(error)\n", stderr); exit(1) }
    }
    dispatchMain()
} else if args.count >= 3 && args[1] == "record", let pid = Int32(args[2]), args[2] != "system" {
    let mute = args.count >= 4 && args[3] == "mute"
    do { try recordApp(pid: pid, mute: mute) } catch { fputs("\(error)\n", stderr); exit(1) }
} else {
    fputs("usage: ud-app-audio list | record system | record PID\n", stderr)
    exit(1)
}
