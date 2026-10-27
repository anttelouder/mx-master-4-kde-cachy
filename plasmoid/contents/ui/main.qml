// MX Master 4 widget for the KDE Plasma 6 panel.
// All the logic lives in ~/.local/bin/mousectl (mousectl.py in the repo root): the widget calls
// it through the executable engine and parses JSON. A new feature = a new mousectl command
// + an element here; the "Buttons" tab so far only shows the xremap config (room for an editor).
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PC3
import org.kde.plasma.extras as PlasmaExtras
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    readonly property string mousectl: "~/.local/bin/mousectl"
    property var st: ({})
    // "Buttons" tab: app profiles × buttons (model — buttons.py, via mousectl bindings)
    property var bindData: ({})       // bindings get reply: buttons, catalog, profiles
    property var bindProfiles: []     // editable copy of the profiles; the last one is "All applications"
    property int bindRev: 0
    property int bindProfile: -1      // index in bindProfiles; -1 — not loaded yet
    property string bindKey: ""       // selected key-slot (F13, KEY_FN_F4, WHEEL…)
    property string bindStatus: ""    // "Saving…", "Saved", an error
    property string lastError: ""

    readonly property var mouse: st.mouse || ({})
    readonly property var services: st.services || ({})
    readonly property bool online: mouse.online === true
    readonly property bool logidLost: services.logid !== undefined
                                      && (!services.logid.active || services.logid.sees_mouse === false)
    readonly property bool problem: st.mouse !== undefined && (!online || logidLost)

    Plasmoid.icon: "input-mouse"
    Plasmoid.status: problem ? PlasmaCore.Types.NeedsAttentionStatus : PlasmaCore.Types.ActiveStatus
    toolTipMainText: "MX Master 4"
    toolTipSubText: !online ? "The mouse is not responding (asleep or switched off)"
                    : (logidLost ? "logid cannot see the mouse — switch it off and on\n" : "")
                      + "Battery " + mouse.battery + "%" + (mouse.charging ? ", charging" : "")
                      + " · " + mouse.dpi + " DPI"

    // --- running mousectl ---
    property int seq: 0
    property var callbacks: ({})

    P5Support.DataSource {
        id: exec
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            const cb = root.callbacks[source]
            delete root.callbacks[source]
            disconnectSource(source)
            let parsed = null
            try { parsed = JSON.parse(data.stdout) } catch (e) { parsed = null }
            if (parsed === null)
                root.lastError = (data.stderr || data.stdout || "mousectl did not respond").trim()
            else if (parsed.ok === false && parsed.error)
                root.lastError = parsed.error
            else
                root.lastError = ""
            if (cb) cb(parsed)
        }
    }

    function run(args, cb) {
        // unique trailing comment: identical commands in a row are not merged by the engine
        const cmd = mousectl + " " + args + " #" + (++seq)
        callbacks[cmd] = cb
        exec.connectSource(cmd)
    }

    function refresh() {
        run("status --enforce", r => { if (r) root.st = r })
    }
    function setValue(key, value) {
        run("set " + key + " " + value, r => refresh())
    }
    function service(name, on) {
        run("service " + name + " " + (on ? "start" : "stop"), r => refresh())
    }
    function loadBindings() {
        if (bindSave.running) return   // do not overwrite an edit that has not been saved yet
        run("bindings get", r => {
            if (!r || !r.profiles) return
            root.bindData = r
            root.bindProfiles = r.profiles
            if (root.bindProfile < 0 || root.bindProfile >= r.profiles.length)
                root.bindProfile = r.profiles.length - 1
            root.bindRev++
        })
    }
    function bindChanged() {
        bindRev++
        bindStatus = "Saving…"
        bindSave.restart()
    }
    function setSlot(key, action) {
        bindProfiles[bindProfile].keys[key] = action
        bindKey = ""
        bindChanged()
    }
    function addProfile(app) {
        const keys = {}
        for (const b of bindData.buttons) for (const s of b.slots) keys[s.key] = { kind: "default" }
        // a new profile goes first: it has the highest priority
        bindProfiles.unshift({ name: app.name, icon: app.icon, app: app.id, apps: [], keys: keys, extra: {} })
        bindProfile = 0
        bindKey = ""
        bindChanged()
    }
    function removeProfile() {
        bindProfiles.splice(bindProfile, 1)
        bindProfile = bindProfiles.length - 1
        bindKey = ""
        bindChanged()
    }
    function resetDefaults() {
        bindStatus = "Saving…"
        run("bindings reset", r => {
            root.bindStatus = r && r.ok ? "Default layout restored" : "Not saved"
            root.loadBindings()
        })
    }
    // "C-Shift-t" → "Ctrl+Shift+T"
    function humanKeys(k) {
        const mods = { "C": "Ctrl", "Ctrl": "Ctrl", "M": "Alt", "Alt": "Alt", "Shift": "Shift", "Super": "Meta", "Win": "Meta" }
        const names = { pageup: "PgUp", pagedown: "PgDn", left: "←", right: "→", up: "↑", down: "↓", tab: "Tab",
                        esc: "Esc", enter: "Enter", space: "Space", backspace: "Backspace", delete: "Del",
                        home: "Home", end: "End", minus: "-", equal: "=", comma: ",", dot: ".", slash: "/" }
        const parts = String(k).split("-")
        const key = parts.pop()
        const human = parts.map(m => mods[m] || m)
        const n = names[key.toLowerCase()] || (key.length === 1 ? key.toUpperCase() : key.replace(/^KEY_/, ""))
        return human.concat([n]).join("+")
    }

    readonly property var bindCatalog: {
        const m = {}
        for (const c of (bindData.catalog || [])) m[c.id] = c
        return m
    }
    function actionText(a, profile) {
        if (!a) return ""
        switch (a.kind) {
        case "default": return "inherited"
        case "nothing": return "—"
        case "preset": return bindCatalog[a.id] ? bindCatalog[a.id].name : a.id
        case "keys": return humanKeys(a.keys)
        case "app": {
            const x = (ringData.apps || []).find(p => p.id === a.app)
            return x ? x.name : a.app
        }
        case "kde": {
            const x = (ringData.shortcuts || []).find(s => s.component === a.component && s.name === a.name)
            return x ? x.friendly : a.name
        }
        case "scroll": return "side scroll"
        case "tabs": return "tabs"
        }
        return a.label || "custom"
    }
    function actionIcon(a) {
        if (!a) return ""
        switch (a.kind) {
        case "preset": return bindCatalog[a.id] ? bindCatalog[a.id].icon : ""
        case "keys": return "input-keyboard"
        case "app": {
            const x = (ringData.apps || []).find(p => p.id === a.app)
            return x ? x.icon : "system-run"
        }
        case "kde": return "preferences-desktop-keyboard-shortcut"
        case "tabs": return "tab-duplicate"
        case "scroll": return "transform-move-horizontal"
        }
        return ""
    }

    Timer {
        id: bindSave
        interval: 700
        onTriggered: root.run("bindings set " + root.encodeArg(JSON.stringify(root.bindProfiles)), r => {
            root.bindStatus = r && r.ok ? "Saved" : "Not saved" + (r && r.error ? ": " + r.error : "")
        })
    }
    // percent-encoding without characters that are significant to the shell
    function encodeArg(text) {
        return encodeURIComponent(text).replace(/[!'()*~]/g, c => "%" + c.charCodeAt(0).toString(16).toUpperCase())
    }
    // evdev code → xremap key name (for recording a combo); modifiers are null
    readonly property var evdevNames: {
        const t = { 1: "esc", 12: "minus", 13: "equal", 14: "backspace", 15: "tab", 26: "leftbrace",
                    27: "rightbrace", 28: "enter", 39: "semicolon", 40: "apostrophe", 41: "grave",
                    43: "backslash", 51: "comma", 52: "dot", 53: "slash", 57: "space", 87: "F11", 88: "F12",
                    99: "sysrq", 102: "home", 103: "up", 104: "pageup", 105: "left", 106: "right", 107: "end",
                    108: "down", 109: "pagedown", 110: "insert", 111: "delete" }
        "1234567890".split("").forEach((c, i) => t[2 + i] = c)
        "qwertyuiop".split("").forEach((c, i) => t[16 + i] = c)
        "asdfghjkl".split("").forEach((c, i) => t[30 + i] = c)
        "zxcvbnm".split("").forEach((c, i) => t[44 + i] = c)
        for (let i = 0; i < 10; i++) t[59 + i] = "F" + (i + 1)
        return t
    }

    // --- actions ring ("Ring" tab) ---
    // ringCfg is edited in place; ringRev is a change counter that all bindings depend on.
    property var ringData: ({})
    property var ringCfg: null
    property int ringRev: 0
    property var ringPath: []         // folder indices from the ring root
    property int ringSlot: -1

    function loadRing() {
        run("ring get", r => {
            if (!r || !r.config) return
            root.ringData = r
            const c = r.config
            if (!c.items) c.items = []
            if (!c.apps) c.apps = []
            root.ringCfg = c
            root.ringPath = []
            root.ringSlot = -1
            root.ringRev++
        })
    }
    function ringNode() {
        let node = ringCfg
        for (const i of ringPath) node = node.items[i]
        return node
    }
    function ringList() {
        const node = ringNode()
        if (!node.items) node.items = []
        while (node.items.length < 8) node.items.push(null)
        return node.items
    }
    function ringChanged() {
        ringRev++
        ringSave.restart()
    }
    function editSlot(fn) {
        const l = ringList()
        const it = l[ringSlot] || {}
        fn(it)
        l[ringSlot] = it
        ringChanged()
    }
    function setSlotKind(kind) {
        const l = ringList()
        const old = l[ringSlot] || {}
        const name = old.name || ""
        if (kind === "") l[ringSlot] = null
        else if (kind === "app") l[ringSlot] = { kind: "app", name: name, icon: "", app: "" }
        else if (kind === "kde") l[ringSlot] = { kind: "kde", name: name, icon: "", shortcut: null }
        else if (kind === "cmd") l[ringSlot] = { kind: "cmd", name: name, icon: "", cmd: "" }
        else l[ringSlot] = { kind: "folder", name: name || "Folder", icon: "folder", items: [] }
        ringChanged()
    }
    function moveSlot(delta) {
        const l = ringList()
        const to = (ringSlot + delta + 8) % 8
        const t = l[to]; l[to] = l[ringSlot]; l[ringSlot] = t
        ringSlot = to
        ringChanged()
    }
    function pickApp(a) {
        const l = ringList()
        l[ringSlot] = { kind: "app", name: a.name, icon: a.icon, app: a.id }
        ringChanged()
    }
    function openFolder(index) {
        ringPath = ringPath.concat([index])
        ringSlot = -1
        ringRev++
    }
    function closeFolder() {
        ringSlot = ringPath[ringPath.length - 1]
        ringPath = ringPath.slice(0, -1)
        ringRev++
    }

    Timer {
        id: ringSave
        interval: 500
        onTriggered: {
            root.run("ring set " + root.encodeArg(JSON.stringify(root.ringCfg)), r => {})
        }
    }

    Timer {
        interval: 30000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.refresh()
    }
    onExpandedChanged: if (expanded) { refresh(); loadBindings(); if (!ringSave.running) loadRing() }

    // --- panel icon ---
    compactRepresentation: MouseArea {
        onClicked: root.expanded = !root.expanded
        hoverEnabled: true
        Kirigami.Icon {
            anchors.fill: parent
            source: "input-mouse"
            active: parent.containsMouse
        }
        Rectangle {  // red dot if something is wrong
            visible: root.problem
            width: parent.width / 3; height: width; radius: width / 2
            anchors.right: parent.right; anchors.top: parent.top
            color: Kirigami.Theme.negativeTextColor
        }
        PC3.Label {
            visible: root.online && root.mouse.battery !== undefined && root.mouse.battery <= 20
            text: root.mouse.battery + "%"
            font.pixelSize: parent.height / 3
            anchors.bottom: parent.bottom; anchors.horizontalCenter: parent.horizontalCenter
            color: Kirigami.Theme.negativeTextColor
        }
    }

    // --- expanded window ---
    fullRepresentation: PlasmaExtras.Representation {
        Layout.preferredWidth: Kirigami.Units.gridUnit * 24
        Layout.preferredHeight: Kirigami.Units.gridUnit * 34
        collapseMarginsHint: true

        header: PlasmaExtras.PlasmoidHeading {
            RowLayout {
                anchors.fill: parent
                Kirigami.Heading { level: 3; text: "MX Master 4"; Layout.fillWidth: true }
                PC3.Label {
                    text: !root.online ? "not responding"
                          : root.mouse.battery + "%" + (root.mouse.charging ? " ⚡" : "")
                    color: !root.online || root.mouse.battery <= 20
                           ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.textColor
                }
                PC3.ToolButton {
                    icon.name: "view-refresh"
                    onClicked: { root.refresh(); root.loadBindings() }
                    PC3.ToolTip.text: "Refresh"
                    PC3.ToolTip.visible: hovered
                }
            }
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: Kirigami.Units.smallSpacing

            PC3.TabBar {
                id: tabs
                Layout.fillWidth: true
                PC3.TabButton { text: "Settings" }
                PC3.TabButton { text: "Ring" }
                PC3.TabButton { text: "Buttons" }
            }

            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: root.problem || root.lastError !== ""
                type: root.lastError !== "" ? Kirigami.MessageType.Error : Kirigami.MessageType.Warning
                text: root.lastError !== "" ? root.lastError
                      : !root.online ? "The mouse is not responding: it is asleep or switched off. Move it."
                      : "logid cannot see the mouse, buttons and gestures will not work. Switch the mouse off and on with the switch on its underside."
            }

            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: tabs.currentIndex

                // ===== Settings =====
                PC3.ScrollView {
                    contentWidth: availableWidth
                    ColumnLayout {
                        width: parent.width
                        spacing: Kirigami.Units.smallSpacing

                        Kirigami.Heading { level: 5; text: "Services"; opacity: 0.7 }
                        RowLayout {
                            PC3.Label { text: "logid (buttons and gestures)"; Layout.fillWidth: true }
                            PC3.Label {
                                text: root.services.logid === undefined ? "…"
                                      : !root.services.logid.active ? "not running"
                                      : root.services.logid.sees_mouse ? "sees the mouse" : "mouse not found"
                                color: root.logidLost ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.positiveTextColor
                            }
                        }
                        PC3.Switch {
                            Layout.fillWidth: true
                            text: "Per-app bindings (xremap)"
                            checked: root.services.xremap !== undefined && root.services.xremap.active
                            onToggled: root.service("xremap", checked)
                        }
                        PC3.Switch {
                            visible: root.services.meetings !== undefined && root.services.meetings.installed === true
                            Layout.fillWidth: true
                            text: "Meeting haptic reminders"
                            checked: root.services.meetings !== undefined && root.services.meetings.active
                            onToggled: root.service("meetings", checked)
                        }

                        Kirigami.Heading { level: 5; text: "Mouse"; opacity: 0.7; Layout.topMargin: Kirigami.Units.smallSpacing }
                        SettingSlider { key: "dpi"; label: "Sensitivity"; suffix: " DPI"; from: 200; to: 8000; step: 50 }
                        SettingSlider { key: "haptic"; label: "Haptic strength"; suffix: "%"; from: 0; to: 100; step: 5 }
                        SettingSlider { key: "threshold"; label: "SmartShift threshold"; from: 1; to: 50; step: 1
                                        hint: "the higher the value, the faster you must spin for free spin; 50 — always ratchet" }
                        SettingSlider { key: "torque"; label: "Ratchet torque"; suffix: "%"; from: 1; to: 100; step: 1 }
                        PC3.Switch {
                            Layout.fillWidth: true
                            enabled: root.online
                            text: "Wheel: free spin"
                            checked: root.mouse.freespin === true
                            onToggled: root.setValue("freespin", checked ? 1 : 0)
                        }

                        Kirigami.Heading { level: 5; text: "Haptics"; opacity: 0.7; Layout.topMargin: Kirigami.Units.smallSpacing }
                        RowLayout {
                            Layout.fillWidth: true
                            PC3.ComboBox {
                                id: wave
                                Layout.fillWidth: true
                                model: root.st.waveforms || ["COMPLETED"]
                            }
                            PC3.Button {
                                text: "Test"
                                icon.name: "media-playback-start"
                                enabled: root.online
                                onClicked: root.run("buzz " + wave.currentText, r => {})
                            }
                        }
                    }
                }

                // ===== Actions ring =====
                RingPage {}

                // ===== Buttons: what each button does, per app =====
                ButtonsPage {}
            }
        }
    }

    // "Ring" tab: a scheme of 8 slots, click a slot to pick what it launches.
    // Edits are written straight to ~/.config/actions-ring/ring.json (mousectl ring set),
    // the ring re-reads the file every time it opens.
    component RingPage: PC3.ScrollView {
        id: rp
        contentWidth: availableWidth

        readonly property var places: ["top", "top right", "right", "bottom right",
                                       "bottom", "bottom left", "left", "top left"]
        readonly property var kinds: [
            { key: "app", label: "Application" },
            { key: "folder", label: "Folder (8 more slots)" },
            { key: "cmd", label: "Command" },
            { key: "kde", label: "KDE action" }
        ]
        readonly property var items: { root.ringRev; return root.ringCfg ? root.ringList() : [] }
        readonly property var cur: root.ringSlot >= 0 && items.length ? items[root.ringSlot] : null
        readonly property string kind: cur ? (cur.kind || (cur.items ? "folder" : "cmd")) : ""
        property string mode: ""            // the type picked in the list while the slot is not filled with it yet
        readonly property string shown: mode !== "" ? mode : (kind || "app")
        readonly property string folderTitle: {
            root.ringRev
            let node = root.ringCfg, names = []
            for (const i of root.ringPath) { node = node.items[i]; names.push(node.name) }
            return names.join(" › ")
        }

        Connections {
            target: root
            function onRingSlotChanged() { rp.mode = ""; appFilter.text = ""; kdeFilter.text = "" }
        }
        Timer {
            id: showRing
            interval: 300
            onTriggered: root.run("ring show", r => {})
        }

        ColumnLayout {
            width: parent.width
            spacing: Kirigami.Units.smallSpacing

            RowLayout {
                Layout.fillWidth: true
                PC3.Switch {
                    Layout.fillWidth: true
                    text: "Ring on the haptic panel"
                    checked: root.services.ring !== undefined && root.services.ring.active
                    onToggled: root.service("ring", checked)
                }
                PC3.Button {
                    text: "Show"
                    icon.name: "view-visible"
                    onClicked: { root.expanded = false; showRing.restart() }
                }
            }

            RowLayout {
                visible: root.ringPath.length > 0
                Layout.fillWidth: true
                PC3.ToolButton {
                    text: "Back"
                    icon.name: "go-previous"
                    onClicked: root.closeFolder()
                }
                PC3.Label {
                    Layout.fillWidth: true
                    text: "Folder: " + rp.folderTitle
                    elide: Text.ElideRight
                    font.bold: true
                }
            }

            // ring scheme
            Item {
                id: scheme
                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.gridUnit * 13
                readonly property real r: Math.min(width, height) / 2 - 32

                Rectangle {
                    anchors.centerIn: parent
                    width: (scheme.r + 32) * 2; height: width
                    radius: width / 2
                    color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g,
                                   Kirigami.Theme.textColor.b, 0.06)
                }
                PC3.Label {
                    anchors.centerIn: parent
                    width: scheme.r * 1.1
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.Wrap
                    opacity: 0.6
                    text: root.ringSlot >= 0 && rp.cur ? rp.cur.name
                          : "Pick a slot\nto assign\nan app"
                }
                Repeater {
                    model: 8
                    delegate: PC3.ToolButton {
                        required property int index
                        readonly property var it: rp.items[index] || null
                        readonly property real a: (index * 45 - 90) * Math.PI / 180
                        readonly property bool isFolder: !!it && (it.kind === "folder" || (it.kind === undefined && !!it.items))
                        width: 54; height: 54
                        x: scheme.width / 2 + scheme.r * Math.cos(a) - width / 2
                        y: scheme.height / 2 + scheme.r * Math.sin(a) - height / 2
                        checkable: true
                        checked: root.ringSlot === index
                        icon.name: it ? (it.icon || (isFolder ? "folder" : "application-x-executable")) : "list-add"
                        icon.width: 36; icon.height: 36
                        opacity: it || checked ? 1 : 0.45
                        onClicked: root.ringSlot = index
                        onDoubleClicked: if (isFolder) root.openFolder(index)
                        PC3.ToolTip.text: (it ? it.name : "Empty") + (isFolder ? " — double-click to open" : "")
                        PC3.ToolTip.visible: hovered
                        Rectangle {  // folder marker
                            visible: parent.isFolder
                            width: 10; height: 10; radius: 5
                            anchors.right: parent.right; anchors.bottom: parent.bottom
                            anchors.margins: 6
                            color: Kirigami.Theme.highlightColor
                        }
                    }
                }
            }

            // ===== what is on the selected slot =====
            ColumnLayout {
                visible: root.ringSlot >= 0
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing

                RowLayout {
                    Layout.fillWidth: true
                    Kirigami.Heading {
                        level: 5
                        Layout.fillWidth: true
                        text: "Slot " + (root.ringSlot >= 0 ? rp.places[root.ringSlot] : "")
                    }
                    PC3.ToolButton {
                        icon.name: "object-rotate-left"
                        onClicked: root.moveSlot(-1)
                        PC3.ToolTip.text: "Move counter-clockwise"
                        PC3.ToolTip.visible: hovered
                    }
                    PC3.ToolButton {
                        icon.name: "object-rotate-right"
                        onClicked: root.moveSlot(1)
                        PC3.ToolTip.text: "Move clockwise"
                        PC3.ToolTip.visible: hovered
                    }
                    PC3.ToolButton {
                        icon.name: "edit-clear"
                        enabled: !!rp.cur
                        onClicked: root.setSlotKind("")
                        PC3.ToolTip.text: "Clear slot"
                        PC3.ToolTip.visible: hovered
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    PC3.Label { text: "Launch:" }
                    PC3.ComboBox {
                        Layout.fillWidth: true
                        model: rp.kinds
                        textRole: "label"
                        currentIndex: Math.max(0, rp.kinds.findIndex(k => k.key === rp.shown))
                        onActivated: index => {
                            const k = rp.kinds[index].key
                            if (k === rp.kind) { rp.mode = ""; return }
                            if (k === "app" || k === "kde") rp.mode = k   // the slot will be filled by picking from the list
                            else { rp.mode = ""; root.setSlotKind(k) }
                        }
                    }
                }

                RowLayout {
                    visible: !!rp.cur
                    Layout.fillWidth: true
                    PC3.Label { text: "Name:" }
                    PC3.TextField {
                        Layout.fillWidth: true
                        text: rp.cur ? (rp.cur.name || "") : ""
                        onTextEdited: root.editSlot(it => it.name = text)
                    }
                }
                RowLayout {
                    visible: !!rp.cur && rp.shown !== "app"
                    Layout.fillWidth: true
                    PC3.Label { text: "Icon:" }
                    PC3.TextField {
                        Layout.fillWidth: true
                        placeholderText: "theme name, e.g. folder"
                        text: rp.cur ? (rp.cur.icon || "") : ""
                        onTextEdited: root.editSlot(it => it.icon = text)
                    }
                    Kirigami.Icon {
                        implicitWidth: Kirigami.Units.iconSizes.medium
                        implicitHeight: implicitWidth
                        source: rp.cur && rp.cur.icon ? rp.cur.icon : "image-missing"
                    }
                }

                // app — list of installed ones
                PC3.TextField {
                    id: appFilter
                    visible: rp.shown === "app"
                    Layout.fillWidth: true
                    placeholderText: "Search for an app…"
                    clearButtonShown: true
                }
                ListView {
                    visible: rp.shown === "app"
                    Layout.fillWidth: true
                    Layout.preferredHeight: Kirigami.Units.gridUnit * 11
                    clip: true
                    model: {
                        const q = appFilter.text.toLowerCase()
                        return (root.ringData.apps || []).filter(a => !q || a.name.toLowerCase().includes(q)
                                                                 || a.id.toLowerCase().includes(q))
                    }
                    delegate: PC3.ItemDelegate {
                        required property var modelData
                        width: ListView.view.width
                        text: modelData.name
                        icon.name: modelData.icon
                        highlighted: !!rp.cur && rp.cur.app === modelData.id
                        onClicked: { root.pickApp(modelData); rp.mode = "" }
                    }
                }

                // folder
                PC3.Button {
                    visible: rp.shown === "folder" && !!rp.cur
                    Layout.fillWidth: true
                    text: "Open the folder and arrange apps"
                    icon.name: "folder-open"
                    onClicked: root.openFolder(root.ringSlot)
                }

                // command
                PC3.TextField {
                    visible: rp.shown === "cmd" && !!rp.cur
                    Layout.fillWidth: true
                    placeholderText: "command, e.g. spectacle --region"
                    font.family: "monospace"
                    text: rp.cur ? (rp.cur.cmd || "") : ""
                    onTextEdited: root.editSlot(it => it.cmd = text)
                }

                // KDE action — kglobalaccel global actions
                PC3.TextField {
                    id: kdeFilter
                    visible: rp.shown === "kde"
                    Layout.fillWidth: true
                    placeholderText: "Search for an action…"
                    clearButtonShown: true
                }
                ListView {
                    visible: rp.shown === "kde"
                    Layout.fillWidth: true
                    Layout.preferredHeight: Kirigami.Units.gridUnit * 11
                    clip: true
                    model: {
                        const q = kdeFilter.text.toLowerCase()
                        return (root.ringData.shortcuts || []).filter(s => !q || s.friendly.toLowerCase().includes(q))
                    }
                    delegate: PC3.ItemDelegate {
                        required property var modelData
                        width: ListView.view.width
                        text: modelData.friendly + "  ·  " + modelData.componentName
                        highlighted: !!rp.cur && !!rp.cur.shortcut && rp.cur.shortcut.name === modelData.name
                                     && rp.cur.shortcut.component === modelData.component
                        onClicked: {
                            const s = modelData
                            const l = root.ringList()
                            const old = l[root.ringSlot] || {}
                            l[root.ringSlot] = { kind: "kde", name: old.kind === "kde" && old.name ? old.name : s.friendly,
                                                 icon: old.icon || "preferences-desktop-keyboard-shortcut",
                                                 shortcut: { component: s.component, name: s.name } }
                            rp.mode = ""
                            root.ringChanged()
                        }
                    }
                }
            }

            // ===== haptics =====
            Kirigami.Heading { level: 5; text: "Ring haptics"; opacity: 0.7; Layout.topMargin: Kirigami.Units.smallSpacing }
            Repeater {
                model: [
                    { key: "hover_haptic", label: "Hovering a slot", def: "SUBTLE_COLLISION" },
                    { key: "activate_haptic", label: "Launch", def: "DAMP_STATE_CHANGE" },
                    { key: "folder_haptic", label: "Entering a folder", def: "SHARP_STATE_CHANGE" }
                ]
                delegate: RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    PC3.Label { text: modelData.label; Layout.preferredWidth: Kirigami.Units.gridUnit * 8 }
                    PC3.ComboBox {
                        id: hc
                        Layout.fillWidth: true
                        model: root.ringData.waveforms || []
                        currentIndex: {
                            root.ringRev
                            const v = root.ringCfg && root.ringCfg[modelData.key] ? root.ringCfg[modelData.key] : modelData.def
                            return Math.max(0, model.indexOf(v))
                        }
                        onActivated: index => { root.ringCfg[modelData.key] = model[index]; root.ringChanged() }
                    }
                    PC3.ToolButton {
                        icon.name: "media-playback-start"
                        enabled: root.online
                        onClicked: root.run("buzz " + hc.currentText, r => {})
                    }
                }
            }

            PC3.Label {
                Layout.fillWidth: true
                Layout.topMargin: Kirigami.Units.largeSpacing
                wrapMode: Text.Wrap
                opacity: 0.6
                text: "Saved immediately, the ring picks it up the next time it opens. Folder — double-click its slot in the scheme."
            }
        }
    }

    // "Buttons" tab: profiles on top (app icons, "All applications" first), button cards below;
    // buttons with gestures get a cross "click + 4 directions". Clicking a tile opens the
    // action catalogue right in the card; the choice saves itself (mousectl bindings set, xremap restarts).
    component ButtonsPage: PC3.ScrollView {
        id: bp
        contentWidth: availableWidth

        property bool adding: false
        property bool confirmReset: false
        readonly property var profile: { root.bindRev; return root.bindProfiles[root.bindProfile] || null }
        readonly property bool isDefault: !!profile && !!profile.default

        Timer { id: resetArm; interval: 4000; onTriggered: bp.confirmReset = false }

        ColumnLayout {
            width: parent.width
            spacing: Kirigami.Units.smallSpacing

            // --- profiles ---
            Flow {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing
                Repeater {
                    // profile indices: "All applications" first (it is last in the list), then the apps
                    model: {
                        root.bindRev
                        const n = root.bindProfiles.length
                        const idx = [n - 1]
                        for (let i = 0; i < n - 1; i++) idx.push(i)
                        return n ? idx : []
                    }
                    delegate: PC3.ToolButton {
                        required property int modelData
                        readonly property var p: root.bindProfiles[modelData]
                        checkable: true
                        checked: root.bindProfile === modelData && !bp.adding
                        icon.name: p ? p.icon : ""
                        icon.width: Kirigami.Units.iconSizes.medium
                        icon.height: Kirigami.Units.iconSizes.medium
                        onClicked: { root.bindProfile = modelData; root.bindKey = ""; bp.adding = false }
                        PC3.ToolTip.text: p ? p.name : ""
                        PC3.ToolTip.visible: hovered
                    }
                }
                PC3.ToolButton {
                    icon.name: "list-add"
                    icon.width: Kirigami.Units.iconSizes.medium
                    icon.height: Kirigami.Units.iconSizes.medium
                    checkable: true
                    checked: bp.adding
                    onClicked: bp.adding = !bp.adding
                    PC3.ToolTip.text: "Per-app buttons"
                    PC3.ToolTip.visible: hovered
                }
            }

            // --- add an app ---
            ColumnLayout {
                visible: bp.adding
                Layout.fillWidth: true
                Kirigami.Heading { level: 5; text: "Which app should these buttons apply to?" }
                PickList {
                    source: root.ringData.apps || []
                    placeholder: "Search for an app…"
                    iconRole: "icon"
                    onPicked: item => { root.addProfile(item); bp.adding = false }
                }
            }

            // --- profile header ---
            RowLayout {
                visible: !bp.adding && !!bp.profile
                Layout.fillWidth: true
                Kirigami.Icon {
                    source: bp.profile ? bp.profile.icon : ""
                    implicitWidth: Kirigami.Units.iconSizes.medium
                    implicitHeight: implicitWidth
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    Kirigami.Heading { level: 4; text: bp.profile ? bp.profile.name : ""; Layout.fillWidth: true; elide: Text.ElideRight }
                    PC3.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        font: Kirigami.Theme.smallFont
                        opacity: 0.6
                        text: bp.isDefault ? "This is how the buttons work everywhere without their own settings."
                                           : "Grey means inherited from All applications. Click a tile to change it."
                    }
                }
                PC3.ToolButton {
                    visible: !bp.isDefault
                    icon.name: "edit-delete"
                    onClicked: root.removeProfile()
                    PC3.ToolTip.text: "Remove this app's custom settings"
                    PC3.ToolTip.visible: hovered
                }
            }

            // --- button cards ---
            Repeater {
                model: bp.adding ? [] : (root.bindData.buttons || [])
                delegate: Rectangle {
                    id: card
                    required property var modelData
                    readonly property bool open: modelData.slots.some(s => s.key === root.bindKey)
                    Layout.fillWidth: true
                    implicitHeight: cardCol.implicitHeight + Kirigami.Units.largeSpacing * 2
                    radius: Kirigami.Units.cornerRadius
                    color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.04)
                    border.color: open ? Kirigami.Theme.highlightColor
                                       : Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.12)

                    ColumnLayout {
                        id: cardCol
                        anchors.fill: parent
                        anchors.margins: Kirigami.Units.largeSpacing
                        spacing: Kirigami.Units.smallSpacing

                        RowLayout {
                            Layout.fillWidth: true
                            Kirigami.Heading { level: 5; text: card.modelData.name }
                            PC3.Label {
                                Layout.fillWidth: true
                                text: card.modelData.hint
                                font: Kirigami.Theme.smallFont
                                opacity: 0.6
                                elide: Text.ElideRight
                            }
                        }

                        // one tile or a "click + 4 directions" cross
                        GridLayout {
                            Layout.fillWidth: true
                            columns: card.modelData.slots.length > 1 ? 3 : 1
                            rowSpacing: Kirigami.Units.smallSpacing
                            columnSpacing: Kirigami.Units.smallSpacing
                            Repeater {
                                model: card.modelData.slots.length > 1
                                       ? ["", "up", "", "left", "click", "right", "", "down", ""]
                                       : [card.modelData.slots[0].dir]
                                delegate: SlotTile {
                                    required property string modelData
                                    slot: card.modelData.slots.find(s => s.dir === modelData) || null
                                }
                            }
                        }

                        ActionPicker {
                            visible: card.open
                            slotKey: card.open ? root.bindKey : ""
                            isDefault: bp.isDefault
                        }
                    }
                }
            }

            // --- footer ---
            RowLayout {
                visible: !bp.adding
                Layout.fillWidth: true
                Layout.topMargin: Kirigami.Units.smallSpacing
                PC3.Label {
                    Layout.fillWidth: true
                    text: root.bindStatus
                    opacity: 0.7
                    elide: Text.ElideRight
                }
                PC3.Button {
                    text: bp.confirmReset ? "Sure? Click again" : "Default layout"
                    icon.name: "edit-reset"
                    onClicked: {
                        if (!bp.confirmReset) { bp.confirmReset = true; resetArm.restart(); return }
                        bp.confirmReset = false
                        root.resetDefaults()
                    }
                    PC3.ToolTip.text: "Reset All applications to the defaults; per-app settings are kept"
                    PC3.ToolTip.visible: hovered
                }
            }
        }
    }

    // tile of one key-slot: the direction and what it does; an empty cross cell is invisible
    component SlotTile: Rectangle {
        id: tile
        property var slot: null
        readonly property var profile: { root.bindRev; return root.bindProfiles[root.bindProfile] || null }
        readonly property var a: slot && profile ? profile.keys[slot.key] : null
        readonly property bool selected: !!slot && root.bindKey === slot.key
        readonly property bool inherited: !!a && a.kind === "default"
        readonly property var arrows: ({ click: "●", up: "↑", down: "↓", left: "←", right: "→", wheel: "⇅" })
        Layout.fillWidth: true
        Layout.preferredWidth: 1
        Layout.preferredHeight: Kirigami.Units.gridUnit * 3
        opacity: slot ? 1 : 0
        radius: Kirigami.Units.cornerRadius
        color: selected ? Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g, Kirigami.Theme.highlightColor.b, 0.25)
             : hover.hovered ? Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.10)
             : Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.06)
        border.color: selected ? Kirigami.Theme.highlightColor : "transparent"

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.smallSpacing
            spacing: 0
            PC3.Label {
                Layout.fillWidth: true
                text: tile.slot ? tile.arrows[tile.slot.dir] + " " + tile.slot.label : ""
                font: Kirigami.Theme.smallFont
                opacity: 0.6
                elide: Text.ElideRight
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing
                Kirigami.Icon {
                    readonly property string name: root.actionIcon(tile.a)
                    visible: name !== ""
                    source: name
                    implicitWidth: Kirigami.Units.iconSizes.small
                    implicitHeight: implicitWidth
                    opacity: tile.inherited ? 0.5 : 1
                }
                PC3.Label {
                    Layout.fillWidth: true
                    text: root.actionText(tile.a, tile.profile)
                    elide: Text.ElideRight
                    opacity: tile.inherited || (tile.a && tile.a.kind === "nothing") ? 0.5 : 1
                }
            }
        }
        HoverHandler { id: hover; enabled: !!tile.slot; cursorShape: Qt.PointingHandCursor }
        TapHandler {
            enabled: !!tile.slot
            onTapped: root.bindKey = tile.selected ? "" : tile.slot.key
        }
    }

    // action catalogue for the selected key: ready-made actions by section + app / key combo / KDE action
    component ActionPicker: ColumnLayout {
        id: ap
        property string slotKey: ""
        property bool isDefault: false
        property string mode: ""                 // "", "app", "keys", "kde"
        readonly property bool isWheel: slotKey === "WHEEL"
        readonly property var cur: { root.bindRev; const p = root.bindProfiles[root.bindProfile]; return p && slotKey ? p.keys[slotKey] : null }
        readonly property var entries: {
            const q = search.text.toLowerCase()
            const list = (root.bindData.catalog || []).concat([
                { id: "__app", cat: "Other", name: "Launch an app…", icon: "system-run" },
                { id: "__keys", cat: "Other", name: "Press a key combo…", icon: "input-keyboard" },
                { id: "__kde", cat: "Other", name: "KDE action…", icon: "preferences-desktop-keyboard-shortcut" }
            ]).filter(c => !q || c.name.toLowerCase().includes(q) || c.cat.toLowerCase().includes(q))
            const out = []
            let cat = ""
            for (const c of list) {
                if (c.cat !== cat) { out.push({ header: true, name: c.cat }); cat = c.cat }
                out.push(c)
            }
            return out
        }
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing
        onSlotKeyChanged: { mode = ""; search.text = "" }

        RowLayout {
            Layout.fillWidth: true
            PC3.Button {
                visible: !ap.isDefault
                text: "As in All applications"
                onClicked: root.setSlot(ap.slotKey, { kind: "default" })
            }
            PC3.Button {
                visible: !ap.isWheel
                text: "Nothing"
                onClicked: root.setSlot(ap.slotKey, { kind: "nothing" })
            }
            Item { Layout.fillWidth: true }
            PC3.ToolButton {
                icon.name: "dialog-close"
                onClicked: root.bindKey = ""
                PC3.ToolTip.text: "Close"
                PC3.ToolTip.visible: hovered
            }
        }

        // thumb wheel: only scrolling or tabs
        ColumnLayout {
            visible: ap.isWheel
            Layout.fillWidth: true
            PC3.ItemDelegate {
                Layout.fillWidth: true
                text: "Normal side scroll"
                icon.name: "transform-move-horizontal"
                highlighted: !!ap.cur && ap.cur.kind === "scroll"
                onClicked: root.setSlot(ap.slotKey, { kind: ap.isDefault ? "scroll" : "default" })
            }
            PC3.ItemDelegate {
                Layout.fillWidth: true
                text: "Switch tabs (one tab per 4 clicks)"
                icon.name: "tab-duplicate"
                highlighted: !!ap.cur && ap.cur.kind === "tabs"
                onClicked: root.setSlot(ap.slotKey, { kind: "tabs", prev: "C-Shift-tab", next: "C-tab" })
            }
        }

        // catalogue
        PC3.TextField {
            id: search
            visible: !ap.isWheel && ap.mode === ""
            Layout.fillWidth: true
            placeholderText: "Search for an action…"
            clearButtonShown: true
        }
        ListView {
            visible: !ap.isWheel && ap.mode === ""
            Layout.fillWidth: true
            Layout.preferredHeight: Kirigami.Units.gridUnit * 14
            clip: true
            model: ap.entries
            delegate: PC3.ItemDelegate {
                required property var modelData
                width: ListView.view.width
                text: modelData.name
                font.bold: !!modelData.header
                enabled: !modelData.header
                icon.name: modelData.header ? "" : modelData.icon
                highlighted: !modelData.header && !!ap.cur && ap.cur.kind === "preset" && ap.cur.id === modelData.id
                onClicked: {
                    if (modelData.id === "__app") ap.mode = "app"
                    else if (modelData.id === "__keys") ap.mode = "keys"
                    else if (modelData.id === "__kde") ap.mode = "kde"
                    else root.setSlot(ap.slotKey, { kind: "preset", id: modelData.id })
                }
            }
        }

        PC3.ToolButton {
            visible: ap.mode !== ""
            text: "Back to the action list"
            icon.name: "go-previous"
            onClicked: ap.mode = ""
        }
        PickList {
            visible: ap.mode === "app"
            source: root.ringData.apps || []
            placeholder: "Search for an app…"
            iconRole: "icon"
            currentKey: ap.cur && ap.cur.kind === "app" ? ap.cur.app : ""
            onPicked: item => root.setSlot(ap.slotKey, { kind: "app", app: item.id })
        }
        ColumnLayout {
            visible: ap.mode === "keys"
            Layout.fillWidth: true
            KeyCapture {
                value: ap.cur && ap.cur.kind === "keys" ? ap.cur.keys : ""
                onCommitted: v => { if (v) root.setSlot(ap.slotKey, { kind: "keys", keys: v }) }
            }
            PC3.Label {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                font: Kirigami.Theme.smallFont
                opacity: 0.6
                text: "Click Record, then press the combo. Combos with Meta are grabbed by KDE — type them instead, e.g. Super-w, and press Enter."
            }
        }
        PickList {
            visible: ap.mode === "kde"
            source: root.ringData.shortcuts || []
            placeholder: "Search for a KDE action…"
            textRole: "friendly"
            keyRole: "name"
            currentKey: ap.cur && ap.cur.kind === "kde" ? ap.cur.name : ""
            onPicked: item => root.setSlot(ap.slotKey, { kind: "kde", component: item.component, name: item.name })
        }
    }

    // searchable list: apps, KDE actions
    component PickList: ColumnLayout {
        id: pl
        property var source: []
        property string placeholder: "Search…"
        property string textRole: "name"
        property string iconRole: ""
        property string keyRole: "id"
        property string currentKey: ""
        signal picked(var item)
        Layout.fillWidth: true

        PC3.TextField {
            id: plFilter
            Layout.fillWidth: true
            placeholderText: pl.placeholder
            clearButtonShown: true
        }
        ListView {
            Layout.fillWidth: true
            Layout.preferredHeight: Kirigami.Units.gridUnit * 11
            clip: true
            model: {
                const q = plFilter.text.toLowerCase()
                return pl.source.filter(x => !q || String(x[pl.textRole]).toLowerCase().includes(q))
            }
            delegate: PC3.ItemDelegate {
                required property var modelData
                width: ListView.view.width
                text: modelData[pl.textRole]
                icon.name: pl.iconRole ? modelData[pl.iconRole] : ""
                highlighted: pl.currentKey !== "" && modelData[pl.keyRole] === pl.currentKey
                onClicked: pl.picked(modelData)
            }
        }
    }

    // key combo in xremap syntax (C-Shift-t, Super-left): type it by hand or click Record.
    // Global KDE combos (Meta+W etc.) are grabbed by KWin first — type them by hand.
    component KeyCapture: RowLayout {
        id: kc
        property string value: ""
        signal committed(string v)
        Layout.fillWidth: true

        PC3.TextField {
            Layout.fillWidth: true
            font.family: "monospace"
            placeholderText: "C-Shift-t"
            text: kc.value
            onAccepted: kc.committed(text.trim())
        }
        PC3.Button {
            id: rec
            checkable: true
            text: checked ? "Press…" : "Record"
            icon.name: "media-record"
            onCheckedChanged: if (checked) catcher.forceActiveFocus()
        }
        Item {
            id: catcher
            width: 1; height: 1
            onActiveFocusChanged: if (!activeFocus) rec.checked = false
            Keys.onPressed: event => {
                event.accepted = true
                const name = root.evdevNames[event.nativeScanCode - 8]
                if (!name) return                        // only a modifier is pressed — waiting for a key
                const m = event.modifiers
                if (name === "esc" && !m) { rec.checked = false; return }
                const v = (m & Qt.ControlModifier ? "C-" : "") + (m & Qt.ShiftModifier ? "Shift-" : "")
                          + (m & Qt.AltModifier ? "M-" : "") + (m & Qt.MetaModifier ? "Super-" : "") + name
                rec.checked = false
                kc.committed(v)
            }
        }
    }

    // settings slider: the value comes from the mouse, written on release
    component SettingSlider: ColumnLayout {
        id: ss
        required property string key
        required property string label
        property string suffix: ""
        property string hint: ""
        property real from: 0
        property real to: 100
        property real step: 1
        readonly property var current: root.mouse[key]
        Layout.fillWidth: true
        spacing: 0
        enabled: root.online && current !== undefined

        RowLayout {
            Layout.fillWidth: true
            PC3.Label { text: ss.label; Layout.fillWidth: true }
            PC3.Label { text: Math.round(slider.value) + ss.suffix; font.bold: true }
        }
        PC3.Slider {
            id: slider
            Layout.fillWidth: true
            from: ss.from; to: ss.to; stepSize: ss.step; snapMode: PC3.Slider.SnapAlways
            onPressedChanged: if (!pressed && Math.round(value) !== ss.current) root.setValue(ss.key, Math.round(value))
            Component.onCompleted: if (ss.current !== undefined) value = ss.current
        }
        Connections {
            target: ss
            function onCurrentChanged() { if (!slider.pressed && ss.current !== undefined) slider.value = ss.current }
        }
        PC3.Label {
            visible: ss.hint !== ""
            text: ss.hint
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            font: Kirigami.Theme.smallFont
            opacity: 0.6
        }
    }
}
