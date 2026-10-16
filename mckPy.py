"""
mckPy.py
- This is designed to make learning graphics as easy as possible. It's just a wrapper
for pygame.
"""

# Import all pygame modules and system module
from pygame import *
from random import *
from math import *
from glob import *
import os
import sys


# Initialize pygame
init()

TRAJAN_REGULAR = os.path.join(os.path.dirname(__file__), "Trajan-regular.ttf")
TRAJAN_BOLD = os.path.join(os.path.dirname(__file__), "Trajan-bold.otf")

allFonts = {}
fnt = font.Font(TRAJAN_REGULAR, 24)
allFonts[(TRAJAN_REGULAR, 24)] = fnt

# Set up the display window
screen = display.set_mode((800, 600))

# Create a clock object to manage frame rate
myClock = time.Clock()

# Track mouse button clicks: [left, middle, right, upwheel, downwheel]
clicked = [False, False, False, False, False]

# Default frames per second
FPS = 60

"""
"mario" -> {frame:0, move:"", delay:0, maxDelay:4, moves -> {"up":[], "down":[]}}
"""
barriers = []
maskImage = None
maskValues = {}
barrierDrawOffsetX = 0
barrierDrawOffsetY = 0

class Barrier(Rect):
    def __init__(self, left, top, width, height, colour="black", kind="wall", image=None, animation = None):
        super().__init__(left, top, width, height)
        self.colour = colour
        self.kind = kind
        if image != None:
            iw, ih = image.get_size()
            if iw != width or ih != height:
                if iw > width and ih > height:
                    image = image.subsurface((0,0,width, height))
                else:
                    image = transform.smoothscale(image,(width, height))
        self.image=image
        self.animation = animation

    def move(self, dx, dy):
        self.left += dx
        self.top += dy

    def setXY(self, x, y):
        self.left = x
        self.top = y

    def draw(self, surface, outline, outlineColour, pos):
        if self.image != None:
            screen.blit(self.image, (self.left, self.top))
        elif self.animation != None:
            drawAnimation(self.animation, self.left, self.top, True)
        else:
            draw.rect(surface, self.colour, self)
        if pos != -1:
            drawText(0, str(pos), self.left+5, self.top+5)
        if outline > 0:
            draw.rect(surface, outlineColour, self, outline)

def getOffsetX():
    return barrierDrawOffsetX
    
def getOffsetY():
    return barrierDrawOffsetY
    
def loadAnimation(name, newWidth=0, newHeight=0, delay = 4, startFrame = 0, centerX=False, centerY=False):
    ani = {}    
    folders = [f for f in os.listdir(name) if os.path.isdir(os.path.join(name, f))]
    moves = {}
    maxW = {}
    maxH = {}
    for f in folders:
        moves[f] = [ ]
        maxW[f] = 0
        maxH[f] = 0
        for fn in os.listdir(os.path.join(name, f)):
            nname = os.path.join(name, f, fn)
            pic = loadImage(nname, newWidth, newHeight)
            wid, hei = pic.get_size()
            maxW[f] = max(maxW[f], wid)
            maxH[f] = max(maxH[f], hei)
            moves[f].append(pic)

    ani["frame"] = startFrame
    ani["move"] = folders[0]
    ani["delay"] = 0
    ani["maxDelay"] = delay
    ani["moves"] = moves
    ani["centerX"] = centerX
    ani["centerY"] = centerY
    ani["maxW"] = maxW
    ani["maxH"] = maxH
    
    return ani
    


def drawAnimation(ani, x, y, advance = True):
    """ ani must be loaded with loadAnimation. Draws character at its
        current location showing current move.
    """
    move = ani["move"]
    pics = ani["moves"][move]
    maxW = ani["maxW"][move]
    maxH = ani["maxH"][move]
    if advance:
        ani["delay"] += 1
        if ani["delay"] == ani["maxDelay"]:
            ani["delay"] = 0
            ani["frame"] += 1
            if ani["frame"] == len(pics):
                ani["frame"] = 0
    pic = pics[ani["frame"]]
    offx = 0
    offy = 0
    if ani["centerX"]:
        wid, hei = pic.get_size()
        offx = (maxW - wid) // 2
        offy = (maxH - hei) // 2
        
    screen.blit(pic, (x+offx, y+offy))

