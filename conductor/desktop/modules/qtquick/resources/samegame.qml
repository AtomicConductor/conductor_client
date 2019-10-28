import QtQuick 1.0

Rectangle {
 id: screen

width: 490; height: 720

SystemPalette { id: activePalette }

Item {
 width: parent.width
 anchors { top: parent.top; bottom: toolBar.top }

Image {
 id: background
 anchors.fill: parent
 source: "../shared/pics/background.jpg"
 fillMode: Image.PreserveAspectCrop
 }
 }

Rectangle {
 id: toolBar
 width: parent.width; height: 30
 color: activePalette.window
 anchors.bottom: screen.bottom

Button {
 anchors { left: parent.left; verticalCenter: parent.verticalCenter }
 text: "New Game"
 onClicked: console.log("This doesn't do anything yet…")
 }

Text {
 id: score
 anchors { right: parent.right; verticalCenter: parent.verticalCenter }
 text: "Score: Who knows?"
 }
 }
}