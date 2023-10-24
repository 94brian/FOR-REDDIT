import os
import logging
import threading
import time
import random
from tkinter import Tk, filedialog, Button, Label, Entry, messagebox
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
import google_auth_oauthlib.flow
import googleapiclient.discovery
import hashlib
import re
import subprocess


# Global variable
youtube_service = None
QUOTA_EXCEEDED = False
THUMBNAIL_FOLDER = r"MY THUMB FOLDER"  # Update this path to the desired location on your system

# Setup logging
logging.basicConfig(filename=r'MY LOG FILE', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.info("Script started.")

# Mockup #
USE_MOCKUP = True
MOCKING_QUOTA_EXCEEDED = True
QUOTA_TIMER = 1 #In hours, or in minutes. Check QUOTA_TIMER_MINUTES
QUOTA_TIMER_MINUTES = 1 * 1 #Default 60 * 60


def load_titles_from_file(filename):
    with open(filename, 'r') as file:
        return [line.strip() for line in file.readlines()]

titles = load_titles_from_file(r'MY TITLES FILE')


def save_hash(file_path, hash_value):
    with open(r"MY HASHES FILE", 'a') as f:
        f.write(f"{file_path} - {hash_value}\n")


def extract_number_from_filename(filename):
    match = re.search(r'(\d+)', filename)
    return int(match.group(1)) if match else 0


def authenticate_and_set_service():
    global youtube_service
    if not youtube_service:
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
        api_service_name = "youtube"
        api_version = "v3"
        client_secrets_file = r"MY SUPER SECRET NUCLEAR CODE"  
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(client_secrets_file, ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"])
        credentials = flow.run_local_server(port=0)
        youtube_service = googleapiclient.discovery.build(api_service_name, api_version, credentials=credentials)


def get_authenticated_service():
    global youtube_service
    return youtube_service


def choose_directory():
    root.withdraw()  # Temporarily hide the main window
    folder_selected = filedialog.askdirectory()
    root.deiconify()  # Restore the main window
    return folder_selected


def upload_video_mock(video_path, title, description, tags):
    # Simulating random success and failure for testing purposes
    success = random.choice([True, True, True, False])  # 75% chance of success
    if success:
        video_id = hashlib.md5(video_path.encode()).hexdigest()[:11]  # Generating a dummy video ID
        print(f"Mock: Video {video_id} has been uploaded.")
        logging.info(f"Mock: Video {video_id} has been uploaded.")
        return True
    else:
        error_msg = random.choice(["Some random error.", "Daily quota exceeded."])
        print(f"Mock: {error_msg}")
        logging.error(f"Mock: {error_msg}")
        if "quota" in error_msg:
            global QUOTA_EXCEEDED
            QUOTA_EXCEEDED = MOCKING_QUOTA_EXCEEDED
        return False


def upload_video(video_path, title, description, tags):
    if USE_MOCKUP:
        return upload_video_mock(video_path, title, description, tags)

    youtube = get_authenticated_service()

    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags,
            'categoryId': '22'
        },
        'status': {
            'privacyStatus': 'private'
        }
    }

    insert_request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True)
    )

    try:
        video_response = insert_request.execute()
        logging.info(f"Video {video_response['id']} has been uploaded.")
        
        
        return True
    except HttpError as e:
        error_content = e.content.decode('utf-8')
        logging.error(f"An HTTP error {e.resp.status} occurred: {error_content}")

        if "quota" in error_content.lower():
            messagebox.showwarning("Quota Exceeded", "You have hit your daily quota limit. Please try again tomorrow.")
            global QUOTA_EXCEEDED
            QUOTA_EXCEEDED = True

        return False


def threaded_start_upload():
    authenticate_and_set_service()  # Authenticate the user before starting the upload thread
    threading.Thread(target=start_upload).start()


def partial_hash(file_path, mb_to_hash=5):
    """Compute a SHA-256 hash of the first few megabytes of the given file."""
    sha256_hash = hashlib.sha256()
    mb_size = 1024 * 1024
    with open(file_path, 'rb') as f:
        byte_block = f.read(mb_to_hash * mb_size)
        sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def hash_exists(file_path, hash_value):
    try:
        with open(r"MY HASHES FILE", 'r') as f:
            lines = f.readlines()
            for line in lines:
                path, stored_hash = line.strip().split(" - ")
                if path == file_path and stored_hash == hash_value:
                    return True
    except FileNotFoundError:
        return False
    return False


