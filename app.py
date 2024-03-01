from flask import Flask, request, jsonify
import json
import logging
import os
from slack_sdk import WebClient
import psycopg2
from main import fetch_moving_averages, analyze_videos

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO)

SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')

slack_client = WebClient(token=SLACK_BOT_TOKEN)


db_params = {
    'database': os.environ.get('DB_NAME'),
    'user': os.environ.get('DB_USER'),
    'password': os.environ.get('DB_PASS'),
    'host': os.environ.get('DB_HOST'),
    'port': os.environ.get('DB_PORT')
}

@app.route('/slack/interactivity-endpoint', methods=['POST'])
def interactivity_endpoint():
    # Slack sends interaction data as a JSON string in the 'payload' form field
    interaction_data = json.loads(request.form.get('payload', '{}'))
    
    # Log the interaction data
    logging.info(f"Received interaction: {interaction_data}")

    # Acknowledge the interaction with an empty JSON body
    return jsonify({})


@app.route('/error-logging', methods=['POST'])
def error_logging():
    error_data = request.json  # Assuming error details are sent as a JSON payload
    logging.error(f"Error logged: {error_data}")
    # Here, you could add the error to a monitoring system or a database
    return jsonify({'status': 'Error Received'})

@app.route('/alert-sent', methods=['POST'])
def alert_sent():
    # This is a simple logging endpoint for when main.py sends an alert
    data = request.json  # Assuming main.py sends a JSON payload
    logging.info(f"Alert sent: {data}")
    return jsonify({'status': 'Received'})



def get_top_comments(video_url):
    # Execute SQL query to fetch top 5 comments for the given video URL
    conn = psycopg2.connect(**db_params)
    cursor = conn.cursor()
    query = f"""
    SELECT * 
    FROM comments 
    WHERE video_url = '{video_url}'
    ORDER BY likes DESC
    LIMIT 5;
    """
    cursor.execute(query)
    results = cursor.fetchall()    
    return results

@app.route('/slack/actions', methods=['POST'])
def slack_actions():
    try:
        payload = json.loads(request.form.get('payload'))
        video_link = payload['original_message']['attachments'][1]['title_link']
        youtube_thumbnail = f"https://img.youtube.com/vi/{get_video_id(video_link)}/0.jpg"
        additional_image = payload['original_message']['attachments'][1]['image_url']
        comments = get_top_comments(video_link)

        # Create a list to store blocks for the modal
        modal_blocks = [
            {
                "type": "image",
                "title": {
                    "type": "plain_text",
                    "text": "YouTube Video"
                },
                "image_url": youtube_thumbnail,
                "alt_text": "YouTube Video"
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"<{video_link}|Watch on YouTube>"
                    }
                ]
            }
        ]

        # Add the image section before the comments
        image_section = {
            "type": "image",
            "title": {
                "type": "plain_text",
                "text": "Chart"
            },
            "image_url": additional_image,
            "alt_text": ""
        }
        modal_blocks.append(image_section)

        # Add comments section after the image
        # Create a header row for the table
        table_header = {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": "*COMMENTS*"},
                {"type": "mrkdwn", "text": "*LIKES*"},
            ]
        }
        modal_blocks.append(table_header)

        # Add divider after the headings
        divider_block = {"type": "divider"}
        modal_blocks.append(divider_block)

        # Add comments as rows in the table with numbering
        for index, comment in enumerate(comments, start=1):
            comment_text = comment[3]
            likes = comment[5]
            comment_row = {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"{index}. {comment_text}"},
                    {"type": "mrkdwn", "text": str(likes)},
                ]
            }
            modal_blocks.append(comment_row)
        response = slack_client.views_open(
            trigger_id=payload['trigger_id'],
            view={
                "type": "modal",
                "title": {
                    "type": "plain_text",
                    "text": "Details"
                },
                "blocks": modal_blocks,
                "private_metadata": "abc123"  # Add private_metadata as needed
            },
            hash="modal_css",  # Specify an identifier for CSS
            css="div.p-modal__content { max-width: 800px !important; }"  # Define CSS styles for the modal
        )

        if not response["ok"]:
            raise ValueError(f"Failed to open modal: {response['error']}")

        return "", 200
    except Exception as e:
        print(e)
        return "Internal Server Error", 500



def get_video_id(video_link):
    """
    Extracts the YouTube video ID from the video link.
    """
    # Assuming the video link is a standard YouTube link
    return video_link.split('v=')[-1]


@app.route('/slack/notifications', methods=['GET'])
def send_notifications():
    df_moving_averages = fetch_moving_averages()
    if df_moving_averages is not None and not df_moving_averages.empty:
        analyze_videos(df_moving_averages)
        return jsonify({'status': 'Notification sent'})

    else:
        return jsonify({'status': 'No moving averages found to analyze'})

if __name__ == '__main__':
    app.run(debug=True, port=8080)