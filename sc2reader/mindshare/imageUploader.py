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

    def readImage(self, image_id):
        response = requests.get(f"{self.RESOURCE_URL}{image_id}")
        if response.status_code == 200:
            return response.content
        else:
            return {"status": response.status_code, "error": response.content.decode('utf-8')}

    def updateImage(self, image_id, imageFolder, imageName): 
        files = {
            'type': (None, 'node.images'),
            'file': (imageName, open("{}/{}".format(imageFolder, imageName), 'rb'), 'image/png'),
            'meta.width': (None, self.SCREENSHOT_WIDTH),
            'meta.height': (None, self.SCREENSHOT_HEIGHT)
        }

        response = requests.put(f"{self.SERVER_URL}/{image_id}", files=files)
        return {"status": response.status_code, "content": response.content.decode('utf-8')}

    def deleteImage(self, image_id):
        response = requests.delete(f"{self.SERVER_URL}/{image_id}")
        return {"status": response.status_code, "content": response.content.decode('utf-8')}




if __name__ == "__main__":
    
    iu = ImageUploader()
    res = iu.readImage("66943f0dfca2b4001510f7c7")

    print(res)
