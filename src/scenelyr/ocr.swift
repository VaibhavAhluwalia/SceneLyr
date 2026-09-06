import AppKit
import Foundation
import Vision

struct TextItem: Codable {
    let text: String
    let confidence: Float
    let x: Double
    let y: Double
    let width: Double
    let height: Double
}

guard CommandLine.arguments.count > 1,
      let image = NSImage(contentsOfFile: CommandLine.arguments[1]),
      let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    fputs("Unable to read image\n", stderr)
    exit(2)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = true
request.recognitionLanguages = ["en-US"]
try VNImageRequestHandler(cgImage: cgImage, options: [:]).perform([request])

let items = (request.results ?? []).compactMap { observation -> TextItem? in
    guard let candidate = observation.topCandidates(1).first else { return nil }
    let box = observation.boundingBox
    return TextItem(text: candidate.string, confidence: candidate.confidence,
                    x: box.origin.x, y: box.origin.y,
                    width: box.size.width, height: box.size.height)
}
let output = try JSONEncoder().encode(items)
FileHandle.standardOutput.write(output)

