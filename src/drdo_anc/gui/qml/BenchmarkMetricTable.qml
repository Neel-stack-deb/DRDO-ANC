import QtQuick
import QtQuick.Layouts

Item {
    id: root
    property real pretrainedSiSdr: 0
    property real finetunedSiSdr: 0
    property real pretrainedStoi: 0
    property real finetunedStoi: 0
    property real pretrainedPesq: 0
    property real finetunedPesq: 0
    property real pretrainedSnr: 0
    property real finetunedSnr: 0

    property color cyan: "#00E5FF"
    property color white: "#F0F4F8"
    property color dim: "#7A8A9C"
    property color rowBg: "#0D1118"

    implicitHeight: grid.implicitHeight

    GridLayout {
        id: grid
        anchors.left: parent.left
        anchors.right: parent.right
        columns: 4
        columnSpacing: 12
        rowSpacing: 8

        Text { text: "Metric"; color: dim; font.pixelSize: 13; font.bold: true }
        Text { text: "Pretrained"; color: dim; font.pixelSize: 13; font.bold: true }
        Text { text: "Fine-tuned"; color: dim; font.pixelSize: 13; font.bold: true }
        Text { text: "Δ"; color: dim; font.pixelSize: 13; font.bold: true }

        BenchmarkMetricRow {
            label: "SI-SDR"
            pretrained: pretrainedSiSdr.toFixed(2) + " dB"
            finetuned: finetunedSiSdr.toFixed(2) + " dB"
            delta: root.fmtDelta(finetunedSiSdr - pretrainedSiSdr, 2, " dB")
        }
        BenchmarkMetricRow {
            label: "STOI"
            pretrained: pretrainedStoi.toFixed(3)
            finetuned: finetunedStoi.toFixed(3)
            delta: root.fmtDelta(finetunedStoi - pretrainedStoi, 3, "")
        }
        BenchmarkMetricRow {
            label: "PESQ"
            pretrained: pretrainedPesq.toFixed(3)
            finetuned: finetunedPesq.toFixed(3)
            delta: root.fmtDelta(finetunedPesq - pretrainedPesq, 3, "")
        }
        BenchmarkMetricRow {
            label: "SNR"
            pretrained: pretrainedSnr.toFixed(2) + " dB"
            finetuned: finetunedSnr.toFixed(2) + " dB"
            delta: root.fmtDelta(finetunedSnr - pretrainedSnr, 2, " dB")
        }
    }

    function fmtDelta(value, decimals, suffix) {
        var sign = value >= 0 ? "+" : ""
        return sign + value.toFixed(decimals) + suffix
    }
}
