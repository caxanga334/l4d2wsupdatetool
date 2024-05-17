import requests, json, os, logging, time, subprocess, shutil, shlex
from datetime import datetime

# Tool Settings, modify below as needed

# Steam web API Key here
steamAPIkey = "YOUR_API_HERE"
# File name relative to this script which contains a list of workshop file IDs to download
workshopIDsfile = "workshop_addons.txt"
# Username of a Steam account to use to download the workshop files. Steam guard must disabled for this
steamUser = "username"
# Password of the Steam account used to download
steamPass = "password"
# Path to the steamcmd bin
# Can be just the steamcmd executable if steamcmd is on PATH
steamCMDPath = "C:\steamcmd\steamcmd.exe"
# Path where workshop entries will be downloaded to
downloadPath = "C:\mysevers\workshop_downloads"
# Path to the Left 4 Dead 2 server 'addons' folder
serverPath = os.path.join('c:', os.sep, 'myservers', 'left4dead2ds', 'left4dead2', 'addons')

# Globals
steamAPIURL = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
appID = '550' # While yes, we can get this from the API response, this script was made for a single game: Left 4 Dead 2
currentTime = int(datetime.now().timestamp()) # Current time as a UNIX timestamp
toolVersion = "1.0.1"

def split_list_every(source, step):
  return [source[i::step] for i in range(step)]

class WorkshopEntry(object):
  def __init__(self, id: int, title: str, timestamp: int) -> None:
    self.name = title
    self.id = id
    self.timestamp = timestamp
    self.outdated = True

  def NeedsUpdate(self):
    return self.outdated

