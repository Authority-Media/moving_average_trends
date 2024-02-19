from flask import Flask, request, jsonify
import json
import logging

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO)

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

if __name__ == '__main__':
    app.run(debug=True, port=8080)


