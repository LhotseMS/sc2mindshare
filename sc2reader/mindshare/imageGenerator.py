import os
from sc2reader.resources import Map, MapInfo
from PIL import Image, ImageDraw, ImageFont

# Constants
FONT_PATH = "C:/Windows/Fonts/AGENCYB.TTF"
CLOCK_FONT_SIZE = 40
OUTPUT_DIR = "C:/MS SC/ClockImages"
CLOCK_BACKGROUND_COLOR = (237, 240, 249) 
TEXT_COLOR = (105, 105, 105)  # Dark gray text

P2_FONT_SIZE = 500
P2_BACKGROUND_COLOR = (0, 0, 0)  

def create_time_image(time_str, output_path, width):
    # Create font object
    font = ImageFont.truetype(FONT_PATH, CLOCK_FONT_SIZE)
    
    # Create a dummy image to get text size
    dummy_img = Image.new("RGBA", (1, 1), CLOCK_BACKGROUND_COLOR)
    draw = ImageDraw.Draw(dummy_img)
    
    # Create final image with appropriate size
    img = Image.new("RGBA", (width, 48), CLOCK_BACKGROUND_COLOR)
    draw = ImageDraw.Draw(img)
    draw.text((8, 0), time_str, font=font, fill=TEXT_COLOR)
    
    # Save the image
    img.save(output_path)

def format_time(hours, minutes, seconds):
    if hours > 0:
        return f"{hours}:{minutes:02}:{seconds:02}"
    else:
        return f"{minutes}:{seconds:02}"

def generate_clock_images():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    for minutes in range(60, 80):  # Loop from 0 to 30 minutes
        for seconds in range(0, 60, 10):
            time_str = format_time(0, minutes, seconds)
            file_name = time_str.replace(":", "-") + ".png"
            output_path = os.path.join(OUTPUT_DIR, file_name)
            
            width = 80
            if minutes > 19:
                width = 100

            create_time_image(time_str, output_path, width)

def generatePlayer2Image():
    # Create font object
    font = ImageFont.truetype(FONT_PATH, P2_FONT_SIZE)
    
    # Create a dummy image to get text size
    dummy_img = Image.new("RGBA", (1, 1), P2_BACKGROUND_COLOR)
    draw = ImageDraw.Draw(dummy_img)
    
    # Create final image with appropriate size
    img = Image.new("RGBA", (2558, 1598), P2_BACKGROUND_COLOR)
    draw = ImageDraw.Draw(img)
    draw.text((560, 460), "Player 2", font=font, fill=CLOCK_BACKGROUND_COLOR)
    
    # Save the image
    img.save(OUTPUT_DIR + "/" + "player2BattleImageDivider.png")

def generateBattleHeatMap(map : Map, input_image_path, output_image_path, playersCoordinates, circle_radius=15, circle_color=(255, 0, 0)):

    mapName = input_image_path.split("/")[-1]
    mapInfos = {
        "Alcyone LE.jpg": {
            "fileHeight" : 1400,
            "filewidth" : 1400
        },
        "Amphion LE.jpg": {
            "fileHeight" : 2000,
            "filewidth" : 2000
        },
        "Crimson Court LE.jpg": {
            "fileHeight" : 2387,
            "filewidth" : 2000
        },
        "Dynasty LE.jpg": {
            "fileHeight" : 1527,
            "filewidth" : 2000
        },
        "Ghost River LE.jpg": {
            "fileHeight" : 1280,
            "filewidth" : 1480
        },
        "Goldenaura LE.jpg": {
            "fileHeight" : 1000,
            "filewidth" : 1000
        },
        "Oceanborn LE.jpg": {
            "fileHeight" : 943,
            "filewidth" : 1000
        },
        "Post-Youth LE.jpg": {
            "fileHeight" : 941,
            "filewidth" : 758
        },
        "Site Delta LE.jpg": {
            "fileHeight" : 1088,
            "filewidth" : 1000
        }
    }

    playableMapHeight = map.map_info.height - map.map_info.camera_bottom - (map.map_info.height - map.map_info.camera_top)
    playableMapWidth = map.map_info.width - map.map_info.camera_left - (map.map_info.width - map.map_info.camera_right)

    vCoef = mapInfos[mapName]["fileHeight"] / playableMapHeight
    hCoef = mapInfos[mapName]["filewidth"] / playableMapWidth
    mapSizeCoef = max(mapInfos[mapName]["fileHeight"] ,mapInfos[mapName]["filewidth"]) / 1000
    borderWidth = round(4*mapSizeCoef)

    # Open the existing image
    image = Image.open(input_image_path)
    draw = ImageDraw.Draw(image)

    # Draw circles at the specified coordinates
    for player, coordinates in playersCoordinates.items():
        color = (player.color.r, player.color.g, player.color.b)

        for (x, y, s, isb) in coordinates:

            x1 = (x - map.map_info.camera_left) * hCoef
            y1 = (playableMapHeight - (y - map.map_info.camera_bottom)) * vCoef
                
            if isb:
                
                sqSize = round(20 * mapSizeCoef)
                rect_coords = (x1 - sqSize, y1 - sqSize, x1 + sqSize, y1 + sqSize)
                draw.rectangle(rect_coords, outline=color, fill=(255,255,255), width=borderWidth)
            else:
                if s <= 1:
                    circle_radius = 10
                elif s <= 2:
                    circle_radius = 14
                elif s <= 3:
                    circle_radius = 18
                else:
                    circle_radius = 22

                circle_radius = round(circle_radius * mapSizeCoef)

                #image coordinate system is 0.0 left bottom, SC is left top

                left_up_point = (x1 - circle_radius, 
                                y1 - circle_radius)
                right_down_point = (x1 + circle_radius, 
                                    y1 + circle_radius)
                draw.ellipse([left_up_point, right_down_point], 
                            outline=color, fill=(255,255,255), width=borderWidth)
            

    # Save the result as a new file
    image.save(output_image_path)
    print(f"Image saved to {output_image_path}")

if __name__ == "__main__":
    #generate_clock_images()
    #generatePlayer2Image()
    coordinates = [(50, 50), (100, 100), (150, 150)]  # Example coordinates
    circle_radius = 10
    circle_color = (0, 255, 0)  # Green color
    generateBattleHeatMap("","",coordinates)