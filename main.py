import psycopg2
import pandas as pd
from tqdm import tqdm
import matplotlib.pyplot as plt

# Database connection parameters
db_params = {
    'database': 'youtube-seo',
    'user': 'admin',
    'password': 'wrhTf8KFJ4iWRG6cgIegdVjan6wbmw6b',
    'host': '7hg30g.stackhero-network.com',
    'port': 5432
}

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
        df = pd.DataFrame(results, columns=['video_title', 'video_id', 'date', 'moving_average'])
        return df
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            cursor.close()
            conn.close()

def is_trending(group, min_increase_percentage=10):
    # Assuming 'group' is sorted in ascending date order
    moving_averages = group['moving_average'].values
    if len(moving_averages) < 6:
        return False  # Not enough data to determine a trend

    # Calculate the percentage increase from the start to the end of the 5-day window
    start_average = moving_averages[-6]  # 6th last element (start of window)
    end_average = moving_averages[-1]  # Last element (end of window)
    percentage_increase = ((end_average - start_average) / start_average) * 100

    return percentage_increase >= min_increase_percentage

def analyze_videos(df):
    print("Analyzing videos for trending patterns...")
    for video_id, group in tqdm(df.groupby('video_id'), desc="Analyzing", unit="videos"):
        group = group.sort_values(by='date', ascending=True)
        if is_trending(group):
            title = group['video_title'].iloc[0]
            print(f"\nVideo '{title}' (ID: {video_id}) is trending with significant increase over the last 5 days!")
            plot_moving_average(group)
            if not user_wants_to_continue():
                return  # Stop the analysis based on user input

def plot_moving_average(group):
    group = group.sort_values(by='date')
    plt.figure(figsize=(10, 6))
    plt.plot(group['date'], group['moving_average'], marker='o', linestyle='-', color='b')
    plt.title(f"Moving Average of Views for '{group['video_title'].iloc[0]}'")
    plt.xlabel('Date')
    plt.ylabel('Moving Average of Views')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

def user_wants_to_continue():
    response = input("Do you want to continue analyzing? (yes/no): ")
    return response.lower().startswith('y')

# Main flow
df_moving_averages = fetch_moving_averages()
if df_moving_averages is not None:
    analyze_videos(df_moving_averages)