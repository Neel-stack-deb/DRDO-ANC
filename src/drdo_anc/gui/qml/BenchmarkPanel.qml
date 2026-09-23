import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

ScrollView {
    id: root
    clip: true

    property color white: "#F0F4F8"
    property color cyan: "#00E5FF"
    property color dim: "#888888"
    property color warn: "#FFAA66"
    property bool metricsHelpOpen: false

    ColumnLayout {
        width: root.width
        spacing: 8

        Text {
            text: "OFFLINE BENCHMARK RESULTS"
            color: cyan
            font.pixelSize: 11
            font.bold: true
        }

        Text {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: dim
            font.pixelSize: 9
            text: "Measured offline on the SIH-26 evaluation protocol. " +
                  "These numbers are not live microphone measurements."
        }

        Text {
            visible: !guiBridge.benchmarkLoaded
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: warn
            font.pixelSize: 11
            text: guiBridge.benchmarkUnavailableMessage.length > 0
                ? guiBridge.benchmarkUnavailableMessage
                : "Benchmark results unavailable."
        }

        Text {
            visible: guiBridge.benchmarkPartialWarning.length > 0
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: warn
            font.pixelSize: 9
            text: guiBridge.benchmarkPartialWarning
        }

        // --- Development benchmark ---
        Text {
            visible: guiBridge.devBenchmarkAvailable
            text: guiBridge.devBenchmarkTitle
            color: white
            font.pixelSize: 10
            font.bold: true
            Layout.topMargin: 6
        }

        Text {
            visible: guiBridge.devBenchmarkAvailable
            Layout.fillWidth: true
            text: guiBridge.devBenchmarkContext
            color: dim
            font.pixelSize: 9
            lineHeight: 1.2
            lineHeightMode: Text.ProportionalHeight
            wrapMode: Text.WordWrap
        }

        Text {
            visible: guiBridge.devBenchmarkAvailable
            text: "MODEL COMPARISON"
            color: dim
            font.pixelSize: 9
            font.bold: true
        }

        GridLayout {
            visible: guiBridge.devBenchmarkAvailable
            columns: 3
            columnSpacing: 8
            rowSpacing: 3
            Layout.fillWidth: true

            Text { text: "Metric"; color: dim; font.pixelSize: 9 }
            Text { text: "Pretrained"; color: dim; font.pixelSize: 9 }
            Text { text: "Fine-tuned"; color: dim; font.pixelSize: 9 }

            Text { text: "SI-SDR"; color: white; font.pixelSize: 9 }
            Text { text: guiBridge.devPretrainedSiSdr.toFixed(2) + " dB"; color: white; font.pixelSize: 9 }
            Text { text: guiBridge.devFinetunedSiSdr.toFixed(2) + " dB"; color: cyan; font.pixelSize: 9 }

            Text { text: "STOI"; color: white; font.pixelSize: 9 }
            Text { text: guiBridge.devPretrainedStoi.toFixed(3); color: white; font.pixelSize: 9 }
            Text { text: guiBridge.devFinetunedStoi.toFixed(3); color: cyan; font.pixelSize: 9 }

            Text { text: "PESQ"; color: white; font.pixelSize: 9 }
            Text { text: guiBridge.devPretrainedPesq.toFixed(3); color: white; font.pixelSize: 9 }
            Text { text: guiBridge.devFinetunedPesq.toFixed(3); color: cyan; font.pixelSize: 9 }

            Text { text: "SNR"; color: white; font.pixelSize: 9 }
            Text { text: guiBridge.devPretrainedSnr.toFixed(2) + " dB"; color: white; font.pixelSize: 9 }
            Text { text: guiBridge.devFinetunedSnr.toFixed(2) + " dB"; color: cyan; font.pixelSize: 9 }
        }

        Text {
            visible: guiBridge.devBenchmarkAvailable
            text: "FINE-TUNED SI-SDR IMPROVEMENT\n+" + guiBridge.devSiSdrImprovement.toFixed(2) + " dB"
            color: cyan
            font.pixelSize: 10
            font.bold: true
        }

        Text {
            visible: guiBridge.devBenchmarkAvailable
            text: guiBridge.devSiSdrImproved + " / " + guiBridge.devPairedEvaluations +
                  " paired cases improved" +
                  (guiBridge.devSiSdrDegraded > 0
                    ? (" (" + guiBridge.devSiSdrDegraded + " degraded)")
                    : "")
            color: white
            font.pixelSize: 9
        }

        Item {
            visible: guiBridge.devBenchmarkAvailable
            Layout.fillWidth: true
            Layout.preferredHeight: 72

            readonly property real chartMax: Math.max(guiBridge.devPretrainedSiSdr, guiBridge.devFinetunedSiSdr, 1.0)

            RowLayout {
                anchors.fill: parent
                spacing: 16

                ColumnLayout {
                    spacing: 4
                    Rectangle {
                        Layout.preferredWidth: 36
                        Layout.preferredHeight: Math.max(8, 56 * guiBridge.devPretrainedSiSdr / chartMax)
                        color: "#556677"
                    }
                    Text {
                        text: "Pretrained\n" + guiBridge.devPretrainedSiSdr.toFixed(2) + " dB"
                        color: dim
                        font.pixelSize: 8
                        horizontalAlignment: Text.AlignHCenter
                    }
                }

                ColumnLayout {
                    spacing: 4
                    Rectangle {
                        Layout.preferredWidth: 36
                        Layout.preferredHeight: Math.max(8, 56 * guiBridge.devFinetunedSiSdr / chartMax)
                        color: cyan
                    }
                    Text {
                        text: "Fine-tuned\n" + guiBridge.devFinetunedSiSdr.toFixed(2) + " dB"
                        color: dim
                        font.pixelSize: 8
                        horizontalAlignment: Text.AlignHCenter
                    }
                }

                Text {
                    text: "Mean SI-SDR (development)"
                    color: dim
                    font.pixelSize: 8
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }
            }
        }

        // --- Recording-disjoint ---
        Text {
            visible: guiBridge.rdBenchmarkAvailable
            text: guiBridge.rdBenchmarkTitle
            color: white
            font.pixelSize: 10
            font.bold: true
            Layout.topMargin: 10
        }

        Text {
            visible: guiBridge.rdBenchmarkAvailable && guiBridge.rdHoldoutNote.length > 0
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: warn
            font.pixelSize: 9
            text: guiBridge.rdHoldoutNote
        }

        GridLayout {
            visible: guiBridge.rdBenchmarkAvailable
            columns: 3
            columnSpacing: 8
            rowSpacing: 3
            Layout.fillWidth: true

            Text { text: "Metric"; color: dim; font.pixelSize: 9 }
            Text { text: "Pretrained"; color: dim; font.pixelSize: 9 }
            Text { text: "Fine-tuned"; color: dim; font.pixelSize: 9 }

            Text { text: "SI-SDR"; color: white; font.pixelSize: 9 }
            Text { text: guiBridge.rdPretrainedSiSdr.toFixed(2) + " dB"; color: white; font.pixelSize: 9 }
            Text { text: guiBridge.rdFinetunedSiSdr.toFixed(2) + " dB"; color: cyan; font.pixelSize: 9 }

            Text { text: "STOI"; color: white; font.pixelSize: 9 }
            Text { text: guiBridge.rdPretrainedStoi.toFixed(3); color: white; font.pixelSize: 9 }
            Text { text: guiBridge.rdFinetunedStoi.toFixed(3); color: cyan; font.pixelSize: 9 }

            Text { text: "PESQ"; color: white; font.pixelSize: 9 }
            Text { text: guiBridge.rdPretrainedPesq.toFixed(3); color: white; font.pixelSize: 9 }
            Text { text: guiBridge.rdFinetunedPesq.toFixed(3); color: cyan; font.pixelSize: 9 }

            Text { text: "SNR"; color: white; font.pixelSize: 9 }
            Text { text: guiBridge.rdPretrainedSnr.toFixed(2) + " dB"; color: white; font.pixelSize: 9 }
            Text { text: guiBridge.rdFinetunedSnr.toFixed(2) + " dB"; color: cyan; font.pixelSize: 9 }
        }

        Text {
            visible: guiBridge.rdBenchmarkAvailable
            text: "FINE-TUNED SI-SDR IMPROVEMENT\n+" + guiBridge.rdSiSdrImprovement.toFixed(2) + " dB"
            color: cyan
            font.pixelSize: 10
            font.bold: true
        }

        Text {
            visible: guiBridge.rdBenchmarkAvailable
            text: guiBridge.rdSiSdrImproved + " / " + guiBridge.rdPairedEvaluations +
                  " successful paired evaluations (" + guiBridge.rdSuccessfulEvaluations + " per model)"
            color: white
            font.pixelSize: 9
        }

        Text {
            visible: guiBridge.benchmarkLoaded
            text: "Evaluation information"
            color: dim
            font.pixelSize: 9
            font.bold: true
            Layout.topMargin: 8
        }

        Text {
            visible: guiBridge.devBenchmarkAvailable
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: dim
            font.pixelSize: 8
            text: "Development: rules " + guiBridge.devRulesVersion +
                  "; modes " + guiBridge.devEvaluationModes +
                  "; models " + guiBridge.benchmarkPretrainedModel + " vs " +
                  guiBridge.benchmarkFinetunedModel + "; offline reports " +
                  guiBridge.devPretrainedSource + " / " + guiBridge.devFinetunedSource
        }

        Text {
            visible: guiBridge.rdBenchmarkAvailable
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: dim
            font.pixelSize: 8
            text: "Recording-disjoint: rules " + guiBridge.rdRulesVersion +
                  "; models " + guiBridge.benchmarkPretrainedModel + " vs " +
                  guiBridge.benchmarkFinetunedModel
        }

        Button {
            text: metricsHelpOpen ? "Hide metric explanations" : "What do these metrics mean?"
            flat: true
            font.pixelSize: 9
            palette.buttonText: cyan
            onClicked: metricsHelpOpen = !metricsHelpOpen
        }

        ColumnLayout {
            visible: metricsHelpOpen
            Layout.fillWidth: true
            spacing: 4

            Text { text: "SI-SDR: Measures how well the enhanced signal preserves the target speech relative to distortion."; color: dim; font.pixelSize: 8; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            Text { text: "STOI: Measures speech intelligibility."; color: dim; font.pixelSize: 8; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            Text { text: "PESQ: Measures perceived speech quality."; color: dim; font.pixelSize: 8; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            Text { text: "SNR: Measures the ratio between desired signal power and noise power."; color: dim; font.pixelSize: 8; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            Text { text: "These metrics do not capture every aspect of human listening quality."; color: dim; font.pixelSize: 8; font.italic: true; wrapMode: Text.WordWrap; Layout.fillWidth: true }
        }
    }
}
