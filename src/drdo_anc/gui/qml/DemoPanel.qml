import QtQuick
import QtQuick.Layouts

Item {
    id: root
    property color white: "#F0F4F8"
    property color cyan: "#00E5FF"
    property color dim: "#888888"

    ColumnLayout {
        anchors.fill: parent
        spacing: 6

        Text {
            visible: guiBridge.isDemoMode
            text: guiBridge.demoStatus
            color: cyan
            font.pixelSize: 13
            font.bold: true
        }

        Text {
            visible: guiBridge.isDemoMode
            text: guiBridge.demoScenario
            color: white
            font.pixelSize: 11
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            elide: Text.ElideRight
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Text {
                text: guiBridge.audioStatus
                color: dim
                font.pixelSize: 10
            }
            Text {
                text: guiBridge.abMode === "enhanced" ? "B Enhanced" : "A Raw"
                color: cyan
                font.pixelSize: 10
                font.bold: true
            }
            Text {
                text: guiBridge.demoDurationSeconds.toFixed(1) + " s"
                color: dim
                font.pixelSize: 10
            }
        }

        Text {
            visible: guiBridge.isDemoMode && guiBridge.missingDemoCategories.length > 0
            text: "Extra scenarios need local WAVs (drone / vehicle / impulsive)."
            color: "#AA8866"
            font.pixelSize: 9
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
    }
}
