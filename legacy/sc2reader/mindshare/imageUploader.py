import os

import requests
import json


def _require_uploads_enabled():
    # CR-003: uploads to the media API are off unless MS_UPLOADS_ENABLED=1 is set explicitly.
    if os.environ.get("MS_UPLOADS_ENABLED") != "1":
        raise RuntimeError("Mindshare media uploads are disabled (set MS_UPLOADS_ENABLED=1 to enable)")


class ImageUploader():

    RESOURCE_URL = "https://media.api.mindshareapp.com/media/resource"
    SERVER_URL = "https://media.api.mindshareapp.com/media"
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

        _require_uploads_enabled()
        response = requests.post(self.SERVER_URL, files=files)
        id = json.loads(response.content.decode('utf-8')).get("_id")
        return {"id" : id, "status" : response.status_code}

    def readImage(self, image_id):
        _require_uploads_enabled()
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

        _require_uploads_enabled()
        response = requests.put(f"{self.SERVER_URL}/{image_id}", files=files)
        return {"status": response.status_code, "content": response.content.decode('utf-8')}

    def deleteImage(self, image_id):
        _require_uploads_enabled()
        response = requests.delete(f"{self.SERVER_URL}/{image_id}")
        return {"status": response.status_code, "content": response.content.decode('utf-8')}


if __name__ == "__main__":
    
    iu = ImageUploader()
    res = iu.readImage("66943f0dfca2b4001510f7c7")

    print(res)
