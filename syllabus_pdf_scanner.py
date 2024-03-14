# Download all syllabus pdf files from the UCL website.
# Scrape year and term data out of them using PyPDF2
# Update modules.json with any changes.

import json
import requests
from PyPDF2 import PdfReader
from time import sleep

SYLLABUS_PATH = "/home/mjt/Downloads/syllabuses/"


def downloadSyllabus(module):
    url = module["url"]
    filename = module["syllabusFilename"]
    r = requests.get(url, allow_redirects=True)
    with open(SYLLABUS_PATH + filename, "wb") as pdfFile:
        pdfFile.write(r.content)


def getAllSyllabuses():
    with open("modules.json") as f:
        modules = json.load(f)
    n = len(modules)
    for i, module in enumerate(modules.values()):
        print(
            "Fetching " + modules["syllabusFilename"] +
            "\t" + str(i) + " of " + str(n)
        )
        downloadSyllabus(module)
        sleep(10)  # don't get rate-limited


def getTermFromSyllabus(filename):
    # input is the filename of a pdf syllabus
    reader = PdfReader(filename)
    firstPage = reader.pages[0]
    text = firstPage.extract_text().splitlines()
    # try the first 10 lines, say, for term info
    term = -1
    for line in text[:10]:
        if "Term" in line:
            if "1" in line:
                term = 1
            elif "2" in line:
                term = 2
    if term == -1:
        print("Failed to extract term info from\n")
        print(text[:10])
        print("\n")
    return term


def getYearFromSyllabus(filename):
    reader = PdfReader(filename)
    firstPage = reader.pages[0]
    text = firstPage.extract_text().splitlines()
    year = -1
    for line in text[:10]:
        if "Normal s" in line:  # Normal student group(s)
            if "1" in line:
                year = 1
            elif "2" in line and "3" in line:
                year = 2.5
            elif "2" in line:
                year = 2
            elif "3" in line and "4" in line:
                year = 3.5
            elif "3" in line:
                year = 3
            elif "4" in line:
                year = 4
    if year == -1:
        print("Failed to extract year info from\n")
        print(text[:10])
        print("\n")
    return year


def updateTermInfo():
    with open("modules.json") as f:
        modules = json.load(f)
    for module in modules.values():
        t = getTermFromSyllabus(SYLLABUS_PATH + module["syllabusFilename"])
        if t != module["term"]:
            print(
                "Changing "
                + module["code"]
                + " from term "
                + str(module["term"])
                + " to term "
                + str(t)
            )
            module["term"] = t
    print("Writing out modules.json.")
    with open("modules.json", "w") as f:
        json.dump(modules, f, indent=4)
        # indent makes the file human-readable


def updateYearInfo():
    with open("modules.json") as f:
        modules = json.load(f)
    for module in modules.values():
        y = getYearFromSyllabus(SYLLABUS_PATH + module["syllabusFilename"])
        if (y != -1) and (y != module["year"]):
            print(
                "Changing "
                + module["code"]
                + " from year "
                + str(module["year"])
                + " to year "
                + str(y)
            )
            module["year"] = y
    print("Writing out modules.json")
    with open("modules.json", "w") as f:
        json.dump(modules, f, indent=4)


# typical text_extract output
#   MATH0038 ...
#   Year: 2022–2023
#   Code: MATH0038
#   Level: 6 (UG)
#   Normal student group(s): UG Year 3 Mathematics degrees
#   Value: 15 credits (= 7.5 ECTS credits)
#   Term: 2
#   Assessment: 80% exami...
