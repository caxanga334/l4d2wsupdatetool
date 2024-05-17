# Left 4 Dead 2 Steam Workshop Updater Tool

A python script to automatically download and install Left 4 Dead 2 workshop addons for dedicated servers.

The script uses the Steam web API to fetch the last updated timestamp of each addon. This is then compared to a saved timestamp if available.

# Features
* Automatic download and install
* Only downloads new or updated addons

# Requirements
* Python 3.11
* Python libraries:
  * requests
  * json
  * os
  * logging
  * time
  * subprocess
  * shutil
  * datetime
  * shlex
  * argparse
* Steam web API key.
* Steam account with Steam guard disabled.

# Usage

Open `workshop_updater.py` and edit the *Tool Settings* as needed.

Then run python.

# Limitations

* The tool currently doesn't check if a download has failed.

Run the tool with `--check-addons` to check for extra and missing addons. Missing addons will be downloaded automatically. Extras will be logged but not deleted.