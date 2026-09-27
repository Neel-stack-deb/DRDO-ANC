import QtQuick
import QtQuick.Layouts

Item {
    id: root
    property real pretrained: 0
    property real finetuned: 0
    property string caption: ""

    property color cyan: "#00E5FF"
    property color dim: "#8A9AAB"
    readonly property real chartMax: Math.max(pretrained, finetuned, 1.0)

    RowLayout {
        anchors.fill: parent
        spacing: 28

        ColumnLayout {
            spacing: 8
            Layout.alignment: Qt.AlignBottom

            Item {
                Layout.preferredWidth: 56
                Layout.preferredHeight: 72
                Rectangle {
                    anchors.bottom: parent.bottom
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 48
                    height: Math.max(12, 68 * pretrained / chartMax)
                    radius: 6
                    gradient: Gradient {
                        orientation: Gradient.Vertical
                        GradientStop { position: 0.0; color: "#556677" }
                        GradientStop { position: 1.0; color: "#334455" }
                    }
                }
            }
            Text {
                text: "Pretrained"
                color: dim
                font.pixelSize: 13
                horizontalAlignment: Text.AlignHCenter
                Layout.preferredWidth: 80
            }
            Text {
                text: pretrained.toFixed(2) + " dB"
                color: "#C0CCD8"
                font.pixelSize: 16
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                Layout.preferredWidth: 80
            }
        }

        ColumnLayout {
            spacing: 8
            Layout.alignment: Qt.AlignBottom

            Item {
                Layout.preferredWidth: 56
                Layout.preferredHeight: 72
                Rectangle {
                    anchors.bottom: parent.bottom
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 48
                    height: Math.max(12, 68 * finetuned / chartMax)
                    radius: 6
                    gradient: Gradient {
                        orientation: Gradient.Vertical
                        GradientStop { position: 0.0; color: cyan }
                        GradientStop { position: 1.0; color: "#0088AA" }
                    }
                    border.color: "#80FFFFFF"
                    border.width: 1
                }
            }
            Text {
                text: "Fine-tuned"
                color: dim
                font.pixelSize: 13
                horizontalAlignment: Text.AlignHCenter
                Layout.preferredWidth: 80
            }
            Text {
                text: finetuned.toFixed(2) + " dB"
                color: cyan
                font.pixelSize: 16
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                Layout.preferredWidth: 80
            }
        }

        Text {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            text: caption
            color: dim
            font.pixelSize: 14
            wrapMode: Text.WordWrap
        }
    }
}
