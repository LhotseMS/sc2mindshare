import os
from PIL import Image, ImageDraw, ImageFont

# Constants
FONT_PATH = "C:/Windows/Fonts/AGENCYB.TTF"
FONT_SIZE = 40
OUTPUT_DIR = "C:/MS SC/ClockImages"
BACKGROUND_COLOR = (237, 240, 249)  # Transparent background
TEXT_COLOR = (105, 105, 105)  # Dark gray text

def create_time_image(time_str, output_path, width):
    # Create font object
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    
    # Create a dummy image to get text size
    dummy_img = Image.new("RGBA", (1, 1), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(dummy_img)
    text_bbox = draw.textbbox((10, 0), time_str, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    # Create final image with appropriate size
    img = Image.new("RGBA", (width, 48), BACKGROUND_COLOR)
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

if __name__ == "__main__":
    generate_clock_images()