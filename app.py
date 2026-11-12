from flask import Flask, request, jsonify
import requests
import tweepy
import os

app = Flask(__name__)

# Credentials (Render ke Environment Variables se load honge)
IG_USER_ID = os.environ.get("IG_USER_ID", "YOUR_IG_BUSINESS_ID")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "YOUR_FB_PAGE_ID")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "YOUR_META_TOKEN")

X_API_KEY = os.environ.get("X_API_KEY", "YOUR_X_API_KEY")
X_API_SECRET = os.environ.get("X_API_SECRET", "YOUR_X_API_SECRET")
X_ACCESS_TOKEN = os.environ.get("X_ACCESS_TOKEN", "YOUR_X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.environ.get("X_ACCESS_SECRET", "YOUR_X_ACCESS_SECRET")

LINKEDIN_ACCESS_TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN", "YOUR_LINKEDIN_TOKEN")
LINKEDIN_AUTHOR_URN = os.environ.get("LINKEDIN_AUTHOR_URN", "urn:li:person:YOUR_ID")


def download_image_from_drive(file_id):
    """Google Drive se image download karke temporary file banata hai"""
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    response = requests.get(url)
    response.raise_for_status()
    
    file_path = f"/tmp/{file_id}.jpg"
    with open(file_path, "wb") as f:
        f.write(response.content)
    return file_path, url


def post_instagram(image_url, caption):
    try:
        url = f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media"
        res = requests.post(url, data={
            "image_url": image_url,
            "caption": caption,
            "access_token": META_ACCESS_TOKEN
        }).json()
        
        if "id" in res:
            pub_res = requests.post(f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish", data={
                "creation_id": res["id"],
                "access_token": META_ACCESS_TOKEN
            }).json()
            return pub_res
        return res
    except Exception as e:
        return {"error": str(e)}


def post_facebook(image_url, caption):
    try:
        url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos"
        res = requests.post(url, data={
            "url": image_url,
            "message": caption,
            "access_token": META_ACCESS_TOKEN
        }).json()
        return res
    except Exception as e:
        return {"error": str(e)}


def post_twitter(local_image_path, caption):
    try:
        auth = tweepy.OAuth1UserHandler(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET)
        api_v1 = tweepy.API(auth)
        media = api_v1.media_upload(local_image_path)

        client_v2 = tweepy.Client(
            consumer_key=X_API_KEY, consumer_secret=X_API_SECRET,
            access_token=X_ACCESS_TOKEN, access_token_secret=X_ACCESS_SECRET
        )
        short_caption = caption[:275] + "..." if len(caption) > 280 else caption
        res = client_v2.create_tweet(text=short_caption, media_ids=[media.media_id])
        return {"status": "success", "id": res.data['id']}
    except Exception as e:
        return {"error": str(e)}


def post_linkedin(local_image_path, caption):
    try:
        headers = {
            "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        
        # 1. Register Upload
        reg_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
        reg_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": LINKEDIN_AUTHOR_URN,
                "serviceRelationships": [{"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}]
            }
        }
        reg_res = requests.post(reg_url, headers=headers, json=reg_payload).json()
        upload_url = reg_res['value']['uploadMechanism']['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']['uploadUrl']
        asset_urn = reg_res['value']['asset']

        # 2. Upload Image Binary
        with open(local_image_path, "rb") as img:
            requests.put(upload_url, headers={"Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}"}, data=img)

        # 3. Publish Post
        post_url = "https://api.linkedin.com/v2/ugcPosts"
        post_payload = {
            "author": LINKEDIN_AUTHOR_URN,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": caption},
                    "shareMediaCategory": "IMAGE",
                    "media": [{"status": "READY", "media": asset_urn}]
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
        }
        res = requests.post(post_url, headers=headers, json=post_payload).json()
        return res
    except Exception as e:
        return {"error": str(e)}


@app.route('/', methods=['GET'])
def health_check():
    return "Social Media Auto-Poster Server is Running!", 200


@app.route('/auto-post', methods=['POST'])
def auto_post():
    data = request.json
    file_id = data.get('fileId')
    caption = data.get('caption')

    if not file_id or not caption:
        return jsonify({"error": "fileId and caption are required"}), 400

    local_path, public_url = download_image_from_drive(file_id)

    results = {
        "instagram": post_instagram(public_url, caption),
        "facebook": post_facebook(public_url, caption),
        "twitter": post_twitter(local_path, caption),
        "linkedin": post_linkedin(local_path, caption)
    }

    if os.path.exists(local_path):
        os.remove(local_path)

    return jsonify({"status": "completed", "results": results}), 200


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)