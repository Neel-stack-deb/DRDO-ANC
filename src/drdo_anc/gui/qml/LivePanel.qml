import QtQuick
import QtQuick.Layouts

Item {
    id: root
    property color white: "#F0F4F8"
    property color cyan: "#00E5FF"
    property color dim: "#888888"

    ColumnLayout {
        anchors.fill: parent
        spacing: 4

        Text {
            text: "LIVE MODE"
            color: dim
            font.pixelSize: 9
            font.bold: true
        }

        Text {
            text: "State: " + guiBridge.liveStatus
            color: cyan
            font.pixelSize: 11
            font.bold: true
            Layout.fillWidth: true
        }

        Text {
            visible: guiBridge.errorMessage.length > 0 && guiBridge.operationMode === "live"
            text: guiBridge.errorMessage
            color: "#FF5577"
            font.pixelSize: 10
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        Text {
            text: "Active model"
            color: dim
            font.pixelSize: 9
            font.bold: true
            Layout.topMargin: 4
        }
        Text {
            text: guiBridge.modelName
            color: white
            font.pixelSize: 10
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }

        Text {
            text: "Input device"
            color: dim
            font.pixelSize: 9
            font.bold: true
            Layout.topMargin: 6
        }
        Text {
            text: guiBridge.liveInputSummary
            color: white
            font.pixelSize: 10
            lineHeight: 1.25
            lineHeightMode: Text.ProportionalHeight
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }

        Text {
            text: "Output device"
            color: dim
            font.pixelSize: 9
            font.bold: true
            Layout.topMargin: 6
        }
        Text {
            text: guiBridge.liveOutputSummary
            color: white
            font.pixelSize: 10
            lineHeight: 1.25
            lineHeightMode: Text.ProportionalHeight
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }

        GridLayout {
            columns: 2
            columnSpacing: 12
            rowSpacing: 2
            Layout.fillWidth: true
            Layout.topMargin: 8

            Text { text: "Sample rate"; color: dim; font.pixelSize: 10 }
            Text { text: guiBridge.sampleRate + " Hz"; color: white; font.pixelSize: 10 }

            Text { text: "Processing"; color: dim; font.pixelSize: 10 }
            Text {
                text: guiBridge.processingTimeMs.toFixed(2) + " ms"
                color: white
                font.pixelSize: 10
            }

            Text { text: "RTF"; color: dim; font.pixelSize: 10 }
            Text {
                text: guiBridge.realtimeFactor.toFixed(2) + "x"
                color: white
                font.pixelSize: 10
            }

            Text { text: "Input overflows"; color: dim; font.pixelSize: 10 }
            Text {
                text: guiBridge.liveInputOverflows
                color: white
                font.pixelSize: 10
            }
        }

        Item { Layout.fillHeight: true }
    }
}
