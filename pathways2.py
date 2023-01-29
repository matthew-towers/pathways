# Pathways: new version

# TODO:
# - [x] open modules.json.  Parse it into a dict of code:Module pairs.
# - [x] unless a dont-scrape option was passed, scrape the webpage and
# get which modules are present and their
# filenames
# - [x] (unless...) Update filenames in the code:Module dict. If modules not on
# web, mark as not running. If we
# have filenames for modules not in the json file, warn about this. We
# can't actually create the Module object because we can't get year,
# term, etc. Print messages saying what's happening
# - [x] (unless...) update modules.json (converting from Module objects
# to dicts)
# - [x] build the big prereq graph in networkx
# - [x] assert that it's a dag
# - [x] open and parse pathways.json
# - [ ] for each pathway,
#     - [x] get the nodes corresp to modules tagged with that pathway
#     - [x] use networkx ancestors to augment with prereqs
#     - [x] convert to a list and sort by year and term
#     - [x] build a graphviz svg
#     - [x] build a markdown table
#     - [ ] make networkx subgraphs
#     - [ ] build a d3js fancy graph
# - [x] create and write out the full markdown file
# - [x] create and write out the full html file
# - [ ] create fancy webpage with fancy graphs

# - [ ] fix term and year info by reading pdf files with PyPDF2
# - [ ] deal with non-running modules
# - [ ] push to github
# - [x] explain that y-axis in the html file is time

import json
from bs4 import BeautifulSoup
import requests
import sys
import networkx as nx
import graphviz as gv

SCRAPE = False

MODULE_INFO_URL = "https://www.ucl.ac.uk/maths/current-students/current-undergraduates/module-information-undergraduates"

ANCILLARY_MODULES = [
    "MATH0012",
    "MATH0039",
    "MATH0040",
    "MATH0041",
    "MATH0042",
    "MATH0043",
    "MATH0045",
    "MATH0046",
    "MATH0047",
    "MATH0048",
    "MATH0049",
    "MATH0050",
    "MATH0100",
    "MATH0101",
    "MATH0103",
]

##########################################
# Class definitions and helper functions #
##########################################


class Module:
    def __init__(
        self, name, code, year, term, syllFile, prereqs, ancillary, url, running
    ):
        self.name = name
        self.code = code
        self.year = year
        self.term = term
        self.syllFile = syllFile
        self.prereqs = prereqs
        self.ancillary = ancillary
        self.url = url
        self.isRunning = running

    def toDict(self):
        return {
            "name": self.name,
            "code": self.code,
            "year": self.year,
            "term": self.term,
            "syllabusFilename": self.syllFile,
            "prereqs": self.prereqs,
            "ancillary": self.ancillary,
            "url": self.url,
            "isRunning": self.isRunning,
        }

    @classmethod
    def dictToModule(cls, m):
        # convert a module dict, as parsed from json, to a Module
        # receives Module class as a first argument
        return cls(
            m["name"],
            m["code"],
            m["year"],
            m["term"],
            m["syllabusFilename"],
            m["prereqs"],
            m["ancillary"],
            m["url"],
            m["isRunning"],
        )



class Pathway:
    def __init__(self, name, modules):
        self.name = name
        self.modules = modules

    def add_module(self, module):
        self.modules.append(module)



######################
# Parse modules.json #
######################


with open("modules.json") as f:
    modulesFromJson = json.load(f)

modules = {}
for code, modDict in modulesFromJson.items():
    modules[code] = Module.dictToModule(modDict)

##################################################
# Scrape filenames from the web, update modules  #
# Remember which modules had their url changed   #
# Mark modules not on the webpage as not running #
##################################################

if SCRAPE:
    print("trying to download ucl modules webpage...")

    try:
        page = requests.get(MODULE_INFO_URL)
        page.raise_for_status()  # raise exception if an http error is returned
    except requests.exceptions.HTTPError as e:
        print(e)
        sys.exit(1)  # just give up
    except requests.exceptions.Timeout as e:
        print(e)
        sys.exit(1)  # just give up
    except requests.exceptions.RequestException as e:
        print(e)
        sys.exit(1)  # just give up

    print("success!")
    print("trying to parse the webpage with BS...")

    try:
        soup = BeautifulSoup(page.text, "lxml")  # open("mod_info.html").read()
    except Exception as e:
        print(e)
        sys.exit(1)

    print("success!")

    # The UCL CMS puts every syllabus file link in a span
    spans = soup.find_all("span")
    modulesOnWebPage = set()

    for s in spans:
        a = s.find("a")
        if a is not None:
            # this a holds a link to a module syllabus
            module_url = a["href"]
            filename = module_url.split("/")[-1]
            moduleCode = (
                filename.split("_")[0] if "_" in filename else filename.split(".")[0]
            )
            moduleCode = moduleCode.upper()
            modulesOnWebPage.add(moduleCode)

            if moduleCode in modules:
                modules[moduleCode].url = module_url
                modulesFromJson[moduleCode]["url"] = module_url
                modules[moduleCode].syllFile = filename
                modulesFromJson[moduleCode]["syllabusFilename"] = filename
            elif moduleCode not in ANCILLARY_MODULES:
                print(
                    "Found non-ancillary module on web not in modules.json: "
                    + moduleCode
                )

    for moduleCode in modules:
        if moduleCode not in modulesOnWebPage:
            print(moduleCode + " not on webpage, setting it to not running.")
            modules[moduleCode].isRunning = False
            modulesFromJson[moduleCode]["isRunning"] = False


