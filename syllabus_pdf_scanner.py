# Download all syllabus pdf files from the UCL website.
# Scrape year and term data out of them using PyPDF2 (now badly out of date)
# Update modules.json with any changes.

import json
import math
import requests
from PyPDF2 import PdfReader
from time import sleep
import os

SYLLABUS_PATH = "/home/mjt/Downloads/syllabuses/"


def download_syllabus(module):
    url = module["url"]
    filename = module["syllabus_filename"]
    r = requests.get(url, allow_redirects=True)
    with open(SYLLABUS_PATH + filename, "wb") as pdfFile:
        pdfFile.write(r.content)


def get_all_syllabuses():
    with open("modules.json") as f:
        modules = json.load(f)
    n = len(modules)
    for i, module in enumerate(modules.values()):
        print(
            "Fetching " + modules["syllabus_filename"] + "\t" + str(i) + " of " + str(n)
        )
        download_syllabus(module)
        sleep(10)  # don't get rate-limited


def get_term_from_syllabus(filename):
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


def get_year_from_syllabus(filename):
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


def update_term_info():
    with open("modules.json") as f:
        modules = json.load(f)
    for module in modules.values():
        t = get_term_from_syllabus(SYLLABUS_PATH + module["syllabus_filename"])
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
        json.dump(modules, f, indent=2)
        # indent makes the file human-readable


def update_year_info():
    with open("modules.json") as f:
        modules = json.load(f)
    for module in modules.values():
        y = get_year_from_syllabus(SYLLABUS_PATH + module["syllabus_filename"])
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
        json.dump(modules, f, indent=2)


def create_new_module_from_pdf(pdffile):
    # take a pdf file, return a module dict
    # module dict keys: name code year term syllabus_filename
    # prereqs ancillary url is_running group=""
    module = {}
    module["code"] = pdffile.name[:8].upper()
    reader = PdfReader(pdffile)
    first_page = reader.pages[0]
    text = first_page.extract_text().splitlines()
    module["name"] = text[0].split(maxsplit=1)[-1]
    module["term"] = 0
    module["level"] = 0
    module["syllabus_filename"] = pdffile.name
    module["prereqs"] = []
    module["ancillary"] = True
    module["group"] = ""
    module["is_running"] = True
    module["url"] = (
        "https://www.ucl.ac.uk/maths/sites/maths/files/" + module["syllabus_filename"]
    )
    for i in range(1, 12):
        line = text[i]
        if "Term:" in line:
            if "1" in line:
                module["term"] = 1
            elif "2" in line:
                module["term"] = 2
        if "Level:" in line:
            if "4" in line:
                module["level"] = 4
            elif "5" in line:
                module["level"] = 5
            elif "6" in line:
                module["level"] = 6
        if "Normal P" in line:
            prereqs = line.split(": ")[-1]
            module["prereqs"].append([prereqs, "needed"])
    module["year"] = module["level"] - 3
    return module


def scan_files_and_update_modules_json():
    with open("modules.json") as f:
        modules = json.load(f)  # keyed by code
    for file in os.scandir():
        filename = file.name
        # continue
        if filename.endswith(".pdf"):
            print(f"scanning {filename}...")
            with open(filename, "rb") as f:
                mod = create_new_module_from_pdf(f)
                modules[mod["code"]] = mod

    with open("modules.json", "w") as f:
        json.dump(modules, f, indent=2)


def add_level_info():
    with open("modules.json") as f:
        modules = json.load(f)
    for mod in modules.values():
        mod["level"] = math.ceil(mod["year"]) + 3
    with open("modules.json", "w") as f:
        json.dump(modules, f, indent=2)


def add_syllabus_filename():
    with open("modules.json") as f:
        modules = json.load(f)
    for mod in modules.values():
        if "syllabus_filename" not in mod:
            mod["syllabus_filename"] = mod["url"].split("/")[-1]
    with open("modules.json", "w") as f:
        json.dump(modules, f, indent=2)


# must open pdf files with (filename, 'rb')
#
# typical text_extract output
#   MATH0038 ...
#   Year: 2022–2023
#   Code: MATH0038
#   Level: 6 (UG)
#   Normal student group(s): UG Year 3 Mathematics degrees
#   Value: 15 credits (= 7.5 ECTS credits)
#   Term: 2
#   Assessment: 80% exami...
