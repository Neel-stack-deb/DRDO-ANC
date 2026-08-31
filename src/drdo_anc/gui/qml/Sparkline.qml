import QtQuick

Item {
    id: root
    
    property color lineColor: "#00E5FF"
    property int lineWidth: 1
    property var historyData: []
    
    // Configurable scaling
    property real yMin: 0
    property real yMax: 100
    
    function updateData(newData) {
        historyData = newData
        canvas.requestPaint()
    }
    
    Canvas {
        id: canvas
        anchors.fill: parent
        antialiasing: true
        
        onPaint: {
            var ctx = getContext("2d");
            ctx.clearRect(0, 0, width, height);
            
            if (!historyData || historyData.length === 0) return;
            
            var w = width;
            var h = height;
            var points = historyData.length;
            var step = w / (points - 1);
            
            // Draw faint grid
            ctx.lineWidth = 1;
            ctx.strokeStyle = "#1AFFFFFF"; // faint white
            ctx.beginPath();
            ctx.moveTo(0, h/2); ctx.lineTo(w, h/2);
            for(var g=1; g<10; g++){ ctx.moveTo(w*(g/10), 0); ctx.lineTo(w*(g/10), h); }
            ctx.stroke();
            
            // Sparkline Line
            ctx.beginPath();
            
            // Map function
            var mapY = function(val) {
                var norm = (val - root.yMin) / (root.yMax - root.yMin);
                norm = Math.max(0, Math.min(1, norm));
                return h - (norm * h);
            };
            
            ctx.moveTo(0, mapY(historyData[0]));
            for (var j = 1; j < points; j++) {
                ctx.lineTo(j * step, mapY(historyData[j]));
            }
            
            ctx.lineWidth = root.lineWidth + 1;
            ctx.strokeStyle = root.lineColor;
            ctx.lineJoin = "round";
            ctx.stroke();
            
            // Fill under sparkline
            ctx.lineTo(w, h);
            ctx.lineTo(0, h);
            ctx.closePath();
            
            ctx.globalAlpha = 0.2;
            ctx.fillStyle = root.lineColor;
            ctx.fill();
            ctx.globalAlpha = 1.0;
        }
    }
}