def changeMove(ani, newMove):
    """name must be loaded with loadCharacter. Changes to a valid move"""
    if ani["move"] == newMove: return
    if newMove in ani["moves"]:
        ani["move"] = newMove
        ani["frame"] = 0
        
def addFlippedMove(ani, move, newName):
    """name must be loaded with loadCharacter. Changes to a valid move"""
    moves = ani["moves"]
    moves[newName] = [transform.flip(pic, True, False) for pic in moves[move]]
    ani["maxW"][newName] = ani["maxW"][move]
    ani["maxH"][newName] = ani["maxH"][move]

def loadSound(name):
    """You should be loading *.wav files. Use playSound to play. e.g.
        shot = loadSound("shot.wav") # once, before while running():
        playSound(shot)      # whenever you want the sound to play
    """
    return mixer.Sound(name)

def playSound(snd):
    """ Sound should be loaded with loadSound
        shot = loadSound("shot.wav") # once, before while running():
        playSound(shot)      # whenever you want the sound to play
    """
    snd.play()

def playMusic(name, loops = -1):
    """Should be loading *.mp3 files. By default it will keep looping.
        You can specify how many times you would like it to loop.
    """
    lps = loops
    mixer.music.stop()
    mixer.music.load(name)
    mixer.music.play(loops = lps)

def stopMusic():
    """Stops current song"""
    mixer.music.stop()
    
def pauseMusic():
    """Pauses current song"""
    mixer.music.pause()
    
def unpauseMusic():
    """Unpauses current song"""
    mixer.music.unpause()
    
def justClicked(btn=None):
    """
    Returns True if a mouse button was pressed during the last frame.
    
    Parameters:
    btn (None or int): The button to check.
        - None: check if any button was pressed
        - 0: left button
        - 1: middle button
        - 2: right button
    
    Returns:
    bool: True if specified button was just pressed, False otherwise
    """
    if btn is None:
        return any(clicked)
    else:
        return clicked[btn]

def mouseXY():
    """Returns the current position of the mouse as a tuple (x, y)."""
    return mouse.get_pos()

def mouseX():
    """Returns the current X position of the mouse."""
    return mouse.get_pos()[0]

def getMouse():
    """Returns the current (x, y) position of the mouse."""
    return mouse.get_pos()

def mouseY():
    """Returns the current Y position of the mouse."""
    return mouse.get_pos()[1]

def mouseL():
    """Returns True if the left mouse button is currently pressed."""
    return mouse.get_pressed()[0]

def mouseM():
    """Returns True if the middle mouse button is currently pressed."""
    return mouse.get_pressed()[1]

def mouseR():
    """Returns True if the right mouse button is currently pressed."""
    return mouse.get_pressed()[2]

def wheelUp():
    """Returns True if there was a mouse wheel up event."""
    return clicked[3]

def wheelDown():
    """Returns True if there was a mouse wheel up event."""
    return clicked[4]

def upKey():
    """Returns True if the "w" or up arrow is currently pressed."""
    keys = key.get_pressed()
    return keys[K_w] or keys[K_UP]

def rightKey():
    """Returns True if the "d" or right arrow is currently pressed."""
    keys = key.get_pressed()
    return keys[K_d] or keys[K_RIGHT]

def downKey():
    """Returns True if the "s" or down arrow is currently pressed."""
    keys = key.get_pressed()
    return keys[K_s] or keys[K_DOWN]

def leftKey():
    """Returns True if the "a" or left arrow is currently pressed."""
    keys = key.get_pressed()
    return keys[K_a] or keys[K_LEFT]

def spaceKey():
    """Returns True if the "a" or left arrow is currently pressed."""
    keys = key.get_pressed()
    return keys[K_SPACE]

def keyPressed(keycode):
    """Returns True the keycode is currently pressed. e.g. K_z
    see: https://www.pygame.org/docs/ref/key.html """
    keys = key.get_pressed()
    return keys[keycode]

