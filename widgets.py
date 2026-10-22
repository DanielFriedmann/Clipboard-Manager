import customtkinter as ctk

ICON_FONT = ("Segoe UI Semibold", 12)


def text_color_for(background):
    # Hex-Farbe wie "#fff176" in ihre drei Anteile zerlegen
    red = int(background[1:3], 16)
    green = int(background[3:5], 16)
    blue = int(background[5:7], 16)

    # Wahrgenommene Helligkeit: Grün wirkt am hellsten, Blau am dunkelsten
    brightness = 0.299 * red + 0.587 * green + 0.114 * blue
    return "#1a1a1a" if brightness > 150 else "#ffffff"


class GroupIcon(ctk.CTkFrame):
    # Farbiges Quadrat mit einem Zeichen in der Mitte

    def __init__(self, master, color, text, size=24, text_color=None):
        super().__init__(master, width=size, height=size, corner_radius=5, fg_color=color)
        self.pack_propagate(False)   # feste Größe, unabhängig vom Inhalt

        if text_color is None:
            text_color = text_color_for(color)

        self.label = ctk.CTkLabel(self, text=text, font=ICON_FONT, text_color=text_color,
                                  width=size, height=size)
        self.label.place(relx=0.5, rely=0.5, anchor="center")