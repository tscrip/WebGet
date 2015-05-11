from flask import Flask, request
from threading import Thread
from bs4 import BeautifulSoup
from multiprocessing import Process
from lib import fileDownloader
from config import config as config
import sqlite3
import threading
import time
import requests
import re
import ntpath
import json
import os.path
import urllib2

class Database:
	#Create Database
	#CREATE TABLE Links (id INTEGER Primary Key autoincrement,link varchar(255),status int(1),active int(1));

	#status column can have 3 values
	#  	0 -> Link has not been touched
	#	1 -> Link has been grabbed, but file has not finished downloading
	#	2 -> Link has been grabbed, and file has finished downloading 

	#active column can have 2 values
	#	0 -> Currently not active
	#	1 -> Currently active

	def __init__(self):
		self.con = sqlite3.connect('database.db')

	def write(self,link):
		#con = sqlite3.connect('database.db')
		with self.con:
			cur = self.con.cursor()

			#Inserting link
			try:
				cur.execute('INSERT INTO Links VALUES (null,\''+link+'\',0,0);')
				self.con.commit()

				return True
			except sqlite3.OperationalError, msg:
				return msg

	def select_resume(self):
		with self.con:
			cur = self.con.cursor()
	  
			#Getting link
			cur.execute('SELECT link,id FROM Links WHERE status=1 AND active=0;')
			data = cur.fetchone()
			return data

	def select_new(self):
		with self.con:
			cur = self.con.cursor()
	  
			#Getting link
			cur.execute('SELECT link,id FROM Links WHERE status=0 AND active=0;')
			data = cur.fetchone()
			return data

	def mark_processing(self,link_id):
		#con = sqlite3.connect('database.db')
		with self.con:
			cur = self.con.cursor()
	  
			#Updating link status
			cur.execute('UPDATE Links SET status=1, active=1 WHERE id=?', (link_id,))
			self.con.commit()
			return cur.rowcount

	def mark_processed(self,link_id):
		#con = sqlite3.connect('database.db')
		with self.con:
			cur = self.con.cursor()
	  
			#Updating link status
			cur.execute('UPDATE Links SET status=2, active=0 WHERE id=?', (link_id,))
			self.con.commit()
			return cur.rowcount

	def clear_active(self):
		#con = sqlite3.connect('database.db')
		with self.con:
			cur = self.con.cursor()
	  
			#Updating link status
			cur.execute('UPDATE Links SET active=0 WHERE active=1;')
			self.con.commit()
			return cur.rowcount

	def clear_database(self):
		with self.con:
			cur = self.con.cursor()

			#Updating link status
			cur.execute('DELETE FROM Links Where active IN (0,1,2);')
			self.con.commit()
			return cur.rowcount

