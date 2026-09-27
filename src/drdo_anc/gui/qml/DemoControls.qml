import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

Item {
    id: root
    implicitHeight: column.implicitHeight
    property color white: "#F0F4F8"
    property color cyan: "#00E5FF"
    property color dim: "#8B95A7"
    property color buttonBg: "#151A22"
    property color buttonActive: "#00E5FF"

    ColumnLayout {
        id: column
        width: root.width
        spacing: 6

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

            Text {
                visible: guiBridge.isBenchmarkMode
                text: "Read-only results · switch to Demo or Live for audio"
                color: dim
                font.pixelSize: 12
                font.italic: true
            }
        }

        RowLayout {
            objectName: "modelRow"
            Layout.fillWidth: true
            spacing: 8
            visible: guiBridge.showAudioSelectors

            Text { text: "MODEL"; color: dim; font.pixelSize: 10; font.bold: true }
            DeviceCombo {
                id: modelBox
                objectName: "modelCombo"
                Layout.preferredWidth: 280
                model: guiBridge.modelLabels
                currentIndex: guiBridge.selectedModelIndex
                enabled: guiBridge.audioSelectorsEnabled
                onActivated: guiBridge.selectModel(index)
            }

            Item { Layout.fillWidth: true }
            CheckBox {
                objectName: "showAllDevicesBox"
                text: "Show all devices"
                checked: guiBridge.showAllDevices
                enabled: guiBridge.audioSelectorsEnabled
                onToggled: guiBridge.setShowAllDevices(checked)
                palette.windowText: dim
                palette.button: buttonBg
                palette.highlight: cyan
            }
            DemoButton {
                objectName: "refreshDevicesButton"
                label: "Refresh devices"
                enabled: guiBridge.audioSelectorsEnabled
                onActivated: guiBridge.refreshDevices()
            }
        }

        RowLayout {
            objectName: "inputDeviceRow"
            Layout.fillWidth: true
            spacing: 8
            visible: guiBridge.showAudioSelectors

            Text { text: "INPUT DEVICE"; color: dim; font.pixelSize: 10; font.bold: true }
            DeviceCombo {
                id: inputBox
                objectName: "inputDeviceCombo"
                Layout.fillWidth: true
                model: guiBridge.inputDeviceLabels
                currentIndex: guiBridge.selectedInputDeviceIndex
                enabled: guiBridge.audioSelectorsEnabled
                onActivated: guiBridge.selectInputDevice(index)
            }
        }

        RowLayout {
            objectName: "outputDeviceRow"
            Layout.fillWidth: true
            spacing: 8
            visible: guiBridge.showAudioSelectors

            Text { text: "OUTPUT DEVICE"; color: dim; font.pixelSize: 10; font.bold: true }
            DeviceCombo {
                id: outputBox
                objectName: "outputDeviceCombo"
                Layout.fillWidth: true
                model: guiBridge.outputDeviceLabels
                currentIndex: guiBridge.selectedOutputDeviceIndex
                enabled: guiBridge.audioSelectorsEnabled
                onActivated: guiBridge.selectOutputDevice(index)
            }
        }

        Text {
            objectName: "liveBlockReason"
            Layout.fillWidth: true
            visible: guiBridge.operationMode === "live" && guiBridge.liveBlockReason.length > 0
            text: guiBridge.liveBlockReason
            color: "#FF5577"
            font.pixelSize: 11
            wrapMode: Text.WordWrap
        }

        RowLayout {
            objectName: "scenarioRow"
            Layout.fillWidth: true
            spacing: 8
            visible: guiBridge.showDemoScenario

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
            objectName: "demoSafetyRow"
            Layout.fillWidth: true
            spacing: 8
            visible: guiBridge.showDemoSafety

            Text { text: "PREFLIGHT"; color: dim; font.pixelSize: 10; font.bold: true }
            DemoButton {
                objectName: "demoPreflightButton"
                label: "DEMO PREFLIGHT"
                onActivated: guiBridge.runDemoPreflight()
            }
            DemoButton {
                objectName: "resetDemoButton"
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

        Text {
            objectName: "preflightFailureText"
            Layout.fillWidth: true
            visible: guiBridge.showDemoSafety && guiBridge.preflightHasRun && guiBridge.preflightStatus === "FAILED"
            text: guiBridge.preflightCheckLines.join("\n")
            color: "#FF5577"
            font.pixelSize: 9
            font.family: "Consolas"
            wrapMode: Text.WordWrap
            maximumLineCount: 4
            elide: Text.ElideNone
        }

        RowLayout {
            objectName: "liveFallbackRow"
            Layout.fillWidth: true
            spacing: 8
            visible: guiBridge.showLiveFallback

            Text {
                Layout.fillWidth: true
                text: guiBridge.liveFallbackMessage
                color: "#FF5577"
                font.pixelSize: 11
                wrapMode: Text.WordWrap
            }
            DemoButton {
                objectName: "tryLiveAgainButton"
                label: "TRY AGAIN"
                onActivated: guiBridge.tryLiveAgain()
            }
            DemoButton {
                objectName: "useRecordedDemoButton"
                label: "USE RECORDED DEMO"
                onActivated: guiBridge.useRecordedDemo()
            }
        }

        RowLayout {
            objectName: "demoTransportRow"
            Layout.fillWidth: true
            spacing: 8
            visible: guiBridge.showDemoTransport

            Text { text: "TRANSPORT"; color: dim; font.pixelSize: 10; font.bold: true }
            DemoButton {
                objectName: "playButton"
                label: "Play"
                onActivated: guiBridge.play()
            }
            DemoButton {
                objectName: "pauseButton"
                label: "Pause"
                onActivated: guiBridge.pause()
            }
            DemoButton {
                objectName: "stopButton"
                label: "Stop"
                onActivated: guiBridge.stop()
            }
            DemoButton {
                objectName: "resetButton"
                label: "Reset"
                onActivated: guiBridge.resetDemo()
            }

            Item { Layout.fillWidth: true }

            Text {
                text: "OUTPUT"
                color: dim
                font.pixelSize: 10
                font.bold: true
            }
            DemoButton {
                objectName: "abRawButton"
                label: guiBridge.abMode === "raw" ? "● A — RAW" : "A — RAW"
                active: guiBridge.abMode === "raw"
                onActivated: guiBridge.selectAbRaw()
            }
            DemoButton {
                objectName: "abEnhancedButton"
                label: guiBridge.abMode === "enhanced" ? "● B — ENHANCED" : "B — ENHANCED"
                active: guiBridge.abMode === "enhanced"
                onActivated: guiBridge.selectAbEnhanced()
            }
        }

        RowLayout {
            objectName: "liveTransportRow"
            Layout.fillWidth: true
            spacing: 8
            visible: guiBridge.showLiveTransport

            Text { text: "TRANSPORT"; color: dim; font.pixelSize: 10; font.bold: true }
            DemoButton {
                objectName: "startLiveButton"
                visible: guiBridge.showStartLive
                enabled: guiBridge.startLiveEnabled
                label: "START LIVE"
                onActivated: guiBridge.startLive()
            }
            Text {
                objectName: "liveStartingLabel"
                visible: guiBridge.showLiveStarting
                text: "STARTING"
                color: cyan
                font.pixelSize: 12
                font.bold: true
            }
            DemoButton {
                objectName: "stopLiveButton"
                visible: guiBridge.showStopLive
                enabled: guiBridge.stopLiveEnabled
                label: "STOP"
                onActivated: guiBridge.stopLive()
            }
            Text {
                visible: guiBridge.operationMode === "live"
                text: "OUTPUT"
                color: dim
                font.pixelSize: 10
                font.bold: true
            }
            DemoButton {
                objectName: "liveAbRawButton"
                visible: guiBridge.operationMode === "live"
                label: guiBridge.abMode === "raw" ? "● A — RAW" : "A — RAW"
                active: guiBridge.abMode === "raw"
                onActivated: guiBridge.selectAbRaw()
            }
            DemoButton {
                objectName: "liveAbEnhancedButton"
                visible: guiBridge.operationMode === "live"
                label: guiBridge.abMode === "enhanced" ? "● B — ENHANCED" : "B — ENHANCED"
                active: guiBridge.abMode === "enhanced"
                onActivated: guiBridge.selectAbEnhanced()
            }
            DemoButton {
                objectName: "recoverLiveButton"
                visible: guiBridge.showRecoverLive
                label: "Recover"
                onActivated: guiBridge.recoverLive()
            }
        }

        PipelineChain {
            Layout.fillWidth: true
            Layout.preferredHeight: 34
            visible: guiBridge.showAudioSelectors
        }
    }
}
