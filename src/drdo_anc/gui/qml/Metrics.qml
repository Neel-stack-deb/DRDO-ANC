import QtQuick
import QtQuick.Layouts

Item {
    id: root
    
    property color white: "#FFFFFF"
    property color cyan: "#00E5FF"
    property color darkGrey: "#222222"
    property color lightGrey: "#555555"
    
    ColumnLayout {
        anchors.fill: parent
        spacing: 24
        
        // --- Dual Volume Meters ---
        RowLayout {
            Layout.fillWidth: true
            spacing: 32
            
            // Peak/RMS Labels
            ColumnLayout {
                spacing: 12
                Text { text: "PEAK"; color: white; font.pixelSize: 18; font.bold: true }
                Text { text: "RMS"; color: white; font.pixelSize: 18; font.bold: true }
            }
            
            // Input Meters
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 12
                
                // Input Peak
                Item {
                    Layout.fillWidth: true; Layout.preferredHeight: 14; clip: true
                    Rectangle { anchors.fill: parent; color: "#111111"; radius: 2 }
                    Rectangle { 
                        width: parent.width; height: parent.height; radius: 2
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: "#00E5FF" }
                            GradientStop { position: 0.7; color: "#00FF88" }
                            GradientStop { position: 0.9; color: "#FFFF00" }
                            GradientStop { position: 1.0; color: "#FF0044" }
                        }
                    }
                    Rectangle {
                        color: "#111111"
                        height: parent.height
                        width: parent.width - (parent.width * Math.max(0, (guiBridge.inputPeakDb + 80) / 80))
                        anchors.right: parent.right
                    }
                }
                
                // Input RMS
                Item {
                    Layout.fillWidth: true; Layout.preferredHeight: 14; clip: true
                    Rectangle { anchors.fill: parent; color: "#111111"; radius: 2 }
                    Rectangle { 
                        width: parent.width; height: parent.height; radius: 2
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: "#00E5FF" }
                            GradientStop { position: 0.7; color: "#00FF88" }
                            GradientStop { position: 0.9; color: "#FFFF00" }
                            GradientStop { position: 1.0; color: "#FF0044" }
                        }
                    }
                    Rectangle {
                        color: "#111111"
                        height: parent.height
                        width: parent.width - (parent.width * Math.max(0, (guiBridge.inputLevelDb + 80) / 80))
                        anchors.right: parent.right
                    }
                }
            }
            
            Rectangle { Layout.preferredWidth: 1; Layout.fillHeight: true; color: "#333333" }
            
            // Output Meters
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 12
                
                // Output Peak
                Item {
                    Layout.fillWidth: true; Layout.preferredHeight: 14; clip: true
                    Rectangle { anchors.fill: parent; color: "#111111"; radius: 2 }
                    Rectangle { 
                        width: parent.width; height: parent.height; radius: 2
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: "#00E5FF" }
                            GradientStop { position: 0.7; color: "#00FF88" }
                            GradientStop { position: 0.9; color: "#FFFF00" }
                            GradientStop { position: 1.0; color: "#FF0044" }
                        }
                    }
                    Rectangle {
                        color: "#111111"
                        height: parent.height
                        width: parent.width - (parent.width * Math.max(0, (guiBridge.outputPeakDb + 80) / 80))
                        anchors.right: parent.right
                    }
                }
                
                // Output RMS
                Item {
                    Layout.fillWidth: true; Layout.preferredHeight: 14; clip: true
                    Rectangle { anchors.fill: parent; color: "#111111"; radius: 2 }
                    Rectangle { 
                        width: parent.width; height: parent.height; radius: 2
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: "#00E5FF" }
                            GradientStop { position: 0.7; color: "#00FF88" }
                            GradientStop { position: 0.9; color: "#FFFF00" }
                            GradientStop { position: 1.0; color: "#FF0044" }
                        }
                    }
                    Rectangle {
                        color: "#111111"
                        height: parent.height
                        width: parent.width - (parent.width * Math.max(0, (guiBridge.outputLevelDb + 80) / 80))
                        anchors.right: parent.right
                    }
                }
            }
        }
        
        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: lightGrey }
        
        // --- Data Grids with Sparklines ---
        GridLayout {
            Layout.fillWidth: true
            columns: 4
            columnSpacing: 24
            
            // Processing Latency
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text { text: "PROCESSING LATENCY"; color: white; font.pixelSize: 14 }
                RowLayout {
                    Text { text: guiBridge.processingTimeMs.toFixed(2); color: white; font.pixelSize: 42; font.bold: true }
                    Text { text: "ms"; color: white; font.pixelSize: 20; anchors.bottom: parent.bottom; anchors.bottomMargin: 6 }
                }
                Text { text: "HISTORY SPARKLINE"; color: cyan; font.pixelSize: 8; font.bold: true }
                Sparkline { id: sparkProc; Layout.fillWidth: true; Layout.preferredHeight: 40; yMin: 0; yMax: 10 }
                Connections { target: guiBridge; function onHistoryUpdated() { sparkProc.updateData(guiBridge.procTimeHistory); } }
            }
            
            // Buffer Saturation
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text { text: "BUFFER SATURATION"; color: white; font.pixelSize: 14 }
                RowLayout {
                    Text { text: guiBridge.bufferFillPercent.toFixed(2); color: white; font.pixelSize: 42; font.bold: true }
                    Text { text: "%"; color: white; font.pixelSize: 20; anchors.bottom: parent.bottom; anchors.bottomMargin: 6 }
                }
                Text { text: "HISTORY SPARKLINE"; color: cyan; font.pixelSize: 8; font.bold: true }
                Sparkline { id: sparkBuf; Layout.fillWidth: true; Layout.preferredHeight: 40; yMin: 0; yMax: 100 }
                Connections { target: guiBridge; function onHistoryUpdated() { sparkBuf.updateData(guiBridge.bufferFillHistory); } }
            }
            
            // Dropped Packets
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text { text: "DROPPED PACKETS"; color: white; font.pixelSize: 14 }
                Text { text: guiBridge.droppedFrames; color: white; font.pixelSize: 42; font.bold: true }
                Text { text: "HISTORY SPARKLINE"; color: cyan; font.pixelSize: 8; font.bold: true }
                Sparkline { id: sparkDrop; Layout.fillWidth: true; Layout.preferredHeight: 40; yMin: 0; yMax: 10 }
                Connections { target: guiBridge; function onHistoryUpdated() { sparkDrop.updateData(guiBridge.droppedHistory); } }
            }
            
            // Real-Time Factor
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text { text: "REAL-TIME FACTOR"; color: white; font.pixelSize: 14 }
                RowLayout {
                    Text { text: guiBridge.realtimeFactor.toFixed(2); color: white; font.pixelSize: 42; font.bold: true }
                    Text { text: "x"; color: white; font.pixelSize: 20; anchors.bottom: parent.bottom; anchors.bottomMargin: 6 }
                }
                Text { text: "HISTORY SPARKLINE"; color: cyan; font.pixelSize: 8; font.bold: true }
                Sparkline { id: sparkRtf; Layout.fillWidth: true; Layout.preferredHeight: 40; yMin: 0; yMax: 2 }
                Connections { target: guiBridge; function onHistoryUpdated() { sparkRtf.updateData(guiBridge.rtfHistory); } }
            }
        }
    }
}