#####################################
# Write any changes to modules.json #
#####################################

with open("modules.json", "w") as f:
    # indent makes the file human-readable
    json.dump(modulesFromJson, f, indent=4)

#####################################
# Build networkX prerequisite graph #
#####################################

prereqGraph = nx.DiGraph()
prereqGraph.add_nodes_from(modules)
# prereqGraph is a graph whose nodes are the module codes

for code, module in modules.items():
    for prereqCode, prereqType in module.prereqs:
        if (prereqType == "needed") or (prereqType == "recommended"):
            prereqGraph.add_edge(prereqCode, code, object=prereqType)

assert nx.is_directed_acyclic_graph(prereqGraph)


#######################
# Parse pathways.json #
#######################

with open("pathways.json") as f:
    pathways = json.load(f)

# pathways is a {pathwayName: list of module codes} dictionary

############################
# Compute pathway closures #
############################

# Currently, some of the pathways aren't closed under taking
# prerequisites. We want them to be prerequisite-closed when we
# create our graphs.

pathwayClosures = {}

for pathwayName, pathway in pathways.items():
    pathwayClosure = set()
    for code in pathway:
        pathwayClosure.add(code)
        pathwayClosure.update(nx.ancestors(prereqGraph, code))
    pathwayClosures[pathwayName] = pathwayClosure

# When using graphviz, we want the pathway entries sorted by year then
# by term. That means turning the pathway sets into lists.

pathwayClosuresLists = {}

for pathwayName, moduleCodeSet in pathwayClosures.items():
    moduleCodeList = list(moduleCodeSet)
    moduleCodeList = sorted(moduleCodeList, key=lambda m: modules[m].term)
    moduleCodeList = sorted(moduleCodeList, key=lambda m: modules[m].year)
    # this works because Python sorts are guaranteed to be "stable": they don't
    # change the order of things with the same key, see
    # https://docs.python.org/3/howto/sorting.html#sort-stability-and-complex-sorts
    pathwayClosuresLists[pathwayName] = moduleCodeList


########################
# Make graphviz graphs #
########################

# Configure the colours we will use. The colours dict maps (year, term)
# to a graphviz colour name.

colours = {
    (1, 1): "orange",
    (1, 2): "orange",
    (2, 1): "green3",
    (2, 2): "green3",
    (2.5, 1): "cadetblue",
    (2.5, 2): "cadetblue",
    (3, 1): "brown1",
    (3, 2): "brown1",
    (3.5, 1): "deeppink",
    (3.5, 2): "deeppink",
    (4, 1): "midnightblue",
    (4, 2): "midnightblue",
}