def overlapsList(lst1, lst2):
    """Returns True if the two rectangles overlap."""
    r1 = Rect(lst1)
    r2 = Rect(lst2)
    return r1.colliderect(r2)

def overlaps(x1, y1, w1, h1, x2, y2, w2, h2):
    """Returns True if the two rectangles overlap."""
    r1 = Rect(x1, y1, w1, h1)
    r2 = Rect(x2, y2, w2, h2)
    return r1.colliderect(r2)

def loadImage(img, newWidth=0, newHeight=0):
    """Loads an image from a file."""
    #print(img, newWidth, newHeight)
    try:
        pic =  image.load(img)
    except:
        pic = Surface((10,10))
        pic.fill("beige")
    if newWidth==0 and newHeight==0:
        return pic
    wid, hei = pic.get_size()
    if newHeight == 0:
        ratio = newWidth / wid
        newHeight = hei * ratio
    elif newWidth == 0:
        ratio = newHeight / hei
        newWidth = wid * ratio
    #print(img, newWidth, newHeight)
    return transform.smoothscale(pic, (newWidth, newHeight))
        


def drawImage(img, x=0, y=0):
    """Draws an image at the specified (x, y) position."""
    screen.blit(img, (x, y))

def drawRectList(c, lst, t=0, corner=0, outline=0, alpha=255, outlineColour=0):
    drawRect(c, lst[0], lst[1], lst[2], lst[3], t, corner, outline, alpha, outlineColour)

def drawRect(c, x, y, width, height, t=0, corner=0, outline=0, alpha=255, outlineColour=0):
    """
    Draws a rectangle.
    
    Parameters:
    c: color
    x, y: top-left corner
    width, height: dimensions
    t: thickness (0 = filled)
    corner: corner radius (for rounded corners)
    """
    if alpha == 255:
        draw.rect(screen, c, (x, y, width, height), t, corner)
        if outline > 0:
            draw.rect(screen, outlineColour, (x, y, width, height), outline, corner)
    elif 0<alpha<255:
        surf = Surface((width, height)).convert()
        surf.set_alpha(alpha)
        surf.fill(c)
        screen.blit(surf, (x, y))

def drawLine(c, x, y, x2, y2, t=1):
    """Draws a line from (x, y) to (x2, y2) with thickness t."""
    draw.line(screen, c, (x, y), (x2, y2), t)

def drawText(c, txt, x, y, alpha = 255, align = "left", font = None):
    """Draws a text in current font at (x, y) in colour c.
        to draw in a custom font, pass font=("Trajan-regular.ttf", 45). """
    global fnt
    tmpFnt = fnt
    if font != None:
        f,s = font
        setFont(f, s)
    txtPic = fnt.render(txt, True, c)
    txtPic.set_alpha(alpha)
    if align == "right":
        ox = x
        x = ox - txtPic.get_width()
    screen.blit(txtPic,(x,y))
    fnt = tmpFnt


def setFont(name, size=24):
    """sets the font for drawing."""
    global fnt
    font_name = str(name)
    if font_name.lower() in ("trajan", "trajan-regular", "trajan-regular.ttf"):
        font_name = TRAJAN_REGULAR
    elif font_name.lower() in ("trajan-bold", "trajan-bold.otf"):
        font_name = TRAJAN_BOLD
    if (font_name, size) in allFonts:
        fnt = allFonts[(font_name, size)]
    else:
        try:
            if os.path.exists(font_name):
                fnt = font.Font(font_name, size)
            elif "." in font_name:
                candidate = os.path.join(os.path.dirname(__file__), font_name)
                if os.path.exists(candidate):
                    fnt = font.Font(candidate, size)
                else:
                    fnt = font.SysFont(font_name, size)
            else:
                fnt = font.SysFont(font_name, size)
            allFonts[(font_name, size)] = fnt
        except:
            print("invalid font")

def wait(n):
    display.flip()
    time.wait(n)

def drawArc(c, x, y, width, height, startAng, stopAng, t=0, outline=0, outlineColour=0):
    """Draws an oval (ellipse) inside the specified rectangle."""
    start = radians(startAng)
    stop = radians(stopAng)
    draw.arc(screen, c, (x, y, width, height), start, stop, t)
    if outline > 0:
        draw.ellipse(screen, outlineColour, (x, y, width, height),  start, stop, outline)

