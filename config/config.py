from ConfigParser import ConfigParser

#Importing config file
config = ConfigParser()
config.read('config/config.ini')

#Creating global variables
global filesFound 
global nonvalidhref
global validfileext
global searchdepth
global apikeys
global savelocation
global numfetchthreads

#Setting variables
nonvalidhref = str(config.get("Settings", "nonvalidhref")).lower().split(',')
validfileext = str(config.get("Settings", "validfileext")).lower().split(',')
searchdepth = str(config.get("Settings", "searchdepth")).lower()
apikeys = str(config.get("Settings", "apikeys")).lower().split(',')
savelocation = str(config.get("Settings", "savelocation"))
numfetchthreads = str(config.get("Settings", "numfetchthreads")).lower()