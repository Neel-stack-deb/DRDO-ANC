import QtQuick

Rectangle {
    id: root
    property string label: ""
    property bool active: false
    signal activated()

    width: labelItem.width + 20
    height: 32
    radius: 6
    opacity: enabled ? 1.0 : 0.4
    color: active ? "#00E5FF" : (mouse.pressed ? "#1E2836" : "#151A22")
    border.color: active ? "#00E5FF" : (mouse.containsMouse ? "#45E5FF88" : "#2A3544")
    border.width: active ? 1 : (mouse.containsMouse ? 2 : 1)

    scale: mouse.pressed ? 0.97 : 1.0
    Behavior on scale { NumberAnimation { duration: 80 } }
    Behavior on border.color { ColorAnimation { duration: 120 } }

    Text {
        id: labelItem
        anchors.centerIn: parent
        text: root.label
        color: active ? "#000000" : "#F0F4F8"
        font.pixelSize: 11
        font.bold: active
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        enabled: root.enabled
        hoverEnabled: true
        onClicked: root.activated()
    }
}
