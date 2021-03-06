from bs4 import BeautifulSoup
import requests
import json
import urllib3
import re
import concurrent.futures
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS 		= {
	"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.89 Safari/537.36",
	"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
	"Referer": "https://flex.infosecinstitute.com/portal/register",
	"Accept-Encoding": "gzip, deflate",
	"Accept-Language": "en-US,en;q=0.9,la;q=0.8",
	"Connection": "close",
}

COOKIES 		= {
	"flexcenter": '',
}

cyan 	= "\033[0;96m"
green 	= "\033[0;92m"
white 	= "\033[0;97m"
red 	= "\033[0;91m"
blue 	= "\033[0;94m"
yellow 	= "\033[0;33m"
magenta = "\033[0;35m"

bar 	= "-" * 150

def login(loginURL, username, password):
	"""
	Returns only the required cookie (i.e. flexcenter)
	"""
	response 	= requests.post(loginURL,
		headers = HEADERS,
		data 	= {
			'_method': 'POST',
			'email': username,
			'password': password,
			'remember_me': 1,
			'_Token[unlocked]': '',
		},
		# proxies = {
		# 	'http': '127.0.0.1:8080',
		# 	'https': '127.0.0.1:8080',
		# },
		# verify 	= False,
		allow_redirects = False,
	)

	flexcenter 	= response.headers['Set-Cookie'].split(";")[0].split("=")[1]
	# print(flexcenter)
	return(flexcenter)

def fetchCourseLinks(url):
	"""
	Fetches videos URLs
	"""

	url 		= url.replace('/portal/', '/portal/api/')

	response 	= requests.get(url,
		headers = HEADERS,
		cookies = COOKIES,
		# proxies = {
		# 	'http': '127.0.0.1:8080',
		# 	'https': '127.0.0.1:8080',
		# },
		# verify 	= False
	)

	if response.status_code == 200:
		return(response.text)

	print("[#] Error: ", response.status_code, response.headers, response.text)

def parseCourseLinks(body):
	"""
	Returns Course's videos links in a list
	"""

	try:
		urls 		= {}
		children 	= json.loads(body)
		children 	= children['playlist']['children']

		for objs, vidNumber in zip(children, range(1, len(children) + 1)):
			urls[f"{vidNumber:02d}_{objs['name']}"] = objs['item_url']

		return(urls)

	except KeyError:
		urls 			= {}
		data 			= json.loads(body)
		childrenNodes 	= data['data']['playlist']['children']
		vidNumber		= 1

		for items in childrenNodes:
			for singleChildren in items['children']:
				name 	= singleChildren['name']
				url 	= singleChildren['item_url']

				urls[f"{vidNumber:03d}_{name}"] = url
				vidNumber += 1

		# print(urls)
		return(urls)

def fetchCourses():
	print(bar)
	print("{}{:<5}{} | {}{:<60}{} | {}{:<20}{}".format(
		yellow, "ID", white,
		magenta, "Course URL", white,
		cyan, "Course Name", white,
	))
	print(bar)

	data 		= {}
	pagesURL 	= "https://flex.infosecinstitute.com/portal/api/skills/search.json?type=path&page=1&limit=10000" 	# Fetches JSON containing all courses details/links
	response 	= requests.get(pagesURL,
		headers = HEADERS,
		cookies = COOKIES,
		# proxies = {
		# 	'http': '127.0.0.1:8080',
		# 	'https': '127.0.0.1:8080',
		# },
		# verify 	= False
	)

	if response.status_code == 200:
		jsonData 	= json.loads(response.text)
		jsonItems 	= jsonData['items']

		for objs in jsonItems:
			courseId 	= objs['id']
			courseName 	= objs['name']
			courseURL 	= objs['item_url']

			data[courseId] = {'url': courseURL, 'name': courseName}

			print("{}{:<5}{} | {}{:<60}{} | {}{:<20}{}".format(
				yellow, courseId, white,
				magenta, courseURL, white,
				cyan, courseName, white,
			))

		print(bar)

	# print(json.dumps(data, indent=4, default=str))
	return(data)

