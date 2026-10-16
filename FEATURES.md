# Features & How to Play


## Controls

Default controls:

*   **Movement:** `W`, `A`, `S`, `D`
*   **Sword Swing:** `Arrow Keys`
*   **Heal:** `Space` (Hold; 3 accumulated sword hits grant $1$ HP back)
*   **Circular Swing:** `Space` (Quick press; damages enemies in a circular area)
*   **Projectile:** `Space` + `Arrow key` (Quick press; fires a projectile that damages enemies)
*   **Developer Console:** `` ` ``, see **[commands.txt](commands.txt)** for available commands
*   **Pause In-Game:** `Esc`

---

## Game Features

### Maze Generation & Customization
*   **Configurable Dimensions:** Adjust the grid columns (`3` to `50`) and rows (`3` to `50`).
*   **Tile Scaling:** Adjust the tile size (`20px` to `500px`).
*   **Themes:** Cycle through multiple aesthetic themes (such as the default theme) to change the look of walls, floors, and atmosphere.

### Vision Systems
*   **Fog Vision:** Enable a limited visibility radius around player to explore shadowed corridors. Adjust the radius from `1` to `15` tiles.
*   **Realistic Vision:** Cast dynamic wall shadows and block line-of-sight based on maze geometry (requires Fog Vision to be active).

### Combat / Survival Modes
*   **Chasing Enemies:** Enable roaming enemies that track the player down after a configurable delay (`1` to `60` seconds).
*   **Survival Mode:** Face waves of enemies spawning across the map. Opt to eliminate all enemies to clear the challenge.
*   **Health & Healing:** Manage health ($\text{HP}$). Attack enemies or charge heal meter using the `Space` key to recover health.

### Special Objectives & Boss Fights
*   **Find Keys:** Enable hidden keys scattered throughout non-shortest-path cells. Collect all required keys to unlock path forward.
*   **Final Boss Mode:** Reach the end of the maze to enter a custom $5 \times 5$ arena and battle a challenging final boss encounter with dedicated mechanics.

### Settings, Saves & Audio
*   **Persistent Settings:** Export and import your custom configurations using `settings.json`, with an option to apply settings automatically on startup.
*   **Audio Controls:** Independently tweak Master, Sound Effects (SFX), and Music volumes, or toggle background music on/off.
*   **Maze Saving:** Save completed or lost mazes to `saved_maze.json` and reload them instantly from the main menu.