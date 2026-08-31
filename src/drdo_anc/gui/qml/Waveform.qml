import QtQuick

Item {
    id: root
    
    property color lineColor: "#00E5FF"
    property int lineWidth: 1
    property var waveformData: []
    
    function updateData(newData) {
        waveformData = newData
        canvas.requestPaint()
    }
    
    // Axis labels
    Text { text: "AMPLITUDE"; color: "#555555"; font.pixelSize: 9; rotation: -90; anchors.left: parent.left; anchors.leftMargin: -20; anchors.verticalCenter: parent.verticalCenter }
    Text { text: "TIME (ms)"; color: "#555555"; font.pixelSize: 9; anchors.bottom: parent.bottom; anchors.bottomMargin: -16; anchors.horizontalCenter: parent.horizontalCenter }
    
    Canvas {
        id: canvas
        anchors.fill: parent
        anchors.margins: 10
        antialiasing: true
        
        onPaint: {
            var ctx = getContext("2d");
            ctx.clearRect(0, 0, width, height);
            
            if (!waveformData || waveformData.length === 0) return;
            
            var w = width;
            var h = height;
            var halfH = h / 2;
            var points = waveformData.length;
            var step = w / (points - 1);
            
            // Complex Telemetry Grid
            ctx.lineWidth = 1;
            ctx.strokeStyle = "#222222";
            
            for(var gy=0; gy<=10; gy++) {
                ctx.beginPath(); ctx.moveTo(0, h*(gy/10)); ctx.lineTo(w, h*(gy/10)); ctx.stroke();
            }
            for(var gx=0; gx<=20; gx++) {
                ctx.beginPath(); ctx.moveTo(w*(gx/20), 0); ctx.lineTo(w*(gx/20), h); ctx.stroke();
            }
            
            ctx.strokeStyle = "#444444";
            ctx.beginPath(); ctx.moveTo(0, halfH); ctx.lineTo(w, halfH); ctx.stroke();
            
            // Draw Waveform
            ctx.beginPath();
            ctx.moveTo(0, halfH - (waveformData[0] * halfH));
            
            for (var j = 1; j < points; j++) {
                var x = j * step;
                var val = waveformData[j];
                var y = halfH - (val * halfH); 
                ctx.lineTo(x, y);
            }
            
            ctx.lineJoin = "round";
            ctx.lineWidth = root.lineWidth + 1;
            ctx.strokeStyle = root.lineColor;
            
            // Subtle glow
            ctx.shadowColor = root.lineColor;
            ctx.shadowBlur = 8;
            ctx.stroke();
            
            ctx.shadowBlur = 0; // reset
            
            // Fill under waveform
            ctx.lineTo(w, halfH);
            ctx.lineTo(0, halfH);
            ctx.closePath();
            
            ctx.globalAlpha = 0.15;
            ctx.fillStyle = root.lineColor;
            ctx.fill();
            ctx.globalAlpha = 1.0;
        }
    }
}