def quadratic_bezier(t, p0, p1, p2):
    """Calculate a point on a quadratic Bézier curve."""
    x = (1 - t)**2 * p0[0] + 2 * (1 - t) * t * p1[0] + t**2 * p2[0]
    y = (1 - t)**2 * p0[1] + 2 * (1 - t) * t * p1[1] + t**2 * p2[1]
    return (int(x), int(y))

def drawCurve(c, x1, y1, x2, y2, x3, y3, thickness=1, accuracy = 200):
    p0 = (x1, y1)
    p1 = (x2, y2)
    p2 = (x3, y3)   
    # Generate points along the Bézier curve
    curve_points = [quadratic_bezier(t / 200.0, p0, p1, p2) for t in range(201)]
    # Draw circles at each point on the curve
    for point in curve_points:
        draw.circle(screen, c, point, thickness)
        
def drawOval(c, x, y, width, height, t=0, outline=0, outlineColour=0):
    """Draws an oval (ellipse) inside the specified rectangle."""
    draw.ellipse(screen, c, (x, y, width, height), t)
    if outline > 0:
        draw.ellipse(screen, outlineColour, (x, y, width, height), outline)

def drawCircle(c, x, y, r, t=0, outline=0, outlineColour=0):
    """Draws a circle centered at (x, y) with radius r."""
    draw.circle(screen, c, (x, y), r, t)
    if outline > 0:
        draw.circle(screen, outlineColour, (x, y), r, outline)

def drawPoly(c, points, t=0, outline=0, outlineColour=0):
    """Draws a polygon using a list of point tuples."""
    draw.polygon(screen, c, points, t)
    if outline > 0:
        draw.polygon(screen, outlineColour, points, outline)

def drawTriangle(c, x1, y1, x2, y2, x3, y3, t=0, outline=0, outlineColour=0):
    """Draws a triangle using three points."""
    points = [(x1, y1), (x2, y2), (x3, y3)]
    draw.polygon(screen, c, points, t)
    if outline > 0:
        draw.polygon(screen, outlineColour, points, outline)

def drawTri(c, x1, y1, x2, y2, x3, y3, t=0, outline=0, outlineColour=0):
    """Draws a triangle using three points."""
    drawTriangle(c, x1, y1, x2, y2, x3, y3, t, outline, outlineColour)

def fill(c):
    """Fills the entire screen with the specified color."""
    screen.fill(c)

def background(c):
    """Fills the entire screen with the specified color."""
    screen.fill((c, c, c))

def resize(width, height):
    """Resizes the screen to the new width and height."""
    global screen
    screen = display.set_mode((width, height))

def frameRate(fps):
    """Sets the frame rate (frames per second)."""
    global FPS
    FPS = fps

def clickOnRect(x,y,w,h,btn=1):
    """returns true if the mouse is inside the rectangle given
       and the mouse button just went down. By default it check the left
       mouse button, but you can add 2 or 3 for the middle or right button.
       """
    if btn not in [1,2,3]:
        btn=1
    click = clicked[btn-1]
    mx,my = mouse.get_pos()
    return click and x <= mx <= x+w and y <= my <= y+h
    
def pressOnRect(x,y,w,h,btn=1):
    """returns true if the mouse is inside the rectangle given
       and the mouse button is down. By default it check the left mouse button,
       but you can add 2 or 3 for the middle or right button.
       """
    if btn not in [1,2,3]:
        btn=1
    click = mouse.get_pressed()[btn-1]
    mx,my = mouse.get_pos()
    return click and x <= mx <= x+w and y <= my <= y+h
    
def overRect(x,y,w,h):
    """returns true if the mouse is inside the rectangle given.
       """
    mx,my = mouse.get_pos()
    return x <= mx <= x+w and y <= my <= y+h
    

