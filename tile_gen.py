import os
from PIL import Image, ImageDraw, ImageFilter, ImageChops

TILE_SIZE = 512
MARGIN = 78       # collision and border width matching my game spec
SHADOW_BLUR = 20  # px shadow spread
SHADOW_OPACITY = 255 # darkness of the shadow (0-255)

# Specify which tiles to generate. Leave empty or set to None to generate all tiles.
GENERATE_TILES = []

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def generate_tiles():
    tiles_dir = os.path.join("tiles")
    ensure_dir(tiles_dir)

    try:
        master_grass = Image.open(os.path.join(tiles_dir, "grass.png")).convert("RGBA").resize((TILE_SIZE, TILE_SIZE))
        master_dirt = Image.open(os.path.join(tiles_dir, "dirt.png")).convert("RGBA").resize((TILE_SIZE, TILE_SIZE))
    except FileNotFoundError:
        print("Error: 'grass.png' or 'dirt.png' not found in the 'tiles/' directory.")
        return

    # Base tiles
    master_grass.save(os.path.join(tiles_dir, "grass.png"))
    master_dirt.save(os.path.join(tiles_dir, "dirt.png"))

    def make_tile(draw_shapes_func):
        tile = master_grass.copy()
        
        # 1. Create path mask where dirt is white, grass is black
        mask = Image.new("L", (TILE_SIZE, TILE_SIZE), 0)
        draw = ImageDraw.Draw(mask)
        draw_shapes_func(draw)
        
        # 2. Generate shadow along the grass-dirt border
        grass_mask = Image.eval(mask, lambda px: 255 - px)
        shadow_mask = grass_mask.filter(ImageFilter.GaussianBlur(SHADOW_BLUR))
        shadow_mask = ImageChops.multiply(shadow_mask, mask)
        
        shadow_layer = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
        black_fill = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, SHADOW_OPACITY))
        shadow_layer.paste(black_fill, (0, 0), shadow_mask)
        
        # 3. Composite everything onto the tile
        tile.paste(master_dirt, (0, 0), mask)
        tile = Image.alpha_composite(tile, shadow_layer)
        
        return tile

    def draw_ns(draw):
        draw.rectangle([MARGIN, 0, TILE_SIZE - MARGIN, TILE_SIZE], fill=255)

    def draw_we(draw):
        draw.rectangle([0, MARGIN, TILE_SIZE, TILE_SIZE - MARGIN], fill=255)

    def draw_n(draw):
        draw.rectangle([MARGIN, 0, TILE_SIZE - MARGIN, TILE_SIZE - MARGIN], fill=255)

    def draw_s(draw):
        draw.rectangle([MARGIN, MARGIN, TILE_SIZE - MARGIN, TILE_SIZE], fill=255)

    def draw_e(draw):
        draw.rectangle([MARGIN, MARGIN, TILE_SIZE, TILE_SIZE - MARGIN], fill=255)

    def draw_w(draw):
        draw.rectangle([0, MARGIN, TILE_SIZE - MARGIN, TILE_SIZE - MARGIN], fill=255)

    def draw_ne(draw):
        draw.rectangle([MARGIN, 0, TILE_SIZE - MARGIN, TILE_SIZE - MARGIN], fill=255)
        draw.rectangle([MARGIN, MARGIN, TILE_SIZE, TILE_SIZE - MARGIN], fill=255)

    def draw_nw(draw):
        draw.rectangle([MARGIN, 0, TILE_SIZE - MARGIN, TILE_SIZE - MARGIN], fill=255)
        draw.rectangle([0, MARGIN, TILE_SIZE - MARGIN, TILE_SIZE - MARGIN], fill=255)

    def draw_se(draw):
        draw.rectangle([MARGIN, MARGIN, TILE_SIZE - MARGIN, TILE_SIZE], fill=255)
        draw.rectangle([MARGIN, MARGIN, TILE_SIZE, TILE_SIZE - MARGIN], fill=255)

    def draw_sw(draw):
        draw.rectangle([MARGIN, MARGIN, TILE_SIZE - MARGIN, TILE_SIZE], fill=255)
        draw.rectangle([0, MARGIN, TILE_SIZE - MARGIN, TILE_SIZE - MARGIN], fill=255)

    def draw_ne_(draw):
        draw.rectangle([MARGIN, 0, TILE_SIZE - MARGIN, TILE_SIZE - MARGIN], fill=255)
        draw.rectangle([MARGIN, 0, TILE_SIZE, TILE_SIZE - MARGIN], fill=255)

    def draw_nw_(draw):
        draw.rectangle([MARGIN, 0, TILE_SIZE - MARGIN, TILE_SIZE - MARGIN], fill=255)
        draw.rectangle([0, 0, TILE_SIZE - MARGIN, TILE_SIZE - MARGIN], fill=255)

    def draw_se_(draw):
        draw.rectangle([MARGIN, MARGIN, TILE_SIZE - MARGIN, TILE_SIZE], fill=255)
        draw.rectangle([MARGIN, MARGIN, TILE_SIZE, TILE_SIZE], fill=255)

    def draw_sw_(draw):
        draw.rectangle([MARGIN, MARGIN, TILE_SIZE - MARGIN, TILE_SIZE], fill=255)
        draw.rectangle([0, MARGIN, TILE_SIZE - MARGIN, TILE_SIZE], fill=255)

    def draw_wall_n(draw):
        draw.rectangle([0, MARGIN, TILE_SIZE, TILE_SIZE], fill=255)

    def draw_wall_e(draw):
        draw.rectangle([0, 0, TILE_SIZE - MARGIN, TILE_SIZE], fill=255)

    def draw_wall_s(draw):
        draw.rectangle([0, 0, TILE_SIZE, TILE_SIZE - MARGIN], fill=255)

    def draw_wall_w(draw):
        draw.rectangle([MARGIN, 0, TILE_SIZE, TILE_SIZE], fill=255)

    def draw_3_n(draw):
        draw.rectangle([0, MARGIN, TILE_SIZE, TILE_SIZE - MARGIN], fill=255)
        draw.rectangle([MARGIN, MARGIN, TILE_SIZE - MARGIN, TILE_SIZE], fill=255)

    def draw_3_s(draw):
        draw.rectangle([0, MARGIN, TILE_SIZE, TILE_SIZE - MARGIN], fill=255)
        draw.rectangle([MARGIN, 0, TILE_SIZE - MARGIN, TILE_SIZE - MARGIN], fill=255)

    def draw_3_e(draw):
        draw.rectangle([MARGIN, 0, TILE_SIZE - MARGIN, TILE_SIZE], fill=255)
        draw.rectangle([0, MARGIN, TILE_SIZE - MARGIN, TILE_SIZE - MARGIN], fill=255)

    def draw_3_w(draw):
        draw.rectangle([MARGIN, 0, TILE_SIZE - MARGIN, TILE_SIZE], fill=255)
        draw.rectangle([MARGIN, MARGIN, TILE_SIZE, TILE_SIZE - MARGIN], fill=255)

    def draw_4(draw):
        draw.rectangle([MARGIN, 0, TILE_SIZE - MARGIN, TILE_SIZE], fill=255)
        draw.rectangle([0, MARGIN, TILE_SIZE, TILE_SIZE - MARGIN], fill=255)

    def draw_boss(draw):
        draw.rectangle([0, 0, TILE_SIZE - MARGIN, TILE_SIZE], fill=255)
        draw.rectangle([0, MARGIN, TILE_SIZE, TILE_SIZE - MARGIN], fill=255)

    tile_definitions = {
        "ns": draw_ns,
        "we": draw_we,
        "n": draw_n,
        "s": draw_s,
        "e": draw_e,
        "w": draw_w,
        "ne": draw_ne,
        "nw": draw_nw,
        "se": draw_se,
        "sw": draw_sw,
        "ne_": draw_ne_,
        "nw_": draw_nw_,
        "se_": draw_se_,
        "sw_": draw_sw_,
        "wall_n": draw_wall_n,
        "wall_e": draw_wall_e,
        "wall_s": draw_wall_s,
        "wall_w": draw_wall_w,
        "3_n": draw_3_n,
        "3_e": draw_3_e,
        "3_s": draw_3_s,
        "3_w": draw_3_w,
        "4": draw_4,
        "boss_entrance": draw_boss
    }

    targets = GENERATE_TILES if (GENERATE_TILES and len(GENERATE_TILES) > 0) else tile_definitions.keys()

    print(f"Generating selected tiles: {list(targets)}...")
    for filename in targets:
        if filename in tile_definitions:
            img = make_tile(tile_definitions[filename])
            img.save(os.path.join(tiles_dir, f"{filename}.png"))
            print(f"Created: {filename}.png")
        else:
            print(f"Warning: Tile '{filename}' not found in definitions.")

    print("Tile generation complete!")

if __name__ == "__main__":
    generate_tiles()