def start_upload():
    videos_folder = directory_entry.get()
    valid_video_extensions = ['.mp4', '.avi', '.mov']

    default_title = random.choice(titles)
    default_description = "Test Video Description"
    default_tags = ["tag11", "tag222", "tag333"]

    for video in sorted(os.listdir(videos_folder), key=extract_number_from_filename):
        # Check for valid video extensions
        if not any(video.endswith(ext) for ext in valid_video_extensions):
            continue

        video_path = os.path.join(videos_folder, video)
        computed_hash = partial_hash(video_path)

        if hash_exists(video_path, computed_hash):
            print(f"{video_path} has already been uploaded. Skipping.")
            logging.info(f"{video_path} has already been uploaded. Skipping.")
            continue
        
        # If the hash does not exist, attempt to upload
        retries = 10
        for _ in range(retries):
            upload_success = upload_video(video_path, default_title, default_description, default_tags)
            
            # Generate and set thumbnail for both mockup and non-mockup
            thumbnail_path = generate_thumbnail(video_path)
            if thumbnail_path and not USE_MOCKUP:
                youtube = get_authenticated_service()
                youtube.thumbnails().set(                    
                    videoId=video_response['id'], #I ALSO COULDN"T FIGURE OUT WHAT IS WRONG WITH THIS
                    media_body=MediaFileUpload(thumbnail_path, chunksize=-1, resumable=True)
                ).execute()

            if upload_success:
                break
            if QUOTA_EXCEEDED:
                message = f"Quota exceeded for the day. Waiting for {QUOTA_TIMER} hours before next upload attempt."
                print(message)
                logging.info(message)
                time.sleep(QUOTA_TIMER * QUOTA_TIMER_MINUTES)
            else:
                print(f"Retry {_ + 1} for {video_path}")
                logging.info(f"Retry {_ + 1} for {video_path}")
                time.sleep(2)

        # If the video was successfully uploaded, save its hash
        if upload_success:
            save_hash(video_path, computed_hash)
        else:
            print(f"Failed to upload {video_path}.")
            logging.error(f"Failed to upload {video_path}.")


def generate_thumbnail(video_path):
    # Extract the filename from the video_path and add the '_thumbnail.jpg' suffix
    thumbnail_name = os.path.basename(video_path).replace('.mp4', '_thumbnail.jpg')
    
    # Join the THUMBNAIL_FOLDER constant with the thumbnail_name to get the full path
    thumbnail_path = os.path.join(THUMBNAIL_FOLDER, thumbnail_name)
    
    cmd = [
        '"C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe"', 
        '-i', 
        f'"{video_path}"', 
        '-ss', 
        '00:00:10',   # 5 seconds into the video
        '-vframes', 
        '1', 
        '-vf', 
        'scale=1280:-1', 
        f'"{thumbnail_path}"'
    ]
    
    try:
        subprocess.check_output(' '.join(cmd), stderr=subprocess.STDOUT, shell=True)
        return thumbnail_path
    except subprocess.CalledProcessError as e:
        logging.error(f"Error generating thumbnail for {video_path}. Error: {str(e)}")
        return None


def set_video_thumbnail(video_id, thumbnail_path):
    youtube = get_authenticated_service()
    media = MediaFileUpload(thumbnail_path, mimetype='image/jpeg', chunksize=-1, resumable=True)
    request = youtube.thumbnails().set(videoId=video_id, media_body=media)
    response = request.execute()
    return response


root = Tk()
root.title("Bulk Video Uploader")

Label(root, text="Select Source Videos Folder").pack(pady=20)
directory_entry = Entry(root, width=50)
directory_entry.pack(padx=20, pady=5)

choose_button = Button(root, text="Choose Folder", command=lambda: directory_entry.insert(0, choose_directory()))
choose_button.pack(pady=20)

upload_button = Button(root, text="Start Upload", command=threaded_start_upload)
upload_button.pack(pady=20)

root.mainloop()
