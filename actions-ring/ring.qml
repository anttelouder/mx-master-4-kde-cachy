// Кольцо действий: прозрачный layer-shell поверх активного экрана, кольцо у курсора.
// Выбор — по углу от центра (мёртвая зона в середине), клик — выполнить или открыть папку.
// Клик в центре / Esc — назад из папки, иначе закрыть; правый клик — закрыть.
// Смена сектора → ring.hover() → вибрация в мыши. Пустые позиции не выбираются.
import QtQuick
import QtQuick.Shapes
import QtQuick.Window
import org.kde.layershell 1.0 as LayerShell
import org.kde.kirigami as Kirigami

Window {
    id: win
    visible: false
    color: "transparent"

    LayerShell.Window.scope: "actions-ring"
    LayerShell.Window.layer: LayerShell.Window.LayerOverlay
    LayerShell.Window.anchors: LayerShell.Window.AnchorTop | LayerShell.Window.AnchorBottom
                               | LayerShell.Window.AnchorLeft | LayerShell.Window.AnchorRight
    LayerShell.Window.exclusionZone: -1
    LayerShell.Window.keyboardInteractivity: LayerShell.Window.KeyboardInteractivityExclusive
    LayerShell.Window.wantsToBeOnActiveScreen: true

    readonly property int count: 8
    readonly property real step: 360 / count
    readonly property real outerR: 150
    readonly property real innerR: 58
    readonly property real iconR: (outerR + innerR) / 2
    readonly property color accent: Kirigami.Theme.highlightColor

    property bool placed: false
    property int selected: -1
    property real cx: 0
    property real cy: 0
    property real lastX: 0
    property real lastY: 0

    // стек открытых папок: [{items, title}]
    property var levels: []
    readonly property var curItems: levels.length ? levels[levels.length - 1].items : ring.items
    readonly property string curTitle: levels.length ? levels[levels.length - 1].title : ring.title

    function open() {
        if (visible) { close(); return }
        placed = false
        selected = -1
        levels = []
        disc.scale = 0.75
        disc.opacity = 0
        visible = true
        requestActivate()
        fallback.restart()
    }

    function close() {
        fallback.stop()
        visible = false
    }

    function place(x, y) {
        if (placed) return
        // не даём кольцу вылезти за край экрана
        cx = Math.min(Math.max(x, outerR + 8), width - outerR - 8)
        cy = Math.min(Math.max(y, outerR + 8), height - outerR - 8)
        placed = true
        fallback.stop()
        appear.restart()
    }

    function track(x, y) {
        lastX = x; lastY = y
        if (!placed) { place(x, y); return }
        const dx = x - cx, dy = y - cy
        let idx = -1
        if (Math.hypot(dx, dy) > innerR * 0.7) {
            const a = (Math.atan2(dx, -dy) * 180 / Math.PI + 360) % 360  // 0° — вверх, по часовой
            idx = Math.round(a / step) % count
            if (!curItems[idx]) idx = -1
        }
        if (idx !== selected) {
            selected = idx
            if (idx >= 0) ring.hover(idx)
        }
    }

    function enter(item) {
        levels = levels.concat([{ items: ring.slotsOf(item.items), title: item.name }])
        afterLevelChange()
    }

    function back() {
        if (!levels.length) { close(); return }
        levels = levels.slice(0, -1)
        afterLevelChange()
    }

    function afterLevelChange() {
        ring.enterFolder()
        selected = -1
        disc.scale = 0.88
        appear.restart()
        track(lastX, lastY)
    }

    function activate() {
        const item = selected >= 0 ? curItems[selected] : null
        if (!item) { back(); return }
        if (item.kind === "folder" || (item.kind === undefined && item.items)) { enter(item); return }
        close()
        ring.run(item)
    }

    Connections {
        target: ring
        function onShowRequested() { win.open() }
        function onHideRequested() { win.close() }
    }

    // Если wl_pointer.enter не пришёл (курсор на другом экране), ставим по центру.
    Timer {
        id: fallback
        interval: 250
        onTriggered: win.place(win.width / 2, win.height / 2)
    }

    ParallelAnimation {
        id: appear
        NumberAnimation { target: disc; property: "scale"; to: 1; duration: 180; easing.type: Easing.OutBack; easing.overshoot: 1.6 }
        NumberAnimation { target: disc; property: "opacity"; to: 1; duration: 120 }
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onEntered: { win.lastX = mouseX; win.lastY = mouseY; win.place(mouseX, mouseY) }
        onPositionChanged: mouse => win.track(mouse.x, mouse.y)
        onClicked: mouse => {
            if (mouse.button === Qt.RightButton) win.close()
            else win.activate()
        }
    }

    Item {
        focus: true
        Keys.onEscapePressed: win.back()
    }

    Item {
        id: disc
        width: win.outerR * 2
        height: width
        x: win.cx - width / 2
        y: win.cy - height / 2
        visible: win.placed

        // фон кольца
        Rectangle {
            anchors.fill: parent
            radius: width / 2
            color: Qt.rgba(0.11, 0.11, 0.13, 0.93)
            border.color: Qt.rgba(1, 1, 1, 0.08)
            border.width: 1
        }

        // подсветка сектора — плавно доезжает до выбранного
        Shape {
            id: wedge
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            opacity: win.selected >= 0 ? 1 : 0
            rotation: Math.max(win.selected, 0) * win.step
            Behavior on opacity { NumberAnimation { duration: 90 } }
            Behavior on rotation { RotationAnimation { duration: 110; direction: RotationAnimation.Shortest; easing.type: Easing.OutCubic } }
            ShapePath {
                fillColor: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.55)
                strokeColor: "transparent"
                PathAngleArc {
                    centerX: win.outerR; centerY: win.outerR
                    radiusX: win.outerR - 4; radiusY: win.outerR - 4
                    startAngle: -90 - win.step / 2; sweepAngle: win.step
                }
                PathAngleArc {
                    centerX: win.outerR; centerY: win.outerR
                    radiusX: win.innerR + 4; radiusY: win.innerR + 4
                    moveToStart: false  // продолжить контур внешней дуги, иначе вместо клина два сегмента
                    startAngle: -90 + win.step / 2; sweepAngle: -win.step
                }
            }
        }

        // иконки; у папки — точка-метка
        Repeater {
            model: win.curItems
            delegate: Kirigami.Icon {
                required property var modelData
                required property int index
                readonly property real a: (index * win.step - 90) * Math.PI / 180
                visible: !!modelData
                width: 44; height: 44
                x: win.outerR + win.iconR * Math.cos(a) - width / 2
                y: win.outerR + win.iconR * Math.sin(a) - height / 2
                source: modelData && modelData.icon ? modelData.icon
                        : (modelData && modelData.kind === "folder" ? "folder" : "application-x-executable")
                scale: index === win.selected ? 1.25 : 1
                Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutBack } }
                Rectangle {
                    visible: !!modelData && (modelData.kind === "folder" || (modelData.kind === undefined && !!modelData.items))
                    width: 9; height: 9; radius: 4.5
                    anchors.right: parent.right; anchors.bottom: parent.bottom
                    color: win.accent
                    border.color: Qt.rgba(0.11, 0.11, 0.13, 1); border.width: 2
                }
            }
        }

        // центр: название выбранного действия, иначе — имя папки / кольца приложения
        Rectangle {
            anchors.centerIn: parent
            width: win.innerR * 2; height: width
            radius: width / 2
            color: Qt.rgba(0.07, 0.07, 0.08, 0.92)
            Kirigami.Icon {
                visible: win.selected < 0 && win.levels.length > 0
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top; anchors.topMargin: 14
                width: 16; height: 16
                source: "go-previous"
                opacity: 0.6
            }
            Text {
                anchors.centerIn: parent
                width: parent.width - 12
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
                maximumLineCount: 3
                elide: Text.ElideRight
                color: "white"
                opacity: win.selected >= 0 ? 1 : 0.55
                font.pixelSize: 13
                font.weight: Font.Medium
                text: win.selected >= 0 ? win.curItems[win.selected].name : win.curTitle
            }
        }
    }
}