class Core(object):
	def __init__(self,database):
		#Getting passed in object
		self.DatabaseObj = database

	#Core contains core functions and code
	def ProcessURL(self,url):
		#Getting object
		DatabaseObj = self.DatabaseObj()

		#Creating global variable
		config.filesfound = 0

		#Getting HTML from site and turning into BS objext
		baseSoup = BeautifulSoup(requests.get(url).text)

		#Checking to see if site is powered by Directory Lister
		for link in baseSoup.find_all('a'):
			if "directorylister.com" in link.get('href'):
				self.baseURL = re.match(ur'(.*\..{2,3}/)', url).group(0)
			else:
				self.baseURL = url

		#Importing URL into nonvalid HREF to prevent unintended looping
		config.nonvalidhref.append(self.baseURL.lower())

		#Looping through all anchor tags on page
		for link in baseSoup.find_all('a'):

			#Verifying link is not in nonvalidhref list
			if link.get('href').lower() not in config.nonvalidhref:

				#Checking to see if anchor ends with extention in validFileExt list
				if link.get('href').lower().endswith(tuple(config.validfileext)):

					print("Found File: "+str(self.baseURL)+link.get('href'))
					
					#Writting urls to the database(link,title)
					self.status = DatabaseObj.write(str(self.baseURL)+link.get('href'))
					
					config.filesfound += 1

				#Checking to see if anchor is directory        
				elif link.get('href').endswith("/") or not re.search("(.*\..{2,3}|javascript:void.*)",link.get('href').lower()):
					print("Found Directory: "+link.get('href'))

					#Running function to loop though directory for media files
					self.ProcessDir(0,config.searchdepth,str(self.baseURL),str(link.get('href')))

		#Returning files found            
		return config.filesfound

	def ProcessDir(self,curdepth,maxdepth,baseurl,anchorurl):
		#Getting object
		DatabaseObj = self.DatabaseObj()


		if curdepth < config.searchdepth:
			soup = BeautifulSoup(requests.get(str(baseurl)+str(anchorurl)).text)
			for link in soup.find_all('a'):
				#DEBUG print("Link: "+link.get('href'))
				if link.get('href').lower() not in config.nonvalidhref:

					#Identifying files and directories
					if link.get('href').lower().endswith(tuple(config.validfileext)):
						print("Found File: "+str(baseurl)+link.get('href'))

						#Writting urls to the database
						self.status = DatabaseObj.write(str(baseurl)+link.get('href'))

						config.filesfound += 1

					elif link.get('href').endswith("/") or not re.search("(.*\..{2,3}|javascript:void.*)",link.get('href').lower()):
						print("Found Directory: "+str(baseurl)+link.get('href'))
						self.ProcessDir(int(curdepth)+1,maxdepth,str(baseurl),str(link.get('href')))

	def TrafficCop(self):
		#Getting object
		DatabaseObj = self.DatabaseObj()

		#Setting variables
		self.activethreads = 0
		
		#select_resume
		#[0] -> link
		#[1] -> id

		#Clearing all actives in database
		DatabaseObj.clear_active()

		while True:
			#DEBUG print("Waiting...")

			if threading.active_count()-2 < int(config.numfetchthreads):
				
				self.resume_link_url = DatabaseObj.select_resume()

				if self.resume_link_url is not None:

					#Creating variables
					self.link_url = str(self.resume_link_url[0])
					self.link_id = str(self.resume_link_url[1])

					#Marking link as processing in database
					DatabaseObj.mark_processing(self.link_id)

					#Threading DownloadURL method
					downloadthread = threading.Thread(target=self.DownloadURL, args=(self.link_url,self.link_id))
					downloadthread.setDaemon(True)
					downloadthread.start()

					#Once Complete
					DatabaseObj.mark_processed(self.link_id)

				else:
					self.new_link_url = DatabaseObj.select_new()
					if self.new_link_url is not None:

						#Creating variables
						self.link_url = str(self.new_link_url[0])
						self.link_id = str(self.new_link_url[1])

						#Marking link as processing in database
						DatabaseObj.mark_processing(self.link_id)

						#Threading DownloadURL method
						downloadthread = threading.Thread(target=self.DownloadURL, args=(self.link_url,self.link_id))
						downloadthread.setDaemon(True)
						downloadthread.start()

						#Once Complete
						DatabaseObj.mark_processed(self.link_id)
			#else:
				#DEBUG print("Max number of fetch threads already active: "+config.numfetchthreads)
			time.sleep(5)

	def DownloadURL(self,url,url_id):
		#Getting object
		DatabaseObj = self.DatabaseObj()

		#Getting thread id
		self.threadid = threading.current_thread()

		#Extracting filename
		self.filename = ntpath.basename(url)
		#Un-URLEncodeing string
		self.filename = urllib2.unquote(self.filename)
		#Making sure filename is valid
		self.filename = "".join(x for x in self.filename if x not in "\/:*?<>|")

		#DEBUG print("FileName: "+self.filename)
 
		#Marking link as processing in database
		DatabaseObj.mark_processing(url_id)

		#Configuring downloader
		downloader = fileDownloader.DownloadFile(url, config.savelocation+self.filename)
		
		#If file exists, resume else start
		self.filepresent = os.path.isfile(config.savelocation+self.filename)
		if self.filepresent:
			print(str(threading.currentThread())+":Resuming Download of: "+self.filename)
			downloader.resume()
		else:
			print(str(threading.currentThread())+":Starting Download of: "+self.filename)
			downloader.download()

		#Once Complete
		DatabaseObj.mark_processed(url_id)   

	def ClearDatabase(self):
		#Getting object
		DatabaseObj = self.DatabaseObj()

		#Clearing ALL records from SQLite database
		DatabaseObj.clear_database()

class WebServer():
	def __init__(self):
		#Creating Object
		CoreObj = Core(Database)

		app = Flask(__name__)
			
		@app.route("/")
		def default():
			return "Hello World!"
				
		@app.route("/clear_database")
		def clear_database():
			#Clearing Database
			CoreObj.ClearDatabase()
			return json.dumps("Database 'Links' Cleared")
		
		@app.route('/add_video', methods=['POST'])
		def add_video():
			#Posted Parameter are: apikey, url

			if request.method == 'POST':
				self.apikey = request.form['apikey']
				self.url = request.form['url']
				if self.apikey != "" and self.url != "": 
					if self.apikey in config.apikeys:
						self.filesfound = CoreObj.ProcessURL(self.url)
						return "Completed:"+str(self.filesfound)

						#if status:
						#	return "Success"
						#else:
						#    return "An Error Has Occured"
				else:
					return "404"

		@app.route('/add_file/<apikey>/<url>', methods=['GET'])
		def add_file(apikey,url):
			var = ""
			if apikey in self.apikey:
				
				status = DatabaseObj.write(url)
				if status:
					return "Success"
				else:
					return "An Error Has Occured"

		@app.route('/add_music/<apikey>/<url>/<artist>/<song>/<album>/<art_url>', methods=['GET'])
		def add_music(apikey,url,artist,song,album,art_url):
			var = ""
			if apikey in self.apikey:

				status = DatabaseObj.write(url)
				if status:
					return "Success"
				else:
					return "An Error Has Occured"

				
		@app.errorhandler(Exception)
		def exception_handler(error):
			return "Error: "  + repr(error)
					
		if __name__ == "__main__":
			app.run(threaded=True)

if __name__ == '__main__':
	try:
		#Starting background fetching job
		CoreObj = Core(Database)

		#Starting web server
		WebServer = threading.Thread(target=WebServer)
		WebServer.setDaemon(True)
		WebServer.start()

		CoreObj.TrafficCop()

	except (KeyboardInterrupt):
		#print("Hello World")
		print("Exiting")


	