README.txt
=========

Introduction
------------
This Python program analyzes video view statistics from the 'youtube-seo' database, focusing on the moving average of views per video. 
It identifies videos with significant increases in their moving average over a 5-day period, potentially signaling trending content, and visually presents this data through graphs.

Requirements
------------
- Python 3.x
- External Libraries: psycopg2, pandas, matplotlib, tqdm
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

Output
------
For each trending video, a graph is displayed showing the moving average of views over time. 
The X-axis represents dates, and the Y-axis represents the moving average of views.


