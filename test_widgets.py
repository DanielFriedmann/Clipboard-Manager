import customtkinter as ctk

from widgets import GroupIcon, text_color_for

ctk.set_appearance_mode("system")

root = ctk.CTk()
root.title("Test Symbole")

# Gruppenfarben aus den Testdaten und ein paar Extremfälle
for color, letter in [
    ("#e57373", "A"), ("#81c784", "P"), ("#64b5f6", "K"),
    ("#fff176", "I"), ("#9e9e9e", "U"), ("#1a237e", "D"), ("#ffffff", "W"),
]:
    print(f"{color} → {text_color_for(color)}")
    GroupIcon(root, color, letter).pack(side="left", padx=6, pady=16)

# "Alle Einträge" und "Neue Gruppe" mit eigener Schriftfarbe
GroupIcon(root, ("#d0d0d0", "#4a4a4a"), "▤",
          text_color=("#1a1a1a", "#f2f2f2")).pack(side="left", padx=6)
GroupIcon(root, "transparent", "＋",
          text_color=("#6b6b6b", "#a0a0a0")).pack(side="left", padx=6)

root.mainloop()