"""Developer console for debugging and cheats."""
from mckPy import *


class ConsoleHistory(list):
    """List wrapper storing a per-entry color for rendering."""

    def __init__(self):
        super().__init__()
        self.colors = []

    def append(self, value, color="lightgreen"):
        super().append(value)
        self.colors.append(color)

    def add(self, value, color="lightgreen"):
        self.append(value, color)

    def set_color(self, index, color):
        if 0 <= index < len(self.colors):
            self.colors[index] = color

    def trim(self, max_items):
        while len(self) > max_items:
            del self[0]
            del self.colors[0]


class DeveloperConsole:
    def __init__(self):
        self.active = False
        self.input_text = ""
        self.history = ConsoleHistory()
        self.command_history = []
        self.history_index = 0
        self.max_history = 20

    def toggle(self):
        self.active = not self.active

    def _history_color(self, line):
        text = str(line).lower()
        if any(token in text for token in ("error", "unknown", "invalid", "failed", "no such")):
            return "red"
        return "lightgreen"

    def record_result(self, command, ok, result=None):
        """Save the result of a command and give it an appropriate color."""
        cmd = str(command).strip()
        if cmd:
            self.command_history.append(cmd)
            self.history_index = len(self.command_history)
            self.history.add(">> " + cmd, "white")
        if result is not None:
            message = str(result)
        elif ok:
            message = "OK"
        else:
            message = "Command failed"
        self.history.add(message, "lightgreen" if ok else "red")
        self.history.trim(self.max_history)

    def _switch_history(self, direction):
        if not self.command_history:
            return

        if direction < 0:
            if self.history_index > 0:
                self.history_index -= 1
            else:
                self.history_index = 0
                self.input_text = ""
                return
        else:
            if self.history_index < len(self.command_history):
                self.history_index += 1
            else:
                self.history_index = len(self.command_history)
                self.input_text = ""
                return

        if self.history_index >= len(self.command_history):
            self.input_text = ""
        else:
            self.input_text = self.command_history[self.history_index]

    def handle_event(self, event_obj):
        if not self.active:
            return None
        if event_obj.type == KEYDOWN:
            if event_obj.key == K_UP:
                self._switch_history(-1)
                return None
            if event_obj.key == K_DOWN:
                self._switch_history(1)
                return None
            if event_obj.key == K_RETURN:
                cmd = self.input_text.strip()
                if cmd:
                    self.command_history.append(cmd)
                    self.history_index = len(self.command_history)
                self.input_text = ""
                return cmd
            elif event_obj.key == K_BACKSPACE:
                self.input_text = self.input_text[:-1]
            else:
                char = event_obj.unicode
                if char and ord(char) >= 32:
                    self.input_text += char
        return None

    def draw(self, screen_width, screen_height):
        if not self.active:
            return
        # Semi-transparent console background
        surf = Surface((screen_width, 220), SRCALPHA)
        surf.fill((10, 10, 10, 210))
        display.get_surface().blit(surf, (0, 0))

        # Draw history lines
        y = 10
        visible = self.history[-9:]
        for idx, line in enumerate(visible):
            actual_index = len(self.history) - len(visible) + idx
            color = self.history.colors[actual_index] if actual_index < len(self.history.colors) else self._history_color(line)
            drawText(color, line, 15, y, font=(TRAJAN_REGULAR, 16))
            y += 20

        # Input box
        drawRect((40, 40, 40), 10, 180, screen_width - 20, 30, corner=4)
        drawText("yellow", ">>> " + self.input_text + "_", 20, 185, font=(TRAJAN_REGULAR, 18))