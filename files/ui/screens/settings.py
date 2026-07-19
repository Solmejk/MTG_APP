from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)

from ui.components.toggle_switch import ToggleSwitch


class SettingsScreen(QWidget):
    """User settings — currently houses cache controls; will grow over time."""
    
    clear_cache_requested = Signal(list)  # list of strings: "collection", "decks", "profile"
    
    def __init__(self):
        super().__init__()
        
        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 30, 40, 40)
        outer.setSpacing(20)
        
        # Header
        title = QLabel("Settings")
        title.setObjectName("screenTitle")
        outer.addWidget(title)
        
        # Cache section
        outer.addWidget(self._build_cache_section())
        
        outer.addStretch()
    
    def _build_cache_section(self) -> QWidget:
        section = QFrame()
        section.setObjectName("settingsSection")
        section.setMaximumWidth(480)
        
        layout = QVBoxLayout(section)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        
        header = QLabel("Cache")
        header.setObjectName("settingsSectionTitle")
        layout.addWidget(header)
        
        description = QLabel(
            "Choose what to clear. Cleared data will be re-fetched on next app launch."
        )
        description.setObjectName("settingsDescription")
        description.setWordWrap(True)
        layout.addWidget(description)
        
        self._collection_toggle = self._toggle_row(layout, "Collection")
        self._decks_toggle = self._toggle_row(layout, "Decks")
        self._profile_toggle = self._toggle_row(layout, "Profile")
        self._images_toggle = self._toggle_row(layout, "Images")
        
        # Button row aligned to the right
        button_row = QHBoxLayout()
        button_row.addStretch()
        clear_btn = QPushButton("Clear selected")
        clear_btn.clicked.connect(self._on_clear_clicked)
        button_row.addWidget(clear_btn)
        layout.addLayout(button_row)
        
        return section
    
    def _toggle_row(self, parent_layout: QVBoxLayout, label: str) -> ToggleSwitch:
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        
        lbl = QLabel(label)
        lbl.setObjectName("settingsLabel")
        row_layout.addWidget(lbl)
        row_layout.addStretch()
        
        toggle = ToggleSwitch(checked=True)
        row_layout.addWidget(toggle)
        
        parent_layout.addLayout(row_layout)  # ← addLayout, not addWidget
        return toggle
    
    def _on_clear_clicked(self):
        targets = []
        if self._collection_toggle.isChecked():
            targets.append("collection")
        if self._decks_toggle.isChecked():
            targets.append("decks")
        if self._profile_toggle.isChecked():
            targets.append("profile")
        if self._images_toggle.isChecked():
            targets.append("images")
        if targets:
            self.clear_cache_requested.emit(targets)