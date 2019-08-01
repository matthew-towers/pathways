#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul 24 21:52:52 2019

@author: mjt

Scrape links from UCL maths module site.

Parse modules.xml with xml.etree.ElementTree

https://docs.python.org/3/library/xml.etree.elementtree.html

then output a markdown file containing tables of prerequisites suitable for
processing with Jekyll.

Markdown syntax:

| Module | Prerequisites
|-----|----
|<a id="math0000id"></a>MATH0000 Math for A | <a href="#math0001id">MATH0001</a>, ...
|<a id="math0001id"></a>MATH0001 Math for B | <a href="#math0002id">MATH0002</a>, ...

|Module | Prerequisites
|-----|----
|MATH9999 Math for X | <a href="#row1">MATH0000</a>
|MATH9óò9 Math for Y | <a href="#row2">MATH0001</a>
|<a id="module id tag"></a> <a href="url for syllabus"> <code/current> <name> </a> | <a href="#module id tag"> <name of prerequisite> </a> (recommended|"")


In modules.xml:

<modules id="all">
  <module id="spectraltheory" ects="7.5">
    <name>Spectral Theory</name>
    <year>4</year>
    <term>1</term>
    <syllabus>math0071.pdf</syllabus>
    <code>
      <old>MATHM111</old>
      <current>MATH0071</current>
    </code>
    <prerequisites>
      <prerequisite type="needed">functionalanalysis</prerequisite>
      <prerequisite type="needed">multivariableanalysis</prerequisite>
      <prerequisite type="recommended">measuretheory</prerequisite>
    </prerequisites>
  </module>
</modules>

Year has 3.5 to mean "3 or 4".  Year 2 term 2 courses are "2 or 3"

In pathways.xml:

<pathways>
  <pathway id="y1y2" name="First and Second Year" startfromyear="1" startfromterm="1"/>

  <pathway id="algebra" name="Algebra" startfromyear="2" startfromterm="2">
    <includedmodule>algebra4</includedmodule>
    <includedmodule>commutativealgebra</includedmodule>
    <includedmodule>galoistheory</includedmodule>
    <includedmodule>algebraicgeometry</includedmodule>
    <includedmodule>representationtheory</includedmodule>
    <includedmodule>ellipticcurves</includedmodule>
    <includedmodule>algebraicnumbertheory</includedmodule>
    <includedmodule>primenumbersandtheirdistributions</includedmodule>
    <includedmodule>historyofmathematics</includedmodule>
    <includedmodule>liegroupsandliealgebras</includedmodule>
    <includedmodule>algebraictopology</includedmodule>
    <includedmodule>algebraicgeometry</includedmodule>
    <includedmodule>logic</includedmodule>
  </pathway>
</pathways>
"""
from bs4 import BeautifulSoup
import requests
import xml.etree.ElementTree as ET

###################################################################
# Get filenames from the UCL maths module webpage                 #
# They keep changing them, so we can't rely on what's in the xml  #
###################################################################

url = 'https://www.ucl.ac.uk/maths/current-students/current-undergraduates/module-information-undergraduates'
page = requests.get(url)
soup = BeautifulSoup(page.text, 'lxml')  # open("mod_info.html").read()
spans = soup.find_all('span')

codeToFile = {}

for s in spans:
    if s.find('a') is not None:
        filename = s.find('a')['href'].split('/')[-1]
        moduleCode = filename.split('_')[0] if '_' in filename else filename.split('.')[0]
        codeToFile[moduleCode.upper()] = filename

# Now codeToFile is a dict with moduleId as keys and filenames as values
# all the keys are upper cased since that's how they're named in the xml

##########################
# Now build the markdown #
##########################

root = ET.parse('modules.xml').getroot()

urlprefix = root.find('linkprefix').text

# ElementTree has two classes: Element, a node in the doc tree, and ElementTree
# which is the whole tree.
#
# Element has methods for iterating recursively on the subtree below it
# for module in root.iter('module')

modules = {}
# modules will be a dict whose keys are module ids.
# modules[id] will be a dict containing all the info about the module

for module in root.iter('module'):
    modDict = {}
    modDict["name"] = module.find('name').text
    modDict["code"] = module.find('code').find('current').text
    modDict["year"] = float(module.find('year').text)
    modDict["term"] = int(module.find('term').text)
    modDict["syllFile"] = module.find('syllabus').text

    prereqs = module.find('prerequisites')
    modDict["prereqs"] = [(prereq.text, prereq.get('type')) for prereq in prereqs]
    modules[module.get('id')] = modDict


y1y2modules = [id for id in modules.keys() if modules[id]["year"] <= 2]
# there's no list in pathways.xml, and the xsl file just filters all the
# modules with year 1 or 2

pathways = []
# pathways is a list of the pathways
# a pathway will be a tuple (name, contents)
# where name is the pathway name
# and contents is a list of module ids.

pathwayroot = ET.parse('pathways.xml').getroot()
for pathway in pathwayroot.iter('pathway'):
    pathwayId = pathway.get('id')
    pathwayName = pathway.get('name')

    if pathwayId == 'y1y2':
        pathways.append((pathwayName, y1y2modules))
    else:
        contents = [modId.text for modId in pathway.findall('includedmodule')]
        pathways.append((pathwayName, contents))

markdownOutput = """---
layout: page
title: UCL Pathways
permalink: /pathways/
---

"""


def tablify(moduleList):
    # return a string containing a markdown table of the prereqs of the modules
    # in moduleList
    header = "| Module | Year | Term | Prerequisites\n|----|----|----|----\n"
    # sort the module list by year then term. Remember to deal with 3.5
    moduleList = sorted(moduleList, key=lambda modid: modules[modid]["term"])
    moduleList = sorted(moduleList, key=lambda modid: modules[modid]["year"])
    # this works because Python sorts are guaranteed to be "stable": they don't
    # change the order of things with the same key, see
    # https://docs.python.org/3/howto/sorting.html#sort-stability-and-complex-sorts
    rows = ""
    for modId in moduleList:
        rows += tableRow(modId)
    return header + rows


def tableRow(modId):
    moddict = modules[modId]
    # create the row of the table corresponding to modId

    if moddict['code'] in codeToFile.keys():
        filename = codeToFile[moddict['code']]
    else:
        print(modId, "not found on the scraped module webpage")
        filename = moddict["syllFile"]

    moduleCol = '<a id="' + modId + '"></a>' + '[' + moddict["code"] + ' ' + moddict["name"] + '](' + urlprefix + filename + ')'
    yearCol = "3 or 4" if moddict["year"] == 3.5 else str(int(moddict["year"]))
    termCol = str(moddict["term"])
    prereqsCol = ""
    for prereqId, prereqType in moddict["prereqs"]:
        # append prereq code, name, link to prereqsCol, whether it's optional
        if prereqType is None:
            prereqsCol += prereqId + ', '
        elif prereqType == "needed":
            pd = modules[prereqId]
            prereqsCol += '<a href="#' + prereqId + '">' + pd["code"] + ' ' + pd["name"] + '</a>, '
        else:
            pd = modules[prereqId]
            prereqsCol += '<a href="#' + prereqId + '">' + pd["code"] + ' ' + pd["name"] + '</a> (recommended), '
    return '|' + moduleCol + ' | ' + yearCol + ' | ' + termCol + ' | ' + prereqsCol[:-2] + '\n'


for pathwayName, pathwayContents in pathways:
    # generate the table, append it to markdownOutput
    markdownOutput += "## " + pathwayName + "\n\n" + tablify(pathwayContents) + '\n'

f = open("pathways.md", "w")
f.write(markdownOutput)
f.close()
