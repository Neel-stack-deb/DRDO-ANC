import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root
    property real deltaDb: 0
    property int improved: 0
    property int paired: 0
    property int degraded: 0
    property string detailSuffix: ""

    radius: 12
    color: "#0A1218"
    border.color: "#40E5FF66"
    border.width: 1
    implicitHeight: col.implicitHeight + 28

    ColumnLayout {
        id: col
        anchors.fill: parent
        anchors.margins: 16
        spacing: 6

        Text {
            text: "Fine-tuned SI-SDR improvement"
            color: "#9AA8B8"
            font.pixelSize: 13
            font.bold: true
            font.letterSpacing: 0.5
        }

        Text {
            text: (deltaDb >= 0 ? "+" : "") + deltaDb.toFixed(2) + " dB"
            color: "#00E5FF"
            font.pixelSize: 36
            font.bold: true
        }

        Text {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: "#D0DCE8"
            font.pixelSize: 14
            text: {
                var base = improved + " / " + paired + " paired cases improved"
                if (degraded > 0)
                    base += " (" + degraded + " degraded)"
                if (detailSuffix.length > 0)
                    base += " · " + detailSuffix
                return base
            }
        }
    }
}