class WorkshopUpdater(object):
  def __init__(self) -> None:
    self.log_dir = None
    self.log_file = None
    self.logger = logging.getLogger("WorkshopUpdaterTool")
    self.workshop_ids = []
    self.http_post_data = {}
    self.http_headers = {
      'User-Agent': 'Python; Steam Workshop Updater Tool ' + toolVersion + '; https://github.com/caxanga334/l4d2wsupdatetool',
    }
    self.json_response = None
    self.api_entries = []
    self.last_updated = 0 # UNIX timestamp of the last time this tool updated the workshop entries
    self.saved_data = None

  def setup_logger(self):
    self.log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    self.log_file = datetime.now().strftime('workshop_tool_%d-%m-%Y.log')

    if not os.path.exists(self.log_dir):
      print("Creating log directory at " + self.log_dir)
      os.makedirs(self.log_dir, mode=0o755)

    logpath = os.path.join(self.log_dir, self.log_file)
    logging.basicConfig(filename=logpath, level=logging.INFO, datefmt='%Y-%m-%d %H:%M:%S', format='%(asctime)s %(levelname)s: %(message)s')

  def load_workshop_ids(self):
    # Read the file and split the lines
    with open(workshopIDsfile) as f:
      lines = [line.strip() for line in f if not line.startswith('//')]

    # Iterate through each line and extract the ID
    for line in lines:
      try:
        self.workshop_ids.append(int(line))
      except ValueError:
        self.logger.warning("Invalid workshop entry \"" + line + "\"")
        pass

    self.logger.info("Found {0} workshop entries!".format(len(self.workshop_ids)))

  def build_post_data(self):
    self.http_post_data['key'] = steamAPIkey

    length = len(self.workshop_ids)

    self.http_post_data['itemcount'] = str(length)

    i = 0
    while i < length:
      self.http_post_data['publishedfileids[' + str(i) + ']'] = str(self.workshop_ids[i])
      i = i + 1

  def make_http_request(self):
    response = requests.post(url=steamAPIURL, headers=self.http_headers, data=self.http_post_data)

    if response.status_code != requests.codes['ok']:
      self.logger.error("Got HTTP response " + str(response.status_code) + " from Steam web API!")
      raise Exception("Steam Web API error!")
    else:
      self.logger.info("Got API response from Steam.")
    
    self.json_response = json.loads(response.text)

    #with open("output.json", "w", encoding='utf-8') as file:
    #  json.dump(self.json_response, file, ensure_ascii=False, indent=4)

  def store_api_response(self):
    count = self.json_response['response']['resultcount']
    if count != len(self.workshop_ids):
      self.logger.warning("Number of entries in the workshop ID list does not match the number of entries from the API response!")
    
    array = self.json_response['response']['publishedfiledetails']

    for entry in array:
      name = entry['title']
      id = int(entry['publishedfileid'])
      timestamp = 0
      if 'time_updated' in entry:
        timestamp = entry['time_updated']
      else:
        timestamp = entry['time_created']

      we = WorkshopEntry(id, name, timestamp)
      self.api_entries.append(we)

    for workshopentry in self.api_entries:
      self.logger.info("Workshop Entry: " + workshopentry.name + " (" + str(workshopentry.id) + ")")

    time.sleep(1)

  def save_data(self):
    outData = {}
    outData['last_update_time'] = currentTime
    outData['entry_count'] = len(self.api_entries)
    outData['workshop_entries'] = []
    for workshopentry in self.api_entries:
      outArrayEntry = {}
      outArrayEntry['id'] = workshopentry.id
      outArrayEntry['timestamp'] = workshopentry.timestamp
      outArrayEntry['title'] = workshopentry.name # Not really used, saved to help identify addons
      outData['workshop_entries'].append(outArrayEntry)

    outStr = json.dumps(outData, ensure_ascii=False, indent=4)

    with open('workshop_updater_data.json', "w") as file:
      file.write(outStr)

    self.logger.info('Saved updater data.')

  def load_saved_data(self):
    if os.path.exists('workshop_updater_data.json'):
      file = open('workshop_updater_data.json', "r")
      self.saved_data = json.load(file)
      self.last_updated = self.saved_data['last_update_time']
      self.logger.info("Loaded saved tool data.")
    else:
      self.logger.info("No saved data was found.")

  def run_steamcmd(self, need_update : list):
    # We have an arg limit, split the list, download about 10 items per 'run'
    N = int(len(need_update) / 10)

    if N < 1:
      N = 1

    to_update = split_list_every(need_update, N)
    i = 1
    i_max = len(to_update)
    self.logger.info("There are {0} addons that needs to be downloaded. They will be split into {1} SteamCMD tasks.".format(len(need_update), i_max))

    for idlist in to_update:    
      args = "+force_install_dir " + downloadPath + " +login " + steamUser + " " + steamPass + " "
      entryargs = ""

      for entryid in idlist:
        print("Updating " + str(entryid))
        download_arg = "+workshop_download_item " + appID + " " + str(entryid) + " "
        entryargs = entryargs + download_arg

      args = args + entryargs + "+quit"
      vargs = shlex.split(args)
      steamcmd = steamCMDPath
      command = []
      command.append(steamcmd)

      for argument in vargs:
        command.append(argument)

      self.logger.info("Starting SteamCMD {0} of {1}.".format(i, i_max))
      subprocess.run(command)
      self.logger.info("SteamCMD done.")
      i = i + 1

  def update_steamcmd(self):
    need_update = []

    # We have saved data
    if self.saved_data:
      array = self.saved_data['workshop_entries']
      for workshopentry in self.api_entries:
        for savedentry in array:
          if workshopentry.id == savedentry['id']:
            if workshopentry.timestamp > savedentry['timestamp']:
              need_update.append(workshopentry.id)
              self.logger.info("Updating " + workshopentry.name)
            else:
              workshopentry.outdated = False

      # Second loop
      for workshopentry in self.api_entries:
        # Outdated is true by default and set to false if found on the up to date addon database
        # This will make sure new entries get updated
        if workshopentry.outdated and workshopentry.id not in need_update:
            need_update.append(workshopentry.id)
            self.logger.info("Updating new entry " + workshopentry.name)

    # We don't have saved data, update all addons
    else:
      for workshopentry in self.api_entries:
        need_update.append(workshopentry.id)
        self.logger.info("Updating " + workshopentry.name)

    if len(need_update) > 0:
      self.run_steamcmd(need_update)
      self.post_steamcmd_update(need_update)
    else:
      self.logger.info("No workshop entries needs to be updated.")

  def post_steamcmd_update(self, updated_ids : list):
    wsfolder = os.path.join(downloadPath, 'steamapps', 'workshop', 'content', appID)
    self.logger.info("Preparing to move updated files to server.")

    for root, subdirs, files in os.walk(wsfolder):
      basename = os.path.basename(root)
      wsid = 0
      try:
        wsid = int(basename)
      except ValueError:
        pass

      if wsid in updated_ids:
        for f in files:
          if f.endswith('.bin'):
            vpk = '{0}.vpk'.format(wsid)
            os.rename(os.path.join(root, f), os.path.join(root, vpk))
            shutil.move(os.path.join(root, vpk), os.path.join(serverPath, vpk))
            self.logger.info("Moving file to server from {0} to {1}".format(os.path.join(root, vpk), os.path.join(serverPath, vpk)))



updater = WorkshopUpdater()
updater.setup_logger()
updater.logger.info("Starting workshop updater tool " + toolVersion + ".")
updater.load_workshop_ids()
updater.load_saved_data()
updater.build_post_data()
updater.make_http_request()
updater.store_api_response()
updater.update_steamcmd()
updater.save_data()
