import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Controls

Window {
    id: mainWindow
    width: 1024
    height: 960
    visible: true
    title: qsTr("DRDO-ANC Telemetry Console")

    Shortcut {
        sequence: "Space"
        onActivated: {
            if (guiBridge.operationMode === "demo") {
                if (guiBridge.playbackState === "playing")
                    guiBridge.pause()
                else
                    guiBridge.play()
            } else if (guiBridge.operationMode === "live") {
                if (guiBridge.liveStatus === "LIVE" || guiBridge.liveStatus === "STARTING")
                    guiBridge.stopLive()
                else if (guiBridge.liveStatus === "IDLE")
                    guiBridge.startLive()
            }
        }
    }
    Shortcut { sequence: "A"; onActivated: { if (guiBridge.operationMode === "demo") guiBridge.selectAbRaw() } }
    Shortcut { sequence: "B"; onActivated: { if (guiBridge.operationMode === "demo") guiBridge.selectAbEnhanced() } }
    Shortcut { sequence: "1"; onActivated: { if (guiBridge.operationMode === "demo") guiBridge.selectScenario(0) } }
    Shortcut { sequence: "2"; onActivated: { if (guiBridge.operationMode === "demo") guiBridge.selectScenario(1) } }

    // Deep Premium Dark Palette
    property color black: "#05070A"
    property color white: "#F0F4F8"
    property color cyan: "#00E5FF"
    property color darkGrey: "#0F1218"
    property color lightGrey: "#2A2E35"
    
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#0B101E" }
            GradientStop { position: 1.0; color: "#000000" }
        }
    }
    
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 16
        
        // Header
        RowLayout {
            Layout.fillWidth: true
            
            Text {
                text: "DRDO-ANC"
                color: white
                font.pixelSize: 32
                font.bold: true
                font.letterSpacing: -1
                Layout.alignment: Qt.AlignLeft
            }
            
            Text {
                objectName: "modeBanner"
                text: guiBridge.modeBanner
                color: cyan
                font.pixelSize: 32
                font.bold: true
                Layout.alignment: Qt.AlignLeft
            }
            
            Item { Layout.fillWidth: true }
            
            // System properties small text
            ColumnLayout {
                spacing: 2
                Layout.alignment: Qt.AlignRight
                Text { text: "MODEL: " + guiBridge.modelName; color: lightGrey; font.pixelSize: 10 }
                Text { text: "SAMPLE RATE: " + guiBridge.sampleRate; color: lightGrey; font.pixelSize: 10 }
                Text { text: "GUI FPS: 30"; color: lightGrey; font.pixelSize: 10 }
            }
        }
        
        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: lightGrey }

        Text {
            objectName: "modeDescription"
            Layout.fillWidth: true
            text: guiBridge.modeDescription
            color: "#8B95A7"
            font.pixelSize: 12
            wrapMode: Text.WordWrap
        }

        Text {
            Layout.fillWidth: true
            visible: guiBridge.errorMessage.length > 0
                    && !guiBridge.liveFallbackOffered
            text: "ERROR: " + guiBridge.errorMessage
            color: "#FF5577"
            font.pixelSize: 12
            wrapMode: Text.WordWrap
        }

        DemoControls {
            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight
        }

        BenchmarkPanel {
            Layout.fillWidth: true
            Layout.fillHeight: guiBridge.isBenchmarkMode
            Layout.preferredHeight: guiBridge.isBenchmarkMode ? -1 : 0
            visible: guiBridge.isBenchmarkMode
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 10
            visible: !guiBridge.isBenchmarkMode

            Text {
                objectName: "activityCaption"
                Layout.fillWidth: true
                visible: guiBridge.activityCaption.length > 0
                color: cyan
                font.pixelSize: 14
                font.bold: true
                elide: Text.ElideRight
                text: guiBridge.activityCaption
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 12

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 4

                    Text {
                        text: guiBridge.operationMode === "demo"
                            ? guiBridge.demoInputLabel
                            : "RAW MIC INPUT"
                        color: white
                        font.pixelSize: 16
                        font.bold: true
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        color: "#08FFFFFF"
                        border.color: "#15FFFFFF"
                        border.width: 1
                        radius: 8

                        Waveform {
                            id: inputWaveform
                            anchors.fill: parent
                            lineColor: cyan
                        }
                    }

                    Connections {
                        target: guiBridge
                        function onInputWaveformUpdated(data) { inputWaveform.updateData(data); }
                    }
                }

                Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: lightGrey }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 4

                    Text {
                        text: guiBridge.operationMode === "demo"
                            ? guiBridge.demoOutputLabel
                            : "ENHANCED OUTPUT"
                        color: white
                        font.pixelSize: 16
                        font.bold: true
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        color: "#08FFFFFF"
                        border.color: "#15FFFFFF"
                        border.width: 1
                        radius: 8

                        Waveform {
                            id: outputWaveform
                            anchors.fill: parent
                            lineColor: cyan
                        }
                    }

                    Connections {
                        target: guiBridge
                        function onOutputWaveformUpdated(data) { outputWaveform.updateData(data); }
                    }
                }

                Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: lightGrey }

                Metrics {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 210
                }
            }
        }
    }
}