def makeGraphVizGraph(pathwayName, pathwayContents):
    # take a pathway, as a list of module codes sorted by year and term.
    # Make an svg using graphviz and save it.
    print("building gv graph for " + pathwayName)
    pathwayGraph = gv.Digraph(
        filename=pathwayName,
        format="svg",
        node_attr={
            "shape": "box",
            "style": "filled,bold",
            "fillcolor": "white",
            "penwidth": "5",
        },
    )
    firstModule = modules[pathwayContents[0]]
    oldYear = firstModule.year
    oldTerm = firstModule.term
    currentSubGraph = gv.Digraph(str(oldYear) + " " + str(oldTerm))
    currentSubGraphNodes = []
    currentSubGraph.attr(rank="same")
    # NB: using currentSubGraph.graph_attr.update(rank='same') sets
    # everything in the whole graph to the same rank.
    for code in pathwayContents:
        module = modules[code]
        # are we starting a new year or term?  Then set everything to
        # the same rank.
        if (module.year != oldYear) or (module.term != oldTerm):
            # add the old subgraph to the big graph
            print("adding subgraph for year " + str(oldYear) + " term "
                    + str(oldTerm))
            pathwayGraph.subgraph(currentSubGraph)
            print(currentSubGraphNodes)
            # update oldYear and oldTerm
            oldYear = module.year
            oldTerm = module.term
            # make a new subgraph
            currentSubGraph = gv.Digraph(str(oldYear) + " " + str(oldTerm))
            currentSubGraphNodes = []
            currentSubGraph.attr(rank="same")
        # build label for current node
        label = module.code + "\n" + module.name
        # build url for current node
        url = module.url
        # add a node to the current subgraph
        currentSubGraph.node(
            code, label, color=colours[(module.year, module.term)], href=url
        )
        currentSubGraphNodes.append(module.code + " " + module.name)
        # build prereq edges
        for prereqCode, prereqType in module.prereqs:
            if prereqType == "comment":
                continue
            elif prereqType == "needed":
                pathwayGraph.edge(prereqCode, code)
            else:
                pathwayGraph.edge(prereqCode, code, style="dashed")
    # deal with last subgraph
    pathwayGraph.subgraph(currentSubGraph)
    print("adding subgraph for year " + str(oldYear) + " term "
            + str(oldTerm))
    print(currentSubGraphNodes, "\n")
    pathwayGraph.render()


# Build a graph for each pathway

for pathwayName, pathwayContents in pathwayClosuresLists.items():
    makeGraphVizGraph(pathwayName, pathwayContents)

#######################
# Build pathways.html #
#######################

# Layout:
#  - legend
#  - link to markdown version
#  - y1y2 pathway
#  - algebra pathway
#  - analysis pathway
#  - applied pathway
#  - modelling... pathway
# Remember to close the html tag

with open("pathways.html", "w") as htmlFile:
    # add the preamble
    preamble = open("preamble.html").read()
    htmlFile.write(preamble)
    htmlFile.write("\n")
    # add the pathway svgs, one by one
    for pathwayName in pathways:
        htmlFile.write("<h1>" + pathwayName + "</h1>\n")
        svg = open(pathwayName + ".svg").read()
        htmlFile.write(svg)
        htmlFile.write("\n")
    # close the html tag
    htmlFile.write("</html>")


#####################
# Build pathways.md #
#####################


def tablify(moduleList):
    """
    Return a string containing a markdown table of the prereqs of the
    modules in the list moduleList.
    """
    header = "| Module | Year | Term | Prerequisites\n|----|----|----|----\n"
    rows = ""
    for code in moduleList:
        rows += tableRow(modules[code])  # this is a fold...do it with functools
    return header + rows


def tableRow(module):
    """
    create and return the row of the prereqs table for the given module
    """

    moduleCol = (
        '<a id="'
        + module.code
        + '"></a>'
        + "["
        + module.code
        + " "
        + module.name
        + "]("
        + module.url
        + ")"
    )
    if module.year == 2.5:
        yearCol = "2 or 3"
    elif module.year == 3.5:
        yearCol = "3 or 4"
    else:
        yearCol = str(int(module.year))
    termCol = str(module.term)
    prereqsCol = ""
    for prereqCode, prereqType in module.prereqs:
        # append prereq code, name, link to prereqsCol, whether it's optional
        if prereqType == "comment":
            prereqsCol += prereqCode + ", "
        elif prereqType == "needed":
            prereqModule = modules[prereqCode]
            prereqsCol += (
                '<a href="#'
                + prereqCode
                + '">'
                + prereqCode
                + " "
                + prereqModule.name
                + "</a>, "
            )
        else:
            prereqModule = modules[prereqCode]
            prereqsCol += (
                '<a href="#'
                + prereqCode
                + '">'
                + prereqCode
                + " "
                + prereqModule.name
                + "</a> (recommended), "
            )
    return (
        "|"
        + moduleCol
        + " | "
        + yearCol
        + " | "
        + termCol
        + " | "
        + prereqsCol[:-2]
        + "\n"
    )


with open("pathways.md", "w") as mdFile:
    # add the preamble
    preamble = open("preamble.md").read()
    mdFile.write(preamble)
    mdFile.write("\n")
    # add the pathway tables, one by one
    for pathwayName, pathwayModules in pathways.items():
        pathwayModules = sorted(pathwayModules, key=lambda m: modules[m].term)
        pathwayModules = sorted(pathwayModules, key=lambda m: modules[m].year)
        mdFile.write("## " + pathwayName + "\n\n")
        mdFile.write(tablify(pathwayModules))
        mdFile.write("\n")
