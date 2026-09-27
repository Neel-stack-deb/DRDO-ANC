import QtQuick

Rectangle {
    id: root
    property string cardTitle: ""
    property string cardSubtitle: ""
    property real pretrainedSiSdr: 0
    property real finetunedSiSdr: 0
    property real pretrainedStoi: 0
    property real finetunedStoi: 0
    property real pretrainedPesq: 0
    property real finetunedPesq: 0
    property real pretrainedSnr: 0
    property real finetunedSnr: 0
    property real deltaDb: 0
    property int improved: 0
    property int paired: 0
    property int degraded: 0
    property string extraDetail: ""
    property string barCaption: ""

    property color cyan: "#00E5FF"
    property color dim: "#9AA8B8"
    property color white: "#F0F4F8"

    height: body.implicitHeight + 36
    radius: 14
    color: "#141A24"
    border.color: "#3A4A5C"
    border.width: 1

    function signed(value, decimals, suffix) {
        var sign = value >= 0 ? "+" : ""
        return sign + value.toFixed(decimals) + suffix
    }

    Column {
        id: body
        x: 20
        y: 18
        width: root.width - 40
        spacing: 14

        Text {
            width: parent.width
            text: cardTitle
            color: white
            font.pixelSize: 20
            font.bold: true
            wrapMode: Text.WordWrap
        }

        Text {
            width: parent.width
            visible: cardSubtitle.length > 0
            text: cardSubtitle
            color: dim
            font.pixelSize: 14
            wrapMode: Text.WordWrap
        }

        Row {
            width: parent.width
            spacing: 8
            Text { width: 90; text: "Metric"; color: dim; font.pixelSize: 13; font.bold: true }
            Text { width: (parent.width - 106) / 3; text: "Pretrained"; color: dim; font.pixelSize: 13; font.bold: true }
            Text { width: (parent.width - 106) / 3; text: "Fine-tuned"; color: dim; font.pixelSize: 13; font.bold: true }
            Text { width: (parent.width - 106) / 3; text: "Change"; color: dim; font.pixelSize: 13; font.bold: true; horizontalAlignment: Text.AlignRight }
        }

        BenchmarkMetricLine {
            width: parent.width
            metricName: "SI-SDR"
            pretrainedText: pretrainedSiSdr.toFixed(2) + " dB"
            finetunedText: finetunedSiSdr.toFixed(2) + " dB"
            changeText: root.signed(finetunedSiSdr - pretrainedSiSdr, 2, " dB")
        }
        BenchmarkMetricLine {
            width: parent.width
            metricName: "STOI"
            pretrainedText: pretrainedStoi.toFixed(3)
            finetunedText: finetunedStoi.toFixed(3)
            changeText: root.signed(finetunedStoi - pretrainedStoi, 3, "")
        }
        BenchmarkMetricLine {
            width: parent.width
            metricName: "PESQ"
            pretrainedText: pretrainedPesq.toFixed(3)
            finetunedText: finetunedPesq.toFixed(3)
            changeText: root.signed(finetunedPesq - pretrainedPesq, 3, "")
        }
        BenchmarkMetricLine {
            width: parent.width
            metricName: "SNR"
            pretrainedText: pretrainedSnr.toFixed(2) + " dB"
            finetunedText: finetunedSnr.toFixed(2) + " dB"
            changeText: root.signed(finetunedSnr - pretrainedSnr, 2, " dB")
        }

        Row {
            width: parent.width
            spacing: 24

            Column {
                width: Math.min(420, Math.max(240, parent.width - 220))
                spacing: 8
                Row {
                    width: parent.width
                    spacing: 10
                    Text { width: 92; text: "Pretrained"; color: dim; font.pixelSize: 13 }
                    Rectangle {
                        width: Math.max(4, (parent.width - 150) * pretrainedSiSdr / Math.max(pretrainedSiSdr, finetunedSiSdr, 1))
                        height: 16
                        radius: 4
                        color: "#4A5A6A"
                    }
                    Text { text: pretrainedSiSdr.toFixed(2) + " dB"; color: white; font.pixelSize: 14; font.bold: true }
                }
                Row {
                    width: parent.width
                    spacing: 10
                    Text { width: 92; text: "Fine-tuned"; color: dim; font.pixelSize: 13 }
                    Rectangle {
                        width: Math.max(4, (parent.width - 150) * finetunedSiSdr / Math.max(pretrainedSiSdr, finetunedSiSdr, 1))
                        height: 16
                        radius: 4
                        color: cyan
                    }
                    Text { text: finetunedSiSdr.toFixed(2) + " dB"; color: cyan; font.pixelSize: 14; font.bold: true }
                }
            }

            Text {
                width: Math.max(120, parent.width - 248)
                text: barCaption
                color: dim
                font.pixelSize: 14
                wrapMode: Text.WordWrap
            }
        }

        Rectangle {
            width: parent.width
            height: hero.implicitHeight + 24
            radius: 10
            color: "#0C141C"
            border.color: "#2A6A7A"

            Column {
                id: hero
                x: 16
                y: 12
                width: parent.width - 32
                spacing: 4
                Text {
                    text: "Fine-tuned SI-SDR improvement"
                    color: dim
                    font.pixelSize: 13
                    font.bold: true
                }
                Text {
                    text: (deltaDb >= 0 ? "+" : "") + deltaDb.toFixed(2) + " dB"
                    color: cyan
                    font.pixelSize: 34
                    font.bold: true
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    color: white
                    font.pixelSize: 14
                    text: {
                        var line = improved + " / " + paired + " paired cases improved"
                        if (degraded > 0)
                            line += " (" + degraded + " degraded)"
                        if (extraDetail.length > 0)
                            line += " · " + extraDetail
                        return line
                    }
                }
            }
        }
    }
}