# only used by floodFill
def color_to_int(col):
    if isinstance(col, color.Color):
        color_obj = col
    elif isinstance(col, str):
        color_obj = Color(col)
    elif isinstance(col, tuple):
        color_obj = Color(col[0], col[1], col[2])
    elif isinstance(col, int):
        return col
    else:
        raise ValueError("Unsupported color format")

    # Convert RGB to integer
    return (color_obj.r << 16) + (color_obj.g << 8) + color_obj.b

def floodFill(fillColour, x, y):
    """ fills the colour fillColour starting at the point (x, y).
        changes all adjacent pixels of the same colour. """
    pxarray = PixelArray(screen)
    replaceColour = screen.get_at((x,y))
    fillColourN = color_to_int(fillColour) # pix array only uses numbers, so convert
    replaceColourN = color_to_int(replaceColour)
    
    if fillColourN == replaceColourN:return

    spots = set([(x,y)])
    while len(spots)>0:
        newSpots = set()
        for fx,fy in spots:
            if 0<fx<800 and 0<fy<600 and pxarray[fx,fy]==replaceColourN:
                pxarray[fx,fy]=fillColourN
                newSpots.add((fx+1,fy))
                newSpots.add((fx-1,fy))
                newSpots.add((fx,fy+1))
                newSpots.add((fx,fy-1))
        spots = newSpots

def drawBarriers(outline = 0, outlineColour=0, kind = "", debug=False):
    if kind == "":
        barrOfKind = barriers
    else:
        barrOfKind = [b for b in barriers if b.kind == kind]
    pos = 1
    for b in barrOfKind:
        if debug:
            b.draw(screen, outline, outlineColour, pos)
            pos += 1
        else:
            b.draw(screen, outline, outlineColour, -1)
            

def moveBarriers(dx, dy, kind = ""):
    if kind == "":
        barrOfKind = barriers
    else:
        barrOfKind = [b for b in barriers if b.kind == kind]
    
    for b in barrOfKind:
        b.move(dx, dy)

def addBarrier(x, y, w, h, colour = "black", kind = "wall", image=None, animation = None):
    b = Barrier(x, y, w, h, colour, kind, image, animation)
    barriers.append(b)

def clearBarriers(kind=None):
    global barriers
    if kind==None:
        barriers.clear()
    else:
        barriers = [b for b in barriers if b.kind != kind]
        
    
def removeBarrier(x, y, w, h):
    rem = None
    for b in barriers:
        if b.left == x and b.top == y and b.width == w and b.height ==h:
            rem = b
    if rem != None:
        barriers.remove(rem)

def hitBarrier(x, y, w, h, kind = "wall", debug = False):
    r = Rect(x, y, w, h)
    barrOfKind = [b for b in barriers if kind in b.kind.split(" ")]

    return r.collidelist(barrOfKind) > -1

def removeHitBarrier(x, y, w, h, kind = "wall"):
    r = Rect(x, y, w, h)
    barrOfKind = [b for b in barriers if b.kind == kind]
    hit = r.collidelist(barrOfKind)
    if hit > -1:
        barriers.remove(barrOfKind[hit])

def loadMask(img, colourKey = None):
    global maskImage
    maskImage = loadImage(img)
    if colourKey != None and type(colourKey) == dict:
        maskValues.update(colourKey)
    else:
        maskValues[color_to_int("white")] = "open"
    
def checkMask(x, y):
    if x < 0 or y < 0 or x >= maskImage.get_width() or y >= maskImage.get_height():
        return "wall"
    col = color_to_int(maskImage.get_at((x, y)))

    if col in maskValues:
        return maskValues[col]
    return "invalid"      
    
def running():
    """
    Updates the display, maintains the frame rate and handles events.
    
    Returns:
    bool: False if the user quits or presses ESC, True otherwise.
    """
    display.flip()
    myClock.tick(FPS)

    # Reset click tracking
    clicked[:] = [False] * 5

    # Exit if ESC key is pressed
    if key.get_pressed()[27]:
        quit()
        return False

    # Handle events
    for evnt in event.get():
        if evnt.type == MOUSEBUTTONDOWN:
            if evnt.button <= 5:
                clicked[evnt.button - 1] = True
        if evnt.type == QUIT:
            quit()
            return False
    return True
