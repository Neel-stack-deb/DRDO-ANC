import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

ScrollView {
    id: root
    clip: true
    contentWidth: availableWidth

    property color cyan: "#00E5FF"
    property color dim: "#9AA8B8"
    property color white: "#F0F4F8"
    property color warn: "#FFAA66"
    property bool metricsHelpOpen: false

    function deltaText(value, decimals, suffix) {
        var sign = value >= 0 ? "+" : ""
        return sign + value.toFixed(decimals) + suffix
    }

    Column {
        width: root.availableWidth > 0 ? root.availableWidth : root.width
        spacing: 18
        topPadding: 4
        bottomPadding: 24

        Row {
            width: parent.width
            spacing: 12

            Rectangle {
                width: 4
                height: 52
                radius: 2
                color: cyan
            }

            Column {
                width: parent.width - 16
                spacing: 6
                Text {
                    text: "Offline benchmark results"
                    color: cyan
                    font.pixelSize: 26
                    font.bold: true
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    color: dim
                    font.pixelSize: 15
                    text: "SIH-26 evaluation protocol · pretrained vs fine-tuned · not live microphone data"
                }
            }
        }

        Text {
            visible: !guiBridge.benchmarkLoaded
            width: parent.width
            wrapMode: Text.WordWrap
            color: warn
            font.pixelSize: 16
            text: guiBridge.benchmarkUnavailableMessage.length > 0
                ? guiBridge.benchmarkUnavailableMessage
                : "Benchmark results unavailable."
        }

        Text {
            visible: guiBridge.benchmarkPartialWarning.length > 0
            width: parent.width
            wrapMode: Text.WordWrap
            color: warn
            font.pixelSize: 14
            text: guiBridge.benchmarkPartialWarning
        }

        BenchmarkResultCard {
            visible: guiBridge.devBenchmarkAvailable
            width: parent.width
            cardTitle: guiBridge.devBenchmarkTitle
            cardSubtitle: guiBridge.devBenchmarkContext
            pretrainedSiSdr: guiBridge.devPretrainedSiSdr
            finetunedSiSdr: guiBridge.devFinetunedSiSdr
            pretrainedStoi: guiBridge.devPretrainedStoi
            finetunedStoi: guiBridge.devFinetunedStoi
            pretrainedPesq: guiBridge.devPretrainedPesq
            finetunedPesq: guiBridge.devFinetunedPesq
            pretrainedSnr: guiBridge.devPretrainedSnr
            finetunedSnr: guiBridge.devFinetunedSnr
            deltaDb: guiBridge.devSiSdrImprovement
            improved: guiBridge.devSiSdrImproved
            paired: guiBridge.devPairedEvaluations
            degraded: guiBridge.devSiSdrDegraded
            barCaption: "Mean SI-SDR · development"
        }

        BenchmarkResultCard {
            visible: guiBridge.rdBenchmarkAvailable
            width: parent.width
            cardTitle: guiBridge.rdBenchmarkTitle
            cardSubtitle: guiBridge.rdHoldoutNote
            pretrainedSiSdr: guiBridge.rdPretrainedSiSdr
            finetunedSiSdr: guiBridge.rdFinetunedSiSdr
            pretrainedStoi: guiBridge.rdPretrainedStoi
            finetunedStoi: guiBridge.rdFinetunedStoi
            pretrainedPesq: guiBridge.rdPretrainedPesq
            finetunedPesq: guiBridge.rdFinetunedPesq
            pretrainedSnr: guiBridge.rdPretrainedSnr
            finetunedSnr: guiBridge.rdFinetunedSnr
            deltaDb: guiBridge.rdSiSdrImprovement
            improved: guiBridge.rdSiSdrImproved
            paired: guiBridge.rdPairedEvaluations
            degraded: 0
            extraDetail: guiBridge.rdSuccessfulEvaluations + " evaluations per model"
            barCaption: "Mean SI-SDR · recording-disjoint"
        }

        Rectangle {
            visible: guiBridge.benchmarkLoaded
            width: parent.width
            height: metaCol.implicitHeight + 32
            radius: 12
            color: "#121820"
            border.color: "#2A3544"

            Column {
                id: metaCol
                x: 18
                y: 16
                width: parent.width - 36
                spacing: 8

                Text {
                    text: "Evaluation notes"
                    color: white
                    font.pixelSize: 16
                    font.bold: true
                }
                Text {
                    visible: guiBridge.devBenchmarkAvailable
                    width: parent.width
                    wrapMode: Text.WordWrap
                    color: dim
                    font.pixelSize: 14
                    text: "Development · " + guiBridge.devRulesVersion +
                          " · " + guiBridge.devEvaluationModes +
                          " · " + guiBridge.benchmarkPretrainedModel +
                          " vs " + guiBridge.benchmarkFinetunedModel
                }
                Text {
                    visible: guiBridge.rdBenchmarkAvailable
                    width: parent.width
                    wrapMode: Text.WordWrap
                    color: dim
                    font.pixelSize: 14
                    text: "Recording-disjoint · " + guiBridge.rdRulesVersion
                }
                Text {
                    text: metricsHelpOpen ? "Hide metric guide" : "What do these metrics mean?"
                    color: cyan
                    font.pixelSize: 14
                    font.underline: helpMouse.containsMouse
                    MouseArea {
                        id: helpMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: metricsHelpOpen = !metricsHelpOpen
                    }
                }
                Text {
                    visible: metricsHelpOpen
                    width: parent.width
                    wrapMode: Text.WordWrap
                    color: dim
                    font.pixelSize: 14
                    text: "SI-SDR — speech vs distortion (higher is better).\n" +
                          "STOI — intelligibility, 0 to 1.\n" +
                          "PESQ — perceived quality.\n" +
                          "SNR — signal-to-noise ratio in dB."
                }
            }
        }
    }
}
