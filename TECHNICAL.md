# Development / Technical Guide

* **Core Library:** Pygame `pygame` (the Pillow `PIL` library was also used to write the **[tile generation script](tile_gen.py)**)
* **Custom Wrapper:** `mckPy` (Simplified drawing, text rendering, and event loops)

---

## Breakdown

The project is structured into components to keep game logic, rendering, audio, and UI clearly separated:

1. **`main.py`:**
   * Manages the game states (`MENU`, `OPTIONS`, `GAME`).
   * Controls the drawing and overlay management (pause screens, win/loss dialogs, dev console integration).

2. **`maze.py`:**
   * Implements maze generation algorithm (recursive backtracking / Depth-First Search).
   * Manages cell walls (`N`, `S`, `E`, `W`), shortest paths, grid dimensions, and tile type resolution.

3. **`player.py` & `enemy.py`:**
   * **Player:** Handles movement collision checks against maze walls, attack cooldowns, health management, and healing mechanics.
   * **Enemy Manager:** Coordinates enemy pathfinding/chasing logic, spawn rates, AI delays, and survival mode waves.

4. **`rendering.py`:**
   * Caches and scales tile images (`get_tile_image`).
   * Generates dynamic fog-of-war surfaces (`get_fog_surface`) and real-time wall shadow casting (`draw_wall_shadows`).

5. **`audio.py` & `ui.py`:**
   * **Audio:** Manages master, SFX, and music volume controls, state-based background audio tracks, and audio cues.
   * **UI:** Draws stylized buttons, toggle switches, decorative Fleur frames, and custom mouse cursors.

6. **`console.py` & `commands.py`:**
   * Provides an in-game developer console accessed via the `` ` `` key to run diagnostic commands or manipulate game state dynamically.