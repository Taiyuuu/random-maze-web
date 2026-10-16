import pygame
import sys

# Initialize Pygame
pygame.init()
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Configure Custom Cursor Hotspot")
clock = pygame.time.Clock()

# Hide default system pointer
pygame.mouse.set_visible(False)

# Load the original cursor image
try:
    orig_cursor_img = pygame.image.load("cursor.png").convert_alpha()
except pygame.error:
    print("Error: Could not find 'cursor.png'. Please place it in the same folder as this script.")
    sys.exit()

# Image dimensions and configuration
orig_w, orig_h = orig_cursor_img.get_size()
cursor_scale = 1.0  # Scale factor (1.0 = original size)

# Hotspot offset (Relative to the top-left corner (0,0) of the scaled cursor image)
# Start it at the center of the image by default
hotspot_x = int(orig_w * cursor_scale) // 2
hotspot_y = int(orig_h * cursor_scale) // 2

# Track cursor position on screen
cursor_pos = [WIDTH // 2, HEIGHT // 2]

# Main Loop
running = True
while running:
    # 1. Dynamic Scaling Calculations
    new_w = int(orig_w * cursor_scale)
    new_h = int(orig_h * cursor_scale)
    scaled_cursor = pygame.transform.scale(orig_cursor_img, (new_w, new_h))

    # 2. Handle Events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            
        elif event.type == pygame.KEYDOWN:
            # Adjust image scale with [ and ] keys
            if event.key == pygame.K_LEFTBRACKET:    # [ key
                cursor_scale = max(0.1, cursor_scale - 0.05)
                # Keep hotspot within new scaled bounds
                hotspot_x = min(hotspot_x, new_w)
                hotspot_y = min(hotspot_y, new_h)
            elif event.key == pygame.K_RIGHTBRACKET: # ] key
                cursor_scale = min(5.0, cursor_scale + 0.05)
                
            # Enter key prints exact code template incorporating the custom hotspot offset
            elif event.key == pygame.K_RETURN:
                print("\n--- Copy this code for your other program ---")
                print(f"# 1. Load and scale your cursor image during setup:")
                print(f"cursor_img = pygame.image.load('cursor.png').convert_alpha()")
                print(f"cursor_img = pygame.transform.scale(cursor_img, ({new_w}, {new_h}))")
                print(f"\n# 2. Use these calculated hotspot offsets in your drawing loop:")
                print(f"hotspot_offset_x = {hotspot_x}")
                print(f"hotspot_offset_y = {hotspot_y}")
                print(f"\n# 3. Put this in your drawing loop (x, y are mouse positions):")
                print(f"screen.blit(cursor_img, (x - hotspot_offset_x, y - hotspot_offset_y))")
                print("---------------------------------------------")

        # Sync with physical mouse movement
        elif event.type == pygame.MOUSEMOTION:
            cursor_pos = list(event.pos)

    # 3. Continuous Keyboard Input (Arrow Keys adjust the HOTSPOT offset)
    keys = pygame.key.get_pressed()
    if keys[pygame.K_LEFT]:  hotspot_x = max(0, hotspot_x - 1)
    if keys[pygame.K_RIGHT]: hotspot_x = min(new_w, hotspot_x + 1)
    if keys[pygame.K_UP]:    hotspot_y = max(0, hotspot_y - 1)
    if keys[pygame.K_DOWN]:  hotspot_y = min(new_h, hotspot_y + 1)

    # 4. Calculate where to render the image (Fixes the list-and-int TypeError)
    render_x = cursor_pos[0] - hotspot_x
    render_y = cursor_pos[1] - hotspot_y

    # 5. Drawing
    screen.fill((40, 40, 40)) # Charcoal background
    
    # Draw custom image
    screen.blit(scaled_cursor, (render_x, render_y))
    
    # Draw reference marker (Red crosshair) precisely at the exact click point
    pygame.draw.line(screen, (255, 0, 0), (cursor_pos[0] - 6, cursor_pos[1]), (cursor_pos[0] + 6, cursor_pos[1]), 1)
    pygame.draw.line(screen, (255, 0, 0), (cursor_pos[0], cursor_pos[1] - 6), (cursor_pos[0], cursor_pos[1] + 6), 1)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()
