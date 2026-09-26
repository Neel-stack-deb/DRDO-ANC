import QtQuick

Item {
    id: root

    property color lineColor: "#00E5FF"
    property int lineWidth: 2
    property var waveformData: []

    function updateData(newData) {
        waveformData = newData
        canvas.requestPaint()
    }

    Canvas {
        id: canvas
        anchors.fill: parent
        anchors.margins: 8
        antialiasing: true

        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()

        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)

            if (!waveformData || waveformData.length < 2) {
                return
            }

            var w = width
            var h = height
            var halfH = h * 0.45
            var midY = h / 2
            var points = waveformData.length
            var step = w / (points - 1)

            var peak = 0.0001
            for (var i = 0; i < points; i++) {
                var a = Math.abs(waveformData[i])
                if (a > peak) {
                    peak = a
                }
            }
            var gain = 0.92 / peak

            ctx.lineWidth = 1
            ctx.strokeStyle = "#222222"
            for (var gy = 1; gy < 10; gy++) {
                ctx.beginPath()
                ctx.moveTo(0, h * (gy / 10))
                ctx.lineTo(w, h * (gy / 10))
                ctx.stroke()
            }

            ctx.strokeStyle = "#333333"
            ctx.beginPath()
            ctx.moveTo(0, midY)
            ctx.lineTo(w, midY)
            ctx.stroke()

            ctx.beginPath()
            ctx.moveTo(0, midY - (waveformData[0] * gain * halfH))

            for (var j = 1; j < points; j++) {
                var x = j * step
                var y = midY - (waveformData[j] * gain * halfH)
                ctx.lineTo(x, y)
            }

            ctx.lineJoin = "round"
            ctx.lineWidth = root.lineWidth
            ctx.strokeStyle = root.lineColor
            ctx.shadowColor = root.lineColor
            ctx.shadowBlur = 6
            ctx.stroke()
            ctx.shadowBlur = 0

            ctx.lineTo(w, midY)
            ctx.lineTo(0, midY)
            ctx.closePath()
            ctx.globalAlpha = 0.12
            ctx.fillStyle = root.lineColor
            ctx.fill()
            ctx.globalAlpha = 1.0
        }
    }
}
