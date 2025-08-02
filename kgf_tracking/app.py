from flask import Flask, render_template, request, jsonify
import os
from bs4 import BeautifulSoup
from collections import Counter
import logging

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

IGNORED_USERNAMES = ["@Babymishra_", "@Berlinjaat", "@deep_struggle", "@KGF_CHAPTER_2", "@JK_17b",
                     "@ismailzawar22", "@ea_fcmobile_", "@Mona_Sona_Hona", "@anokhelaala",
                     "@Atulya_Bharat1", "@bbishnoimukesh_", "@ExSeculr", "@Mr_Nobody_das",
                     "@iemnic", "@SAHILBERWALJi"]

BACKUP_MAPPING = {
    "@user1": "@user1_backup",
    "@user2": "@user2_alt",
}

@app.route("/", methods=["GET"])
def index():
    logger.debug("Rendering index with upload view")
    return render_template("index.html", view="upload", error=None)

@app.route("/upload_main", methods=["POST"])
def upload_main_tweet():
    try:
        main_file = request.files.get('main_tweet')
        if not main_file or not main_file.filename:
            logger.warning("No main tweet file provided")
            return render_template("index.html", view="upload", error="Please provide a main tweet HTML file!")

        all_usernames = extract_usernames_from_file(main_file)
        logger.debug(f"Extracted usernames from main tweet: {all_usernames}")

        all_usernames = [
            name for name in all_usernames
            if name.strip() and name.startswith('@') and name.lower() not in [u.lower() for u in IGNORED_USERNAMES]
        ]

        duplicates = Counter(all_usernames)
        unique_usernames = sorted({name for name, count in duplicates.items() if count == 1})
        duplicate_names = {name: count for name, count in duplicates.items() if count > 1}

        numbered_unique_usernames = [f"{i + 1}. {name}" for i, name in enumerate(unique_usernames)]
        duplicate_list = [f"{i + 1}. {name} ({count} times)" for i, (name, count) in enumerate(duplicate_names.items())]

        logger.debug(f"Unique usernames: {unique_usernames}")
        logger.debug(f"Duplicate usernames: {duplicate_names}")

        return render_template(
            "index.html",
            view="track_tweets",
            unique_usernames=numbered_unique_usernames,
            duplicate_list=duplicate_list,
            total_count=len(unique_usernames),
            error=None
        )
    except Exception as e:
        logger.error(f"Error in upload_main_tweet: {str(e)}")
        return render_template("index.html", view="error", error=f"An error occurred: {e}")

@app.route("/select_tracking", methods=["POST"])
def select_tracking():
    try:
        unique_usernames = request.form.getlist("unique_usernames")
        num_tweets = int(request.form.get("num_tweets"))
        logger.debug(f"Selected usernames for tracking: {unique_usernames}")
        logger.debug(f"Number of tweets to track: {num_tweets}")
        return render_template(
            "index.html",
            view="upload_tracking",
            unique_usernames=unique_usernames,
            num_tweets=num_tweets,
            error=None
        )
    except Exception as e:
        logger.error(f"Error in select_tracking: {str(e)}")
        return render_template("index.html", view="error", error=f"An error occurred: {e}")

@app.route("/process_tracking", methods=["POST"])
def process_tracking():
    try:
        num_tweets = int(request.form.get("num_tweets"))
        unique_usernames = [
            name.split(". ", 1)[1]
            for name in request.form.getlist("unique_usernames")
            if name.split(". ", 1)[1].lower() not in [u.lower() for u in IGNORED_USERNAMES]
        ]

        logger.debug(f"Unique usernames to track: {unique_usernames}")
        logger.debug(f"Number of tracking tweets: {num_tweets}")

        username_occurrences = Counter()
        for i in range(1, num_tweets + 1):
            tracking_file = request.files.get(f"tracking_file_{i}")
            if not tracking_file or not tracking_file.filename:
                logger.warning(f"No valid HTML file provided for tracking file {i}")
                continue

            logger.debug(f"Processing tracking file {i}: {tracking_file.filename}")
            tracking_usernames = extract_usernames_from_file(tracking_file)
            logger.debug(f"Extracted usernames from tracking {i}: {tracking_usernames}")

            tracking_usernames = [name.lower() for name in tracking_usernames if name.lower() not in [u.lower() for u in IGNORED_USERNAMES]]
            username_occurrences.update(tracking_usernames)

        logger.debug(f"Username occurrences: {dict(username_occurrences)}")

        grouped_missing = {count: [] for count in range(num_tweets, 0, -1)}
        for username in unique_usernames:
            main_username_lower = username.lower()
            backup_username = BACKUP_MAPPING.get(username, None)
            backup_username_lower = backup_username.lower() if backup_username else None

            occurrences = username_occurrences[main_username_lower]
            if backup_username_lower:
                occurrences += username_occurrences[backup_username_lower]

            missing_count = num_tweets - occurrences
            if missing_count > 0:
                display_name = f"{username} ({backup_username})" if backup_username else username
                grouped_missing[missing_count].append(display_name)

        for count, usernames in grouped_missing.items():
            grouped_missing[count] = [f"{i + 1}. {username}" for i, username in enumerate(usernames)]

        logger.debug(f"Grouped missing: {grouped_missing}")

        return render_template(
            "index.html",
            view="result",
            grouped_missing=grouped_missing,
            error=None
        )

    except Exception as e:
        logger.error(f"Error in process_tracking: {str(e)}")
        return render_template("index.html", view="error", error=f"An error occurred: {e}")

def extract_usernames_from_file(file):
    usernames = []
    try:
        file.seek(0)
        soup = BeautifulSoup(file.read(), 'html.parser')
        for element in soup.find_all(True):
            text = element.get_text(strip=True)
            if text and text.startswith('@'):
                usernames.append(text)
        for text in soup.stripped_strings:
            if text.startswith('@'):
                if text not in usernames:
                    usernames.append(text)
        logger.debug(f"Extracted {len(usernames)} usernames from file: {usernames}")
    except Exception as e:
        logger.error(f"Error while extracting usernames from file: {e}")
    return usernames

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return render_template("index.html", view="error", error=str(error))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)