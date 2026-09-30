import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root
    property string title: ""
    property string subtitle: ""
    default property alias content: innerLayout.data

    radius: 14
    color: "#141A24"
    border.color: "#35E5FF44"
    border.width: 1

    Rectangle {
        anchors.fill: parent
        radius: parent.radius
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#1A2230" }
            GradientStop { position: 1.0; color: "#0E1218" }
        }
        opacity: 0.95
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 14

        Text {
            visible: root.title.length > 0
            text: root.title
            color: "#F0F4F8"
            font.pixelSize: 20
            font.bold: true
            font.letterSpacing: 0.5
        }

        Text {
            visible: root.subtitle.length > 0
            Layout.fillWidth: true
            text: root.subtitle
            color: "#9AA8B8"
            font.pixelSize: 14
            wrapMode: Text.WordWrap
            lineHeight: 1.25
            lineHeightMode: Text.ProportionalHeight
        }

        ColumnLayout {
            id: innerLayout
            Layout.fillWidth: true
            spacing: 12
        }
    }
}
