from flask import Flask, request, jsonify
import json
import logging
import os
from slack_sdk import WebClient
import urllib.parse
from main import fetch_moving_averages, analyze_videos


app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO)

SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')

slack_client = WebClient(token=SLACK_BOT_TOKEN)

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




@app.route('/slack/actions', methods=['POST'])
def slack_actions():
    encoded_payload = request.get_data(as_text=True)
    decoded_payload = urllib.parse.unquote(encoded_payload)
    payload_str = decoded_payload.split("payload=")[1]
    payload_dict = json.loads(payload_str)
    trigger_id = payload_dict['trigger_id']
    try:
        response = slack_client.views_open(
            trigger_id=trigger_id, 
            view={
                "type": "modal",
                "title": {
                    "type": "plain_text",
                    "text": "Details"
                },
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": " "
                        }
                    }
                ]
            }
        )

        if not response["ok"]:
            raise ValueError(f"Failed to open modal: {response['error']}")

        return "", 200 
    except Exception as e:
        print(e)
        return "Internal Server Error", 500


@app.route('/slack/notifications', methods=['GET'])
def slack_actions():
    df_moving_averages = fetch_moving_averages()
    if df_moving_averages is not None and not df_moving_averages.empty:
        analyze_videos(df_moving_averages)
        return jsonify({'status': 'Notification sent'})

    else:
        return jsonify({'status': 'No moving averages found to analyze'})


if __name__ == '__main__':
    app.run(debug=True, port=8080)


