# This is a one-off program to get all module information into json
# format.
#
# Modules will be stored as objects with these fields:
#  - name
#  - id
#  - code
#  - year (float)
#  - term (int)
#  - syllabus filename
#  - url
#  - pathways (list of strings naming the pathways the module belongs
#    to, don't bother with y1y2)
#  - is it running (bool)
#  - prereqs (list of (text, type) pairs. If type is "needed" or
#    "recommended" then text should be a code)
#  - ancillary (bool)
#
# Also, eliminate the use of "id" and replace it with the module code

import json
import xml.etree.ElementTree as ET

########################################################
# Parse modules.xml into a dict of module dictionaries #
########################################################

modulesRoot = ET.parse('modules.xml').getroot()

urlPrefix = ""
pfxElt = modulesRoot.find("linkprefix")
if pfxElt:
    urlPrefix = pfxElt.text

def safeFind(element, name):
    # Call element.find(name). If the find succeeds, return its text.
    # Otherwise return an empty string.
    # Aim was to avoid annoying pyright errors...
    tryFind = element.find(name)
    if tryFind is not None:
        return tryFind.text
    else:
        return ""

ancillaryModules = ['MATH0012', 'MATH0039', 'MATH0040', 'MATH0041',
        'MATH0042', 'MATH0043', 'MATH0045', 'MATH0046', 'MATH0047',
        'MATH0048', 'MATH0049', 'MATH0050', 'MATH0100', 'MATH0101',
        'MATH0103'] 

modules = {}
idToCode = {}
y1y2Pathway = []

for moduleElement in modulesRoot.iter("module"):
    # Fill out the module dict
    modDict = {}
    modDict["id"] = moduleElement.get("id")
    modDict["url"] = ""
    modDict["name"] = safeFind(moduleElement, "name")
    modDict["code"] = moduleElement.find("code").find("current").text
    modDict["year"] = float(safeFind(moduleElement, "year"))  # not int,
    # e.g. it could be 3.5 for "years 3 and 4"
    modDict["term"] = int(safeFind(moduleElement, "term"))
    modDict["syllabusFilename"] = safeFind(moduleElement, "syllabus")
    modDict["isRunning"] = True

    modDict["pathways"] = []
    if modDict["year"] <= 2:
        modDict["pathways"].append("y1y2")
        y1y2Pathway.append(modDict["code"])

    modDict["prereqs"] = []
    prereqs = moduleElement.find("prerequisites")
    for prereq in prereqs.iter("prerequisite"):
        modDict["prereqs"].append([prereq.text, prereq.get('type')])
        # prereq.text is an id, not a code, so this is a list of (id,
        # type) pairs
    # One module has a comment tag inside prereqs
    for commentElement in prereqs.iter("comment"):
        modDict["prereqs"].append([commentElement.text, "comment"])

    modDict["ancillary"] = modDict["code"].upper() in ancillaryModules

    modules[modDict["code"]] = modDict
    idToCode[modDict["id"]] = modDict["code"]

########################################################
# Make modDict["prereqs"] a list of [code, type] pairs #
########################################################

for code, modDict in modules.items():
    for p in modDict["prereqs"]:
        if p[1] in ["needed", "recommended"]:
            p[0] = idToCode[p[0]]

####################################################
# Parse pathways.xml; add pathways to module dicts #
####################################################

pathways = {"First and Second Year": y1y2Pathway}

pathwaysRoot = ET.parse("pathways.xml").getroot()
for pathwayElement in pathwaysRoot.iter("pathway"):
    pathwayId = pathwayElement.get("id") # e.g. algebra
    pathwayName = pathwayElement.get("name") # e.g. Algebra

    if pathwayId == "y1y2":
        continue
    else:
        contents = []
        for modIdElement in pathwayElement.findall("includedmodule"):
            code = idToCode[modIdElement.text]
            contents.append(code)
            modules[code]["pathways"].append(pathwayName)
        pathways[pathwayName] = contents


#################################################
# Write the dict of module dicts to a json file #
#################################################

f = open("modules.json", "w") #, "x")
json.dump(modules, f, indent=4) # indent makes the file human-readable
f.close()

#############################################
# Write the dict of pathways to a json file #
#############################################

f = open("pathways.json", "w")#, "x")
json.dump(pathways, f, indent=4)
f.close()
