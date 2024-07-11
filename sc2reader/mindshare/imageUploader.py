import requests
import json

class ImageUploader():

    RESOURCE_URL = "https://media.api.mindshare.touch4dev.net/media/resource/"
    SERVER_URL = "https://media.api.mindshare.touch4dev.net/media"
    SCREENSHOT_WIDTH = "2558"
    SCREENSHOT_HEIGHT = "1598"

    def __init__(self) -> None:
        pass

    def uploadImage(self, imageFolder, imageName): 
        
        files = {
            'type': (None, 'node.images'),
            'file': (imageName, open("{}/{}".format(imageFolder, imageName), 'rb'), 'image/png'),
            'meta.width': (None, self.SCREENSHOT_WIDTH),
            'meta.height': (None, self.SCREENSHOT_HEIGHT)
        }

        response = requests.post(self.SERVER_URL, files=files)
        id = json.loads(response.content.decode('utf-8')).get("_id")
        return {"id" : id, "status" : response.status_code}


if __name__ == "__main__":
    url = 'https://media.api.mindshare.touch4dev.net/media'
    file_path = 'C:/Users/Štefan/Downloads/image.png'

    files = {
        'type': (None, 'node.images'),
        'file': ('image.png', open(file_path, 'rb'), 'image/png'),
        'meta.width': (None, '50'),
        'meta.height': (None, '25')
    }
    
    response = requests.post(url, files=files)

    print(response)
