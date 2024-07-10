import requests

class ImageUploader():

    SERVER_URL = "https://media.api.mindshare.touch4dev.net/media/resource/"

    def __init__(self) -> None:
        pass

    def uploadImage(self, imageUrl, imageName): 
        return {"id":"fakeID","status":201}




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

    print(response.status_code)
    print(response.text)
    pass