#!/usr/bin/env python
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.  See http://www.gnu.org/copyleft/gpl.html for
# the full text of the license.

from __future__ import print_function
import time
import re
import sys
import pprint
import xml.etree.ElementTree as ET
import bugzilla
import requests
import json
from jira import JIRA

## Read the XML file
tree = ET.parse('test.xml')
root = tree.getroot()
for mel_release in root.findall('mel_release'):
	mel_release_name = mel_release.get('name')
	print ("%s" % mel_release_name)
	for package in mel_release.iter('package'):		
		package_name = package.get('name')
		package_version = package.get('version')
		source = package.get('source')
		print ("%s %s %s" % (package_name , package_version , source ))
		JIRA_VERSION = mel_release_name
		JIRA_COMPONENT = package_name
		UPSTREAM_VERSION = package_version	

		# Create JIRA interface object
		JIRA_URL = "https://mentorgraphics.atlassian.net"
		JIRA_PROJ_KEY = "JIRATEST"
		jira = JIRA(JIRA_URL, basic_auth=('naeem_khan@mentor.com', 'MentorCare406'))
	
		if source == 'bugzilla':
			# Create bugzilla interface object
			if package_name == 'dbus':			
				BASE_URL = 'https://bugs.freedesktop.org'
			elif package_name == 'kernel':			
				BASE_URL = "https://bugzilla.kernel.org"
			elif package_name == 'ntp':
				BASE_URL = 'http://bugs.ntp.org'
			elif package_name == 'glibc':
				BASE_URL = 'https://sourceware.org/bugzilla'
			BZ_URL = BASE_URL + '/xmlrpc.cgi'
			bzapi = bugzilla.Bugzilla(BZ_URL)

			# Build the query
			query = bzapi.build_query()

			# Since 'query' is just a dict, you could set your own parameters too, like
			# if your bugzilla had a custom field. This will set 'status' for example,
			# but for common opts it's better to use build_query
			query["include_fields"] = ["id", "summary", "product", "component", "status", "version", "resolution", "op_sys"]
			query["product"] = package_name
			query["op_sys"] = [ "Linux (All)" ]
			query["version"] = package_version

			# Grab bugs from the BZ_URL
			# Note: Comments must be fetched separately on stock bugzilla
			print("Querying '%s' upstream project for bugs that apply to %s" % (JIRA_COMPONENT, JIRA_VERSION))
			t1 = time.time()
			bugs = bzapi.query(query)
			t2 = time.time()
			print("Found %d bugs with the upstream query" % len(bugs))
			print("Query processing time: %s" % (t2 - t1))
			#print("\nbugs:\n%s\n" % pprint.pformat(bugs))

			# Load all similar issues from JIRA for later searching
			jira_issues = jira.search_issues('project=JIRATEST AND component in ("'+JIRA_COMPONENT+'")', maxResults=100)
			while len(jira_issues) < jira_issues.total:
				 jira_issues += jira.search_issues('project=JIRATEST AND component in ("'+JIRA_COMPONENT+'")', startAt=len(jira_issues), maxResults=100)
			jira_issues = sorted (jira_issues, key=lambda j: j.fields.customfield_11500)

			new_issues_list = []

			# Search JIRA issues for each bug found in the BZ_URL
			for bug in bugs:
				 #print("\nSearch for bug %s" % bug.id)
				 #print("\n\nbug: %s\n\n" % pprint.pformat(vars(bug)))
				 foundIssue = False

				 # Search the previously downloaded upstream issues
				 # For now, just search for the bug ID for each bug.
				 issues = [issue for issue in jira_issues if issue.fields.customfield_11500 == str(bug.id)]

				 for issue in issues:
					  if str(issue.fields.customfield_11500) == str(bug.id):
						   print("Found %s with bug id %s" % (issue.key, issue.fields.customfield_11500) )
						   update = False

						   # Validate the existing bug fields match with the upstream
						   if issue.fields.customfield_11502 != None and bug.product != "" and issue.fields.customfield_11502 != bug.product:
						       print ("%s : Upstream Product field value of '%s' did not match '%s'" % ( issue.key, issue.fields.customfield_11502, bug.product ) )
						       update = True
						   if issue.fields.customfield_11503 != None and bug.component != "" and issue.fields.customfield_11503 != bug.component:
						       print ("%s : Upstream Component field value of '%s' did not match '%s'" % ( issue.key, issue.fields.customfield_11503, bug.component ) )
						       update = True
						   if issue.fields.customfield_11504 != None and bug.status != "" and issue.fields.customfield_11504 != bug.status:
						       print ("%s : Upstream status field value of '%s' did not match '%s'" % ( issue.key, issue.fields.customfield_11504, bug.status ) )
						       update = True
						   if issue.fields.customfield_11505 != None and bug.resolution != "" and issue.fields.customfield_11505 != bug.resolution:
						       print ("%s : Upstream resolution field value of '%s' did not match '%s'" % ( issue.key, issue.fields.customfield_11505, bug.resolution ) )
						       update = True
						   if issue.fields.customfield_11600 != None and bug.version != "" and issue.fields.customfield_11600 != bug.version:
						       print ("%s : Upstream version field value of '%s' did not match '%s'" % ( issue.key, issue.fields.customfield_11600, bug.version ) )
						       update = True
						   if issue.fields.customfield_11700 != BASE_URL + '/show_bug.cgi?id=' + str(bug.id):
						       print ("%s : Upstream URL field '%s' did not match '%s'" % ( issue.key, issue.fields.customfield_11700, BASE_URL + '/show_bug.cgi?id=' + str(bug.id)))
						       update = True

						   existingVersions = []
						   foundVersion = False
						   for version in issue.fields.versions:
						       existingVersions.append({"name" : version.name})
						       if version.name == JIRA_VERSION:
						           foundVersion = True

						   if not foundVersion :
						       print ("%s : did not contain version %s" % (issue.key, JIRA_VERSION))
						       existingVersions.append({"name" : JIRA_VERSION})
						       update = True

						   existingComponents = []
						   foundComponent = False
						   for component in issue.fields.components:
						       existingComponents.append({"name" : component.name})
						       if component.name == JIRA_COMPONENT:
						           foundComponent = True

						   if not foundComponent :
						       print ("%s : did not contain Component %s" % (issue.key, JIRA_COMPONENT))
						       existingComponents.append({"name" : JIRA_COMPONENT})
						       update = True

						   if update :
						       print ("Updating %s with upstream bug contents" % (issue.key))
						       bug_comments=bug.getcomments()
						       fields={ 'summary'          : bug.summary,
						                'description'      : bug_comments[0]['text'],
						                'customfield_11500': str(bug.id),                # 'Upstream Bug ID'
						                'customfield_11502': str(bug.product),           # 'Upstream Product'
						                'customfield_11503': str(bug.component),         # 'Upstream Component'
						                'customfield_11504': str(bug.status),            # 'Upstream Status'
						                'customfield_11505': str(bug.resolution),        # 'Upstream Resolution'
						                'customfield_11600': str(bug.version),           # 'Upstream Version'
						                'customfield_11700': BASE_URL + '/show_bug.cgi?id=' + str(bug.id), # 'Upstream URL'
						                #'customfield_11501': str(bug.project),           # 'Upstream Project'
						                'components': existingComponents,
						                'versions': existingVersions}
						       jira.transition_issue(issue, 'In Review', fields, notify=False)
						   foundIssue = True
						   break

				 if not foundIssue:
					  bug_comments=bug.getcomments()

					  # Create a new issue in JIRA
					  new_issue = { 'project'    : { 'key': 'JIRATEST'},
						       'issuetype'        : {'name': 'Bug'},
						       'summary'          : bug.summary,
						       'description'      : bug_comments[0]['text'],
						       'customfield_11500': str(bug.id),                # 'Upstream Bug ID'
						       'customfield_11502': str(bug.product),           # 'Upstream Product'
						       'customfield_11503': str(bug.component),         # 'Upstream Component'
						       'customfield_11504': str(bug.status),            # 'Upstream Status'
						       'customfield_11505': str(bug.resolution),        # 'Upstream Resolution'
						       'customfield_11600': str(bug.version),           # 'Upstream Version'
						       'customfield_11700': BASE_URL + '/show_bug.cgi?id=' + str(bug.id), # 'Upstream URL'
						       #'customfield_11501': str(bug.project),           # 'Upstream Project'
						       'components': [{'name': JIRA_COMPONENT}],
						       'versions': [{'name': JIRA_VERSION}],
						       }
					  
					  print ("Copying bug id %s information to create in a batch" % (bug.id))
					  new_issues_list.append( new_issue )
				 if len(new_issues_list) > 99:
					  # Create a batch of new issues in JIRA
					  print ("Creating %s new issues\n" % (len(new_issues_list)))
					  new_jira_issues = jira.create_issues ( field_list=new_issues_list, prefetch=False )
					  del new_issues_list[:]

			# Create new issue(s) in JIRA
			if len(new_issues_list) > 0:
				 print ("Creating %s new issues\n" % (len(new_issues_list)))
				 new_jira_issues = jira.create_issues ( field_list=new_issues_list, prefetch=False )
		else: ## for github
			# Upstream Repository
			BASE_URL = 'https://api.github.com/repos/openssl/openssl'
			# Add the query to the base URL
			GH_URL = BASE_URL + '/issues?per_page=100&labels=' + UPSTREAM_VERSION

			# Grab bugs from the GH_URL
			print("Querying '%s' upstream project for bugs that apply to %s" % (JIRA_COMPONENT, JIRA_VERSION))
			t1 = time.time()

			# Upstream issues list
			u_issues = []

			while GH_URL:
				 r = requests.get(GH_URL)

				 if(r.ok):
					  new_issues = json.loads(r.text or r.content)
					  u_issues += new_issues
					  if r.links.has_key('next'):
						   GH_URL = r.links['next']['url']
					  else:
						   GH_URL = None
				 else:
					  print ('Request failed = %s' % ( pprint.pformat(vars(r))))

			t2 = time.time()
			print("Found %s upstream issues with the upstream query" % ( len(u_issues)))
			print("Query processing time: %s" % (t2 - t1))
			#print("\nu_issues:\n%s\n" % pprint.pformat(u_issues))

			# Load all similar issues from JIRA for later searching
			j_issues = jira.search_issues('project=JIRATEST AND component in ("'+JIRA_COMPONENT+'")', maxResults=100)
			while len(j_issues) < j_issues.total:
				 j_issues += jira.search_issues('project=JIRATEST AND component in ("'+JIRA_COMPONENT+'")', startAt=len(j_issues), maxResults=100)
			j_issues = sorted (j_issues, key=lambda j: j.fields.customfield_11500)

			new_issues_list = []

			# Search JIRA issues for each upstream issue found
			for u_issue in u_issues:
				 foundIssue = False

				 # Search the previously downloaded upstream issues
				 # For now, just search for the upstream issue number in each j_issue.
				 matching_jira_issues = [j_issue for j_issue in j_issues if j_issue.fields.customfield_11500 == str(u_issue['number'])]

				 for j_issue in matching_jira_issues:
					  if str(j_issue.fields.customfield_11500) == str(u_issue['number']):
						   print("Found %s with upstream issue number %s" % (j_issue.key, j_issue.fields.customfield_11500) )
						   update = False

						   # Validate the existing jira issue fields match with the upstream issue
						   if j_issue.fields.customfield_11504 != None and u_issue['state'] != "" and j_issue.fields.customfield_11504 != u_issue['state']:
						       print ("%s : Upstream state field value of '%s' did not match '%s'" % ( j_issue.key, j_issue.fields.customfield_11504, u_issue['state'] ) )
						       update = True
						   if j_issue.fields.customfield_11700 != str(u_issue['html_url']):
						       print ("%s : Upstream URL field '%s' did not match '%s'" % ( j_issue.key, j_issue.fields.customfield_11700, str(u_issue['html_url'])))
						       update = True

						   existingVersions = []
						   foundVersion = False
						   for version in j_issue.fields.versions:
						       existingVersions.append({"name" : version.name})
						       if version.name == JIRA_VERSION:
						           foundVersion = True

						   if not foundVersion :
						       print ("%s : did not contain version %s" % (j_issue.key, JIRA_VERSION))
						       existingVersions.append({"name" : JIRA_VERSION})
						       update = True

						   existingComponents = []
						   foundComponent = False
						   for component in j_issue.fields.components:
						       existingComponents.append({"name" : component.name})
						       if component.name == JIRA_COMPONENT:
						           foundComponent = True

						   if not foundComponent :
						       print ("%s : did not contain Component %s" % (j_issue.key, JIRA_COMPONENT))
						       existingComponents.append({"name" : JIRA_COMPONENT})
						       update = True

						   if update :
						       print ("Updating %s with upstream issue contents" % (j_issue.key))
						       fields={ 'summary'          : str(u_issue['title']),
						                #'description'      : u_issue['body'],
						                'customfield_11500': str(u_issue['number']),     # 'Upstream issue ID'
						                'customfield_11504': str(u_issue['state']),      # 'Upstream Status'
						                'customfield_11700': str(u_issue['html_url']),        # 'Upstream URL'
						                'components'       : existingComponents,
						                'versions'         : existingVersions}
						       jira.transition_issue(j_issue, 'In Review', fields, notify=False)
						   foundIssue = True
						   break

				 if not foundIssue:
					  # Create a new issue in JIRA
					  new_issue = { 'project'    : { 'key': 'JIRATEST'},
						       'issuetype'        : {'name': 'Bug'},
						       'summary'          : str(u_issue['title']),
						       'customfield_11500': str(u_issue['number']),     # 'Upstream issue ID'
						       'customfield_11504': str(u_issue['state']),      # 'Upstream Status'
						       'customfield_11700': str(u_issue['html_url']),        # 'Upstream URL'
						       'components'       : [{'name': JIRA_COMPONENT}],
						       'versions'         : [{'name': JIRA_VERSION}],
						       }
					  
					  print ("Copying issue number %s information to create in a batch" % (str(u_issue['number'])))
					  new_issues_list.append( new_issue )
				 if len(new_issues_list) > 99:
					  # Create a batch of new issues in JIRA
					  print ("Creating %s new issues\n" % (len(new_issues_list)))
					  new_jira_issues = jira.create_issues ( field_list=new_issues_list, prefetch=False )
					  del new_issues_list[:]

			# Create new issue(s) in JIRA
			if len(new_issues_list) > 0:
				 print ("Creating %s new issues\n" % (len(new_issues_list)))
				 new_jira_issues = jira.create_issues ( field_list=new_issues_list, prefetch=False )
