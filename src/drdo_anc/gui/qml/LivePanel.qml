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

            Text { text: guiBridge.processingLatencyLabel; color: dim; font.pixelSize: 10 }
            Text {
                text: guiBridge.processingMeasured
                    ? guiBridge.processingValueText + " ms"
                    : guiBridge.processingValueText
                color: white
                font.pixelSize: 10
            }

            Text { text: guiBridge.rtfLabel; color: dim; font.pixelSize: 10 }
            Text {
                text: guiBridge.rtfMeasured
                    ? guiBridge.rtfValueText + "x"
                    : guiBridge.rtfValueText
                color: white
                font.pixelSize: 10
            }

            Text { text: guiBridge.overflowLabel; color: dim; font.pixelSize: 10 }
            Text {
                text: guiBridge.overflowValueText
                color: white
                font.pixelSize: 10
            }
        }

        Item { Layout.fillHeight: true }
    }
}
