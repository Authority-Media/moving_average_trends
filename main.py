import psycopg2
import pandas as pd
import matplotlib
matplotlib.use('Agg')
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import matplotlib.font_manager as fm
import base64
import os
from dotenv import load_dotenv
import requests
from io import BytesIO
import boto3
from botocore.exceptions import NoCredentialsError
import matplotlib.pyplot as plt
import datetime





load_dotenv()

# Database connection parameters using environment variables
db_params = {
    'database': os.environ.get('DB_NAME'),
    'user': os.environ.get('DB_USER'),
    'password': os.environ.get('DB_PASS'),
    'host': os.environ.get('DB_HOST'),
    'port': os.environ.get('DB_PORT')
}

# Slack webhook URL using an environment variable
slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL')

SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')

def alert_already_sent(cursor, video_id, trend_status):
    # Check if an alert with the same trend status has already been sent for this video_id
    query = '''
    SELECT 1 FROM current_trending_videos
    WHERE video_id = %s AND trend_status = %s;
    '''
    cursor.execute(query, (video_id, trend_status))
    return cursor.fetchone() is not None

def get_video_url(video_id):
    # Connect to the database and fetch the video URL
    try:
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()
        query = 'SELECT video_url FROM videos WHERE video_id = %s'
        cursor.execute(query, (video_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        print(f"An error occurred while fetching the video URL: {e}")
    finally:
        if conn:
            cursor.close()
            conn.close()


def update_trending_videos(trending_videos):
    try:
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()
        # Insert new trending videos
        insert_query = 'INSERT INTO current_trending_videos (video_id) VALUES (%s) ON CONFLICT DO NOTHING'
        # Remove videos that are no longer trending
        remove_query = 'DELETE FROM current_trending_videos WHERE video_id NOT IN %s'
        trending_video_ids = tuple(
            [video_id for video_id, _ in trending_videos])

        cursor.executemany(insert_query, [(video_id,)
                           for video_id in trending_video_ids])
        cursor.execute(remove_query, (trending_video_ids,))

        conn.commit()
    except Exception as e:
        print(f"An error occurred while updating current trending videos: {e}")
    finally:
        if conn:
            cursor.close()
            conn.close()


def fetch_moving_averages():
    print("Fetching moving averages from the database...")
    try:
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()
        query = '''
        SELECT video_title, video_id, date, moving_average
        FROM video_view_statistics
        ORDER BY video_id, date DESC
        '''
        cursor.execute(query)
        results = cursor.fetchall()
        df = pd.DataFrame(results, columns=[
                          'video_title', 'video_id', 'date', 'moving_average'])
        return df
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            cursor.close()
            conn.close()
    print("Finished fetching moving averages.")

def update_trending_videos_database(trending_videos):
    # Add or update entries in current_trending_videos table
    # This function should be called after sending Slack alerts
    for video_id, group, trend_status in trending_videos:
        current_moving_average = group['moving_average'].values[-1]
        update_previous_moving_average(video_id, current_moving_average)


def is_trending(group, min_increase_percentage=15):
    # Assuming 'group' is already sorted by date in ascending order
    moving_averages = group['moving_average'].values
    if len(moving_averages) < 6:
        return False  # Not enough data to determine a trend

    # Instead of taking the entire start and end average, we look at the last 5 days specifically
    start_average = moving_averages[-6]  # 6 days ago
    end_average = moving_averages[-1]    # most recent day

    # Calculate the percentage increase from 6 days ago to the most recent day
    percentage_increase = ((end_average - start_average) / start_average) * 100

    # Check if the increase is consistent over the last 5 days
    is_consistently_increasing = all(moving_averages[i] < moving_averages[i + 1] for i in range(-6, -1))

    # Only return True if the increase is both above the minimum threshold and consistent
    return percentage_increase >= min_increase_percentage and is_consistently_increasing


def analyze_video(group):
    video_id = group['video_id'].iloc[0]
    if is_trending(group):
        last_moving_average = get_last_moving_average(video_id)
        current_moving_average = group['moving_average'].iloc[-1]

        if last_moving_average is None:
            return video_id, group, 'new'
        elif current_moving_average > last_moving_average:
            return video_id, group, 'up'
        elif current_moving_average < last_moving_average:
            return video_id, group, 'down'
    return None

def analyze_videos(df):
    print("Analyzing videos for trending patterns...")
    trending_videos = []

    # Establish database connection
    conn = psycopg2.connect(**db_params)
    cursor = conn.cursor()

    # Initialize the progress bar
    pbar = tqdm(total=len(df['video_id'].unique()), desc="Analyzing Videos", unit="video")
    for video_id, group in df.groupby('video_id'):
        group_sorted = group.sort_values(by='date', ascending=True)
        
        # Determine trend_status before checking if alert was already sent
        trend_status_result = analyze_video(group_sorted)
        if trend_status_result:
            video_id, group, trend_status = trend_status_result
            if alert_already_sent(cursor, video_id, trend_status):
                print(f"Alert for video_id {video_id} with trend status {trend_status} already sent. Skipping.")
                continue
            # If alert not sent, append to trending_videos and send alert
            trending_videos.append(trend_status_result)
            send_slack_alert(video_id, group, trend_status)  # Send alert for each trending video
            update_trending_videos_database(cursor, video_id, group['moving_average'].iloc[-1], trend_status)

        pbar.update(1)  # Update the progress for each video
    pbar.close()
    cursor.close()
    conn.close()

def check_previous_trends(trending_videos):
    # Get a list of all previously trending video IDs
    previously_trending = {video_id for video_id, _, _ in trending_videos}
    df_current_trends = fetch_current_trending_videos()
    
    # Check if they are still trending
    for _, row in df_current_trends.iterrows():
        video_id = row['video_id']
        if video_id not in previously_trending:
            # This video was previously trending but wasn't updated just now
            group = fetch_video_data(video_id)
            if group is not None and not is_trending(group):
                # Send Slack notification that the video is no longer trending
                title = group['video_title'].iloc[0]
                message_text = f"Video *{title}* is no longer trending."
                slack_message = {
                    "text": message_text,
                }
                response = requests.post(slack_webhook_url, json=slack_message, headers={'Content-Type': 'application/json'})
                # Handle the response


def not_already_trending(video_id):
    try:
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()
        query = 'SELECT video_id FROM current_trending_videos WHERE video_id = %s'
        cursor.execute(query, (video_id,))
        return cursor.fetchone() is None
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            cursor.close()
            conn.close()

def get_last_moving_average(video_id):
    # Fetch the last moving average from the database for the given video_id
    try:
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()
        query = 'SELECT last_moving_average FROM current_trending_videos WHERE video_id = %s'
        cursor.execute(query, (video_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        print(f"An error occurred while fetching the last moving average: {e}")
    finally:
        if conn:
            cursor.close()
            conn.close()

def update_trending_videos_database(cursor, video_id, last_moving_average, trend_status):
    # Update or insert the video trend status and last moving average in the database
    try:
        # Increment times_trended if the video is still trending or set it to 1 if it's a new trend
        query = '''
        INSERT INTO current_trending_videos (video_id, last_moving_average, trend_status, last_alert_date, times_trended)
        VALUES (%s, %s, %s, CURRENT_DATE, 1)
        ON CONFLICT (video_id) DO UPDATE
        SET last_moving_average = EXCLUDED.last_moving_average,
            trend_status = EXCLUDED.trend_status,
            last_alert_date = CURRENT_DATE,
            times_trended = current_trending_videos.times_trended + CASE
                                WHEN EXCLUDED.trend_status = current_trending_videos.trend_status THEN 0
                                ELSE 1 END;
        '''
        cursor.execute(query, (video_id, last_moving_average, trend_status))
        cursor.connection.commit()
    except Exception as e:
        print(f"An error occurred while updating the trending videos: {e}")


def upload_to_s3(bucket_name, s3_file_name, data):
    s3 = boto3.client('s3',
                      aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                      aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'))
    try:
        s3.upload_fileobj(data, bucket_name, s3_file_name)
        return f"https://{bucket_name}.s3.amazonaws.com/{s3_file_name}"
    except NoCredentialsError:
        print("Credentials not available")
        return None
    
 
 
def send_slack_alert(video_id, group, trend_status):
    title, video_url, image_public_url, message_text = None, None, None, None
    try:
        title = group['video_title'].iloc[0]
        video_url = get_video_url(video_id)
        graph_image = plot_moving_average(group, title, show=False)
    except Exception as e:
        log_error_to_flask(e, video_id, "Error while preparing alert data")
        return  # Stop further processing if we encounter an error here

    try:
        # Generate a filename for the image
        s3_file_name = f"{video_id}_trend.png"
        
        # Upload the image to cloud storage and get the public URL
        image_public_url = upload_to_s3('graphlinestorage', s3_file_name, graph_image)
    except Exception as e:
        log_error_to_flask(e, video_id, "Error while uploading image to S3")
        return  # Stop further processing if we encounter an error here

    try:
        # Construct the message based on the trend status
        if trend_status == 'new':
            message_text = f"New Trending Video Alert: *{title}*"
        elif trend_status == 'up':
            message_text = f"Continuing to Trend Upwards: *{title}*"
        else:
            message_text = f"Starting to Trend Downwards: *{title}*"

        # Prepare the Slack message payload
        slack_message = {
            "channel": "C06JLDF1MNH",  # Replace with your actual channel ID
            "text": f"Trending Alert: *{title}*",
            "attachments": [
                {
                    "fallback": "You are unable to choose a game",
                    "callback_id": "modal_open",
                    "color": "#3AA3E3",
                    "attachment_type": "default",
                    "actions": [
                        {
                            "name": "details",
                            "text": "View Details",
                            "type": "button",
                            "value": "view_details",
                            "action_id": "open_modal"
                        }
                    ]
                },
                {
                    "title": title,
                    "title_link": video_url,
                    "image_url": image_public_url
                }
            ]
        }


    except Exception as e:
        log_error_to_flask(e, video_id, "Error while constructing Slack message")
        return  # Stop further processing if we encounter an error here

    try:
        # Send the message using the Slack API
        headers = {'Authorization': f'Bearer {SLACK_BOT_TOKEN}', 'Content-Type': 'application/json'}
        response = requests.post('https://slack.com/api/chat.postMessage', headers=headers, json=slack_message)
        # Check for successful response
        if response.status_code == 200:
            log_alert_to_flask({'text': message_text, 'video_id': video_id, 'trend_status': trend_status})
        else:
            raise ValueError(f"Request to Slack API returned an error {response.status_code}, the response is:\n{response.text}")
    except Exception as e:
        # Log the exception to the Flask app
        log_error_to_flask(e, video_id, "Error while sending Slack message")
        print(f"An error occurred while sending the Slack alert: {e}")


def log_error_to_flask(exception, video_id, context):
    # Replace with your Flask app's URL when using ngrok
    flask_url = 'https://cf21-154-222-6-15.ngrok-free.app/error-logging'  
    error_data = {
        'error': str(exception),
        'video_id': video_id,
        'context': context
    }
    try:
        response = requests.post(flask_url, json=error_data)
        if response.status_code != 200:
            print(f"Failed to log error to Flask app: {response.status_code}, {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"An exception occurred when trying to log error to Flask app: {e}")


def log_alert_to_flask(alert_data):
    # Assuming your Flask app's logging endpoint is '/alert-sent' and it is running on localhost:5000
    flask_url = 'https://cf21-154-222-6-15.ngrok-free.app/alert-sent'  # Replace with your Flask app's URL when using ngrok
    response = requests.post(flask_url, json=alert_data)
    if response.status_code == 200:
        print("Alert log sent to Flask app.")
    else:
        print(f"Failed to log alert: {response.status_code}, {response.text}")

def plot_moving_average(group, title, show=True):
    plt.figure(figsize=(10, 6))
    plt.plot(group['date'], group['moving_average'], marker='o', linestyle='-', color='b')
    plt.title(title)
    plt.xlabel('Date')
    plt.ylabel('Moving Average of Views')
    plt.xticks(rotation=45)
    plt.tight_layout()

    if show:
        plt.show()
    else:
        img_buf = BytesIO()
        plt.savefig(img_buf, format='png')
        plt.close()
        img_buf.seek(0)
        return img_buf



# Main flow
df_moving_averages = fetch_moving_averages()
if df_moving_averages is not None and not df_moving_averages.empty:
    analyze_videos(df_moving_averages)
else:
    print("No moving averages found to analyze.")
