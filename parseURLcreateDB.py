################################################
# this code parses the URL and extracts the data
# data is generated as an array with the following information
# Train Number \t Train Name \t Src_station \t Dest_station \t ArvTimeSrc \t DepTimeSrc \t ArvTimeDest \t DeptTimeDest \t Distance \t  Days_it_runs
# eventually this information will be dumped into a database
# TODO: add the fare information to the table
# other than importing the packages, you need to download Chrome driver and add it to the PATH
################################################
import mechanize
from bs4 import BeautifulSoup
from py2neo import Node, Relationship, Graph, watch
import json

# url to look for
url = 'http://www.indianrail.gov.in/train_Schedule.html'

# example of one train number (eventually will need to create an array)
train_num = 12138
train_name = ""

# lookup table to get the station name fromt the stn code
br = mechanize.Browser()

# creating a graph database
graph = Graph()
watch("httpstream")

def gettimediff(time1, time2):
	print time1, time2
	at1 = time1.split(':')
	t1mins = int(at1[0])*60 + int(at1[1])
	at2 = time2.split(':')
	t2mins = int(at2[0])*60 + int(at2[1])
	print t1mins, t2mins
	timediff = t2mins - t1mins
	if (t2mins < t1mins):
		timediff = t2mins + (24*60) - t1mins
	return timediff

# fill the search bar with the desired train number and click "Get Details"
def scrape_html(br):
	br.open("http://www.indianrail.gov.in/train_Schedule.html")
	br.select_form(nr=0)
	br['lccp_trnname'] = str(train_num)
	# get the html page and scrape the page to get the data
	req = br.submit(name='getIt')
	html = req.read()
	print "done reading the html page"
	soup = BeautifulSoup(html)
	results = soup.findAll('table', {"class":"table_border_both"})
	aStn = list()
#	route = list() 
	aArvTime = list()
	aDeptTime = list()
	runs_on = list()
	aDist = list()
	#table0 contains information about the source
	table0 = results[0]
	#table1 contains information about various destinations
	table1 = results[1]
	# processing table0
	trs = table0.findAll('tr')
	for tr in trs:
		tds = tr.findAll('td')
		strToCompare = tds[0].text.replace(" ", "")
		if strToCompare == str(train_num):
			train_name =  tds[1].text.strip()
			runs_from =  tds[2].text.strip()
			for runson in tds[3:]:
				runs_on.append(runson.text)
	# processing table1
	trs = table1.findAll('tr')
	# first tr will give us the source station name
	mytds = trs[1].findAll('td')
	src_stn = mytds[1].text.strip()
	# for SRC the arrival and destination time can be considered the same
	dept_time = arv_time = mytds[5].text.strip()
	# populate the array
	aArvTime.append(arv_time)
	aDeptTime.append(dept_time)
	aStn.append(src_stn)
	aDist.append(0)
	for tr in trs[2:]:
		tds = tr.findAll('td')
		if (len(tds) >= 9):
			stncode = tds[1].text.strip()
			arvtime = tds[4].text.strip()
			depttime = tds[5].text.strip()
			aStn.append(stncode)
			aArvTime.append(arvtime)
			aDeptTime.append(depttime)
			dist = tds[7].text.strip()
			aDist.append(dist)
	# now starts the fare enquiry
	for i in range(len(aStn)):
		for j in range(i+1, len(aStn)):
			src = aStn[i]
			dest = aStn[j]
			print src, dest
			# now query the fare 
			br.open("http://www.indianrail.gov.in/fare_Enq.html")
			br.select_form(nr=0)
			br['lccp_trnno'] = str(train_num)
			br['lccp_day'] = str(17)
			br['lccp_month'] = str(5)
			br['lccp_srccode'] = str(src)
			br['lccp_dstncode'] = str(dest)
			control_classopt = br.find_control(name="lccp_classopt")
			control_classopt.value = ['SL']
			control_age = br.find_control(name="lccp_age")
			control_age.value = ['30']
			control_frclass = br.find_control(name="lccp_frclass1")
			control_frclass.value = ['GN']
			control_conc = br.find_control(name="lccp_conc")
			control_conc.value = ['ZZZZZZ']
			req = br.submit(name='getIt')
			html = req.read()
			soup = BeautifulSoup(html)
			tds = soup.findAll('td', {"class":"table_border_both"})
			fareBWstns = int(tds[-1].text.strip())
			distBWstns = int(aDist[j]) - int(aDist[i])
			timeBWstns = gettimediff(aArvTime[i],aDeptTime[j])
			timeWait = gettimediff(aDeptTime[i],aArvTime[i])
			# now populate the database
			mydict = {'Fare': fareBWstns, 'Dist': distBWstns, 'TravelTime': timeBWstns, 'WaitTime': timeWait, 'TrainNum': train_num, 'TrainName': train_name}
			myjson = json.dumps(mydict)
			print myjson
			# step1: create a unique source node
			qs1 = 'MERGE (a:Stn {name: {psrc}})'
			graph.cypher.execute(qs1, {'psrc':src})
			
			# step 2 is to create a unique node and relationship
			# Source and Dest nodes have label Stn
			# each relationship has a label CONNECTS with property "train_details" which is an array
			qs2 = 'MATCH (a:Stn {name: {psrc}}) MERGE (b:Stn {name: {pdest}}) CREATE UNIQUE (a)-[r:CONNECTS]->(b) SET r.train_details = CASE r.train_details WHEN null THEN [{pjson}] ELSE r.train_details + [{pjson}] END RETURN r'
			results = graph.cypher.execute(qs2, {'psrc':src, 'pdest':dest, 'pjson':myjson})
			print results

if __name__ == '__main__':
	scrape_html(br)
