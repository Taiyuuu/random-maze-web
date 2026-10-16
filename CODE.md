# Code Overview (`main.py`)

```py
import modules

# in-game, runtime, settings variables
# helper functions and custom_running()

while custom_running():
    if game_state == "MENU":
        if not show_quit_confirm:
            # draw normal main menu
        else:
            # draw quit confirm menu

    elif game_state == "OPTIONS":
        if options_sub_menu == None:
            # main options menu

        elif options_sub_menu == "game":
            # game optiond sub menu

        elif options_sub_menu == "audio":
            # audio options sub menu

        elif options_sub_menu == "keyboard":
            # keybind options sub menu


    elif game_state == "GAME":
        if not (console_available and console.active) and not show_quit_confirm and not game_won and not game_over and not game_pause:
            # update player, timer

        if opt_boss_mode and boss_logic_available and not game_over and not game_won and not game_pause and not show_quit_confirm:
            # run boss logic

        for c in range(first_c, last_c + 1):
            for r in range(first_r, last_r + 1):
                # draw tiles

        if opt_keys_enabled:
            # draw keys

        if opt_limited_vis and opt_realistic_vis and not survival_active:
            # draw wall shadows

        if opt_boss_mode and boss_logic_available:
            # draw boss

        # draw player

        if opt_limited_vis:
            # draw fog vision

        if show_hud:
            # draw hud

        if player.hp <= 1:
            # low health effect

        if opt_boss_mode and boss_logic_available:
            # draw boss hud

        if show_minimap:
            # draw minimap

        if show_collisionbox:
            # draw collision boxes

        if show_quit_confirm:
            # quit confirm menu

        if return_confirm and not show_quit_confirm:
            # return to main menu warning menu

        if game_pause and not show_quit_confirm and not return_confirm:
            # pause menu

        if game_won and not show_quit_confirm and not return_confirm:
            # game won menu

        elif game_over and not show_quit_confirm and not return_confirm:
            # game over menu

        if console_available:
            # draw dev console

    # update custom cursor

# quit program
```