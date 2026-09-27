import QtQuick

Rectangle {
    id: root
    property string metricName: ""
    property string pretrainedText: ""
    property string finetunedText: ""
    property string changeText: ""

    height: 42
    radius: 8
    color: "#10151C"
    border.color: "#2A3544"

    Row {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        spacing: 8

        Text {
            width: 78
            height: parent.height
            verticalAlignment: Text.AlignVCenter
            text: metricName
            color: "#F0F4F8"
            font.pixelSize: 15
            font.bold: true
        }
        Text {
            width: (parent.width - 102) / 3
            height: parent.height
            verticalAlignment: Text.AlignVCenter
            text: pretrainedText
            color: "#9AA8B8"
            font.pixelSize: 15
        }
        Text {
            width: (parent.width - 102) / 3
            height: parent.height
            verticalAlignment: Text.AlignVCenter
            text: finetunedText
            color: "#00E5FF"
            font.pixelSize: 15
            font.bold: true
        }
        Text {
            width: (parent.width - 102) / 3
            height: parent.height
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: Text.AlignRight
            text: changeText
            color: "#66FFCC"
            font.pixelSize: 14
            font.bold: true
        }
    }
}