def returnVideoDownloadLink(host, vidURLs, videoName):
	"""
	Returns S3 bucket's DDL for videos
	"""

	response 	= requests.get(vidURLs,
		headers = HEADERS,
		cookies = COOKIES,
		# proxies = {
		# 	'http': '127.0.0.1:8080',
		# 	'https': '127.0.0.1:8080',
		# },
		# verify 	= False
	)

	try:
		regex 		= r'videoUrl = \"(.*?)\"\;'
		soup 		= BeautifulSoup(response.text, 'html.parser')
		urlJS 		= soup.find_all('script')[4].contents[0]
		urlVid 		= re.findall(regex, urlJS)[0]

		ddlURL 		= f"{host}{urlVid}"

		response 	= requests.get(ddlURL,
			headers = HEADERS,
			cookies = COOKIES,
			# proxies = {
			# 	'http': '127.0.0.1:8080',
			# 	'https': '127.0.0.1:8080',
			# },
			# verify 	= False
		)

		downloadURL	= json.loads(response.text)['url']
		# print({videoName: downloadURL})
		return({videoName: downloadURL})

	except IndexError:
		return(None)

def createCourseDirectory(name):
	"""
	For creation of the course directory
	"""

	path 		= os.getcwd()
	courseDir	= os.path.join(path, name)

	if not(os.path.isdir(courseDir)):
		os.mkdir(courseDir)

def downloadVideos(vidName, downloadLink, dirName):
	"""
	For downloading with aria2c
	"""
	vidName 	= vidName.replace('/', '').replace(',', '').replace('"', '').replace("'", '').replace(' ', '_')
	command 	= f"aria2c -s 10 -j 10 -x 16 -k 5M --file-allocation=none '{downloadLink}' -o '{dirName}/{vidName}.mp4' -c"
	print(f"\n{command}")
	os.system(command)

def main():
	ddlURLs 	= []
	host 		= "https://flex.infosecinstitute.com"
	loginURL 	= "https://flex.infosecinstitute.com/portal/login"

	username 	= ""
	password 	= ""

	if username == '' and password == '': exit("[!] Please edit and rerun the script with credentials")
	cookies 				= login(loginURL, username, password)
	COOKIES['flexcenter'] 	= cookies

	courses 	= fetchCourses()
	userInput 	= int(input("\n[&] Please enter any Course Id from the table above (such as 25): "))

	if userInput in courses:
		print(f"\n[$] Name: {cyan}{courses[userInput]['name']}{white}")
		print(f"[$] URL: {yellow}{courses[userInput]['url']}{white}")

		dirName 	= courses[userInput]['name'].replace('/', '').replace(',', '').replace('"', '').replace("'", '')
		createCourseDirectory(dirName)

		print(f"\n{cyan}[*] Fetching path's description")
		jsonBody 	= fetchCourseLinks(courses[userInput]['url'])

		print(f"{yellow}[*] Fetching videos links")
		videoURLs 	= parseCourseLinks(jsonBody)

		playlstName = []
		playlistURL	= []

		for urls in videoURLs.items(): playlstName.append(urls[0]) 		# Appending Video Name 	-> i.e. 0
		for urls in videoURLs.items(): playlistURL.append(urls[1]) 		# Appending URLs 		-> i.e. 1

		# for urls, names in zip(playlistURL, playlstName):
		# 	returnVideoDownloadLink(host, urls, names)
			# break

		print(f"{magenta}[*] Parsing video links for DDL (might take some time)")
		with concurrent.futures.ProcessPoolExecutor(max_workers = 10) as executor:
			for results in executor.map(returnVideoDownloadLink, [host] * len(playlistURL), playlistURL, playlstName):
				if results != None:
					ddlURLs.append(results)

		with open('downloads.json', 'w+') as f: f.write(json.dumps(ddlURLs, indent=4, default=str))

		print(f"\n{green}[*] Starting downloading of videos")
		for urls in ddlURLs:
			for vidName, downloadLink in urls.items():
				downloadVideos(vidName, downloadLink, dirName)

	else:
		print(f"[!] {red}Course not found! Please course ID again{white}")

if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt:
		print("[!] Okay-sed :(")
