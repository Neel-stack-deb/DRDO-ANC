import QtQuick
import QtQuick.Layouts

Item {
    id: root
    property color white: "#F0F4F8"
    property color cyan: "#00E5FF"
    property color dim: "#888888"
    property color panel: "#11151C"

    ColumnLayout {
        anchors.fill: parent
        spacing: 4

        Text {
            text: guiBridge.isDemoMode ? "DEMO MODE v2" : "DEMO STATUS"
            color: dim
            font.pixelSize: 9
            font.bold: true
        }

        Text {
            visible: guiBridge.isDemoMode
            text: "State: " + guiBridge.demoStatus
            color: cyan
            font.pixelSize: 11
            font.bold: true
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }

        GridLayout {
            columns: 2
            columnSpacing: 12
            rowSpacing: 2
            Layout.fillWidth: true

            Text {
                visible: guiBridge.isDemoMode
                text: "Scenario"
                color: dim
                font.pixelSize: 10
            }
            Text {
                visible: guiBridge.isDemoMode
                text: guiBridge.demoScenario
                color: white
                font.pixelSize: 10
            }

            Text {
                visible: guiBridge.isDemoMode && guiBridge.demoSourceFile.length > 0
                text: "Source file"
                color: dim
                font.pixelSize: 10
            }
            Text {
                visible: guiBridge.isDemoMode && guiBridge.demoSourceFile.length > 0
                text: guiBridge.demoSourceFile
                color: white
                font.pixelSize: 10
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            Text {
                visible: guiBridge.isDemoMode
                text: "Duration"
                color: dim
                font.pixelSize: 10
            }
            Text {
                visible: guiBridge.isDemoMode
                text: guiBridge.demoDurationSeconds.toFixed(2) + " s"
                color: white
                font.pixelSize: 10
            }

            Text { text: "Model"; color: dim; font.pixelSize: 10 }
            Text {
                text: guiBridge.isDemoMode && guiBridge.demoModelName.length > 0
                    ? guiBridge.demoModelName
                    : guiBridge.modelName
                color: white
                font.pixelSize: 10
            }

            Text { text: "Sample rate"; color: dim; font.pixelSize: 10 }
            Text { text: guiBridge.sampleRate + " Hz"; color: white; font.pixelSize: 10 }

            Text { text: "Latency"; color: dim; font.pixelSize: 10 }
            Text { text: guiBridge.processingTimeMs.toFixed(2) + " ms"; color: white; font.pixelSize: 10 }

            Text { text: "RTF"; color: dim; font.pixelSize: 10 }
            Text { text: guiBridge.realtimeFactor.toFixed(2) + "x"; color: white; font.pixelSize: 10 }

            Text { text: "Audio"; color: dim; font.pixelSize: 10 }
            Text { text: guiBridge.audioStatus; color: cyan; font.pixelSize: 10 }

            Text {
                visible: guiBridge.operationMode === "demo" && guiBridge.demoNoisyFile.length > 0
                text: "Noisy input"
                color: dim
                font.pixelSize: 10
            }
            Text {
                visible: guiBridge.operationMode === "demo" && guiBridge.demoNoisyFile.length > 0
                text: guiBridge.demoNoisyFile
                color: white
                font.pixelSize: 10
            }

            Text {
                visible: guiBridge.operationMode === "demo" && guiBridge.demoCleanFile.length > 0
                text: "Clean ref"
                color: dim
                font.pixelSize: 10
            }
            Text {
                visible: guiBridge.operationMode === "demo" && guiBridge.demoCleanFile.length > 0
                text: guiBridge.demoCleanFile
                color: white
                font.pixelSize: 10
            }

            Text {
                visible: guiBridge.operationMode === "demo" && guiBridge.demoEnhancedRefFile.length > 0
                text: "Enh. ref"
                color: dim
                font.pixelSize: 10
            }
            Text {
                visible: guiBridge.operationMode === "demo" && guiBridge.demoEnhancedRefFile.length > 0
                text: guiBridge.demoEnhancedRefFile
                color: white
                font.pixelSize: 10
            }

            Text {
                visible: guiBridge.operationMode === "demo"
                text: "B playback"
                color: dim
                font.pixelSize: 10
            }
            Text {
                visible: guiBridge.operationMode === "demo"
                text: guiBridge.demoEnhancedPlayback
                color: cyan
                font.pixelSize: 10
            }

            Text {
                visible: guiBridge.showDemoMetrics
                text: "Noisy SNR"
                color: dim
                font.pixelSize: 10
            }
            Text {
                visible: guiBridge.showDemoMetrics
                text: guiBridge.demoNoisySnr.toFixed(1) + " dB"
                color: white
                font.pixelSize: 10
            }

            Text {
                visible: guiBridge.showDemoMetrics
                text: "Ref enh SNR"
                color: dim
                font.pixelSize: 10
            }
            Text {
                visible: guiBridge.showDemoMetrics
                text: guiBridge.demoEnhancedRefSnr.toFixed(1) + " dB"
                color: white
                font.pixelSize: 10
            }

            Text {
                visible: guiBridge.showBenchmarkSummary
                text: "Development cases"
                color: dim
                font.pixelSize: 10
            }
            Text {
                visible: guiBridge.showBenchmarkSummary
                text: guiBridge.developmentCases
                color: white
                font.pixelSize: 10
            }

            Text {
                visible: guiBridge.showBenchmarkSummary
                text: "Evaluations"
                color: dim
                font.pixelSize: 10
            }
            Text {
                visible: guiBridge.showBenchmarkSummary
                text: guiBridge.evaluations
                color: white
                font.pixelSize: 10
            }
        }

        Text {
            visible: guiBridge.isDemoMode && guiBridge.missingDemoCategories.length > 0
            text: "Unavailable scenarios (no local WAV):"
            color: dim
            font.pixelSize: 9
            font.bold: true
            Layout.topMargin: 6
        }

        Repeater {
            model: guiBridge.missingDemoCategories
            Text {
                visible: guiBridge.isDemoMode
                text: "• " + modelData
                color: "#AA8866"
                font.pixelSize: 9
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
        }
    }
}
