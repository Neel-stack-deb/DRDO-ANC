import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

Item {
    id: root
    property color white: "#F0F4F8"
    property color cyan: "#00E5FF"
    property color dim: "#666666"
    property color buttonBg: "#151A22"
    property color buttonActive: "#00E5FF"

    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text { text: "MODE"; color: dim; font.pixelSize: 10; font.bold: true }

            DemoButton {
                label: "DEMO MODE"
                active: guiBridge.operationMode === "demo"
                onActivated: guiBridge.setDemoMode()
            }
            DemoButton {
                label: "LIVE"
                active: guiBridge.operationMode === "live"
                enabled: guiBridge.liveCanStart || guiBridge.operationMode === "live"
                onActivated: guiBridge.setLiveMode()
            }
            DemoButton {
                label: "BENCHMARK"
                active: guiBridge.operationMode === "benchmark"
                onActivated: guiBridge.setBenchmarkMode()
            }

            Item { Layout.fillWidth: true }
            Text { text: guiBridge.demoScenario; color: cyan; font.pixelSize: 10 }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text { text: "MODEL"; color: dim; font.pixelSize: 10; font.bold: true }
            DeviceCombo {
                id: modelBox
                Layout.preferredWidth: 280
                model: guiBridge.modelLabels
                currentIndex: guiBridge.selectedModelIndex
                enabled: !guiBridge.devicesLocked
                onActivated: guiBridge.selectModel(index)
            }

            Item { Layout.fillWidth: true }
            CheckBox {
                text: "Show all devices"
                checked: guiBridge.showAllDevices
                enabled: !guiBridge.devicesLocked
                onToggled: guiBridge.setShowAllDevices(checked)
                palette.windowText: dim
                palette.button: buttonBg
                palette.highlight: cyan
            }
            DemoButton {
                label: "Refresh devices"
                enabled: !guiBridge.devicesLocked
                onActivated: guiBridge.refreshDevices()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text { text: "INPUT DEVICE"; color: dim; font.pixelSize: 10; font.bold: true }
            DeviceCombo {
                id: inputBox
                Layout.fillWidth: true
                model: guiBridge.inputDeviceLabels
                currentIndex: guiBridge.selectedInputDeviceIndex
                enabled: !guiBridge.devicesLocked
                onActivated: guiBridge.selectInputDevice(index)
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text { text: "OUTPUT DEVICE"; color: dim; font.pixelSize: 10; font.bold: true }
            DeviceCombo {
                id: outputBox
                Layout.fillWidth: true
                model: guiBridge.outputDeviceLabels
                currentIndex: guiBridge.selectedOutputDeviceIndex
                enabled: !guiBridge.devicesLocked
                onActivated: guiBridge.selectOutputDevice(index)
            }
        }

        Text {
            Layout.fillWidth: true
            visible: !guiBridge.liveCanStart && guiBridge.liveBlockReason.length > 0
            text: guiBridge.liveBlockReason
            color: "#FF5577"
            font.pixelSize: 11
            wrapMode: Text.WordWrap
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            visible: guiBridge.operationMode === "demo"

            Text { text: "SCENARIO"; color: dim; font.pixelSize: 10; font.bold: true }

            Repeater {
                model: guiBridge.scenarioLabels
                delegate: DemoButton {
                    label: (index + 1) + " " + modelData
                    active: guiBridge.selectedScenarioIndex === index
                    onActivated: guiBridge.selectScenario(index)
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text { text: "SIH SAFETY"; color: dim; font.pixelSize: 10; font.bold: true }
            DemoButton {
                label: "DEMO PREFLIGHT"
                onActivated: guiBridge.runDemoPreflight()
            }
            DemoButton {
                label: "RESET DEMO"
                onActivated: guiBridge.emergencyResetDemo()
            }
            Item { Layout.fillWidth: true }
            Text {
                visible: guiBridge.preflightHasRun
                text: guiBridge.preflightSummary
                color: guiBridge.preflightStatus === "FAILED" ? "#FF5577"
                    : (guiBridge.preflightStatus === "WARNING" ? "#FFAA44" : cyan)
                font.pixelSize: 11
                font.bold: true
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            visible: guiBridge.preflightHasRun

            Text {
                text: "DEMO PREFLIGHT"
                color: dim
                font.pixelSize: 10
                font.bold: true
            }
            Repeater {
                model: guiBridge.preflightCheckLines
                delegate: Text {
                    text: modelData
                    color: modelData.startsWith("✓") ? "#88CCAA" : "#FF5577"
                    font.pixelSize: 10
                    font.family: "Consolas"
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            visible: guiBridge.liveFallbackOffered

            Text {
                Layout.fillWidth: true
                text: guiBridge.liveFallbackMessage
                color: "#FF5577"
                font.pixelSize: 11
                wrapMode: Text.WordWrap
            }
            DemoButton {
                label: "TRY AGAIN"
                onActivated: guiBridge.tryLiveAgain()
            }
            DemoButton {
                label: "USE RECORDED DEMO"
                onActivated: guiBridge.useRecordedDemo()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text { text: "TRANSPORT"; color: dim; font.pixelSize: 10; font.bold: true }
            DemoButton { label: "Play"; onActivated: guiBridge.play() }
            DemoButton { label: "Pause"; onActivated: guiBridge.pause() }
            DemoButton {
                label: "Stop"
                onActivated: guiBridge.stop()
            }
            DemoButton {
                visible: guiBridge.operationMode === "demo"
                label: "Reset"
                onActivated: guiBridge.resetDemo()
            }
            DemoButton {
                visible: guiBridge.operationMode === "live" && guiBridge.liveStatus === "ERROR"
                label: "Recover"
                onActivated: guiBridge.recoverLive()
            }

            Item { Layout.fillWidth: true }

            Text {
                visible: guiBridge.operationMode === "demo"
                text: "A/B"
                color: dim
                font.pixelSize: 10
                font.bold: true
            }
            DemoButton {
                visible: guiBridge.operationMode === "demo"
                label: "A Raw"
                active: guiBridge.abMode === "raw"
                onActivated: guiBridge.selectAbRaw()
            }
            DemoButton {
                visible: guiBridge.operationMode === "demo"
                label: "B Enhanced"
                active: guiBridge.abMode === "enhanced"
                onActivated: guiBridge.selectAbEnhanced()
            }
        }

        PipelineChain {
            Layout.fillWidth: true
            Layout.preferredHeight: 24
        }
    }
}
