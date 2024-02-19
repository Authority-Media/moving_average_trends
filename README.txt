README.txt
=========

Introduction
------------
This Python program analyzes video view statistics from the 'youtube-seo' database, focusing on the moving average of views per video. 
It identifies videos with significant increases in their moving average over a 5-day period, potentially signaling trending content, and visually presents this data through graphs.

Requirements
------------
- Python 3.x
  Install all dependencies using `pip install -r requirements.txt`.

Usage
-----
To launch the program, execute `python main.py` from the command line within the program's directory. 
The program will automatically connect to the database, analyze the videos, and prompt you to continue after each trending video is identified.

Functionality
-------------
- Fetches video statistics from the database.
- Analyzes each video's moving average over the last 5 days to detect significant increases.
- Plots and displays the moving average trend for videos identified as trending.
- Interactively asks users if they wish to continue after analyzing each trending video.

Slack Integration
-----------------
- The program has been extended with a Flask app to interact with Slack.
- It can send the results of the analysis to Slack, allowing for quick sharing of trending videos.
- A Slack bot is used to post messages in a designated channel.
- The current functionality supports sending data to Slack, but the interactive modal feature to display detailed statistics within Slack is under development.

Known Issues
------------
- The interactive modal feature in Slack, which allows users to open a pop-up window and view detailed video statistics, is not functioning as intended. Discussions with Slack support indicate an issue with payload acknowledgment. The server must respond to Slack's payload with a 200 OK status and an empty JSON body within 3 seconds, which is not currently happening. This issue is being investigated and worked on.

Output
------
For each trending video, a graph is displayed showing the moving average of views over time. 
The X-axis represents dates, and the Y-axis represents the moving average of views.
