import CoreAudio
import Foundation

func cfStr(_ id: AudioObjectID, _ sel: AudioObjectPropertySelector) -> String? {
    var addr = AudioObjectPropertyAddress(mSelector: sel, mScope: kAudioObjectPropertyScopeGlobal, mElement: kAudioObjectPropertyElementMain)
    var size: UInt32 = UInt32(MemoryLayout<CFString?>.size)
    var value: CFString? = nil
    let err = withUnsafeMutablePointer(to: &value) { ptr -> OSStatus in
        AudioObjectGetPropertyData(id, &addr, 0, nil, &size, ptr)
    }
    if err != noErr { return nil }
    return value as String?
}

func devices() -> [AudioObjectID] {
    var addr = AudioObjectPropertyAddress(mSelector: kAudioHardwarePropertyDevices, mScope: kAudioObjectPropertyScopeGlobal, mElement: kAudioObjectPropertyElementMain)
    var size: UInt32 = 0
    guard AudioObjectGetPropertyDataSize(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size) == noErr else { return [] }
    let n = Int(size) / MemoryLayout<AudioObjectID>.size
    var ids = [AudioObjectID](repeating: 0, count: n)
    guard AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size, &ids) == noErr else { return [] }
    return ids
}

func setRate(_ id: AudioObjectID, _ hz: Float64) {
    var addr = AudioObjectPropertyAddress(mSelector: kAudioDevicePropertyNominalSampleRate, mScope: kAudioObjectPropertyScopeGlobal, mElement: kAudioObjectPropertyElementMain)
    var rate = hz
    AudioObjectSetPropertyData(id, &addr, 0, nil, UInt32(MemoryLayout<Float64>.size), &rate)
}

func setDefaultOutput(_ uid: String) {
    guard let id = devices().first(where: { cfStr($0, kAudioDevicePropertyDeviceUID) == uid }) else { return }
    for sel: AudioObjectPropertySelector in [kAudioHardwarePropertyDefaultOutputDevice, kAudioHardwarePropertyDefaultSystemOutputDevice] {
        var addr = AudioObjectPropertyAddress(mSelector: sel, mScope: kAudioObjectPropertyScopeGlobal, mElement: kAudioObjectPropertyElementMain)
        var dev = id
        AudioObjectSetPropertyData(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, UInt32(MemoryLayout<AudioObjectID>.size), &dev)
    }
}

if CommandLine.arguments.contains("speakers") {
    setDefaultOutput("BuiltInSpeakerDevice")
    fputs("SPEAKERS\n", stdout)
    exit(0)
}

let uidKey = "de.plertanix.ud-aufnahme"
var blackhole: String?
var exists = false
for id in devices() {
    let name = cfStr(id, kAudioObjectPropertyName) ?? ""
    let uid = cfStr(id, kAudioDevicePropertyDeviceUID) ?? ""
    if uid == uidKey { setRate(id, 48000); exists = true }
    if name.localizedCaseInsensitiveContains("BlackHole") { blackhole = uid; setRate(id, 48000) }
}
if exists { fputs("EXISTS\n", stdout); exit(0) }
guard let sub = blackhole else { fputs("NO_BLACKHOLE\n", stderr); exit(2) }
let dict: [String: Any] = [
    kAudioAggregateDeviceNameKey as String: "UD Aufnahme",
    kAudioAggregateDeviceUIDKey as String: uidKey,
    kAudioAggregateDeviceMasterSubDeviceKey as String: sub,
    kAudioAggregateDeviceIsStackedKey as String: 0,
    kAudioAggregateDeviceSubDeviceListKey as String: [[kAudioSubDeviceUIDKey as String: sub]],
]
var out = AudioObjectID(0)
let err = AudioHardwareCreateAggregateDevice(dict as CFDictionary, &out)
if err != noErr { fputs("ERR \(err)\n", stderr); exit(1) }
setRate(out, 48000)
for id in devices() {
    let uid = cfStr(id, kAudioDevicePropertyDeviceUID) ?? ""
    if uid == sub || uid == uidKey { setRate(id, 48000) }
}
fputs("CREATED \(out) via \(sub)\n", stdout)
