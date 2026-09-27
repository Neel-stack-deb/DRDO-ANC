import QtQuick
import QtQuick.Layouts

Item {
    id: root
    property string label: ""
    property string pretrained: ""
    property string finetuned: ""
    property string delta: ""

    property color cyan: "#00E5FF"
    property color white: "#E8EEF4"
    property color dim: "#8A9AAB"

    Layout.columnSpan: 4
    Layout.fillWidth: true
    implicitHeight: 40

    Rectangle {
        anchors.fill: parent
        radius: 8
        color: "#10151C"
        border.color: "#252D38"
        border.width: 1
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        spacing: 12

        Text {
            Layout.preferredWidth: 72
            text: label
            color: white
            font.pixelSize: 15
            font.bold: true
        }
        Text {
            Layout.fillWidth: true
            text: pretrained
            color: dim
            font.pixelSize: 15
            horizontalAlignment: Text.AlignHCenter
        }
        Text {
            Layout.fillWidth: true
            text: finetuned
            color: cyan
            font.pixelSize: 15
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
        }
        Text {
            Layout.preferredWidth: 72
            text: delta
            color: "#66FFCC"
            font.pixelSize: 14
            font.bold: true
            horizontalAlignment: Text.AlignRight
        }
    }
}
