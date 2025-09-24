# Pathways.

# TODO:
# - [ ] for each pathway build a d3js/pyvis fancy graph
# - [ ] scrape the syllabus/query the user for prereq, year, term data when a
# new module is found. (Can't really do the prereqs because they can be written
# weirdly)
# - [ ] deal with more complex prerequisites, e.g. 0119

import json
from bs4 import BeautifulSoup
import requests
import sys
import networkx as nx
import graphviz as gv
import re

args = sys.argv

if len(args) > 2:
    print("Too many arguments.")
    sys.exit(1)
elif len(args) == 2 and args[1] != "scrape":
    print("Bad argument.")
    sys.exit(1)
elif len(args) == 2 and args[1] == "scrape":
    SCRAPE = True
else:
    SCRAPE = False

if not SCRAPE:
    print("Not scraping.")

MODULE_INFO_URL = "https://www.ucl.ac.uk/mathematical-physical-sciences/maths/current-students/current-undergraduates/module-information-undergraduates"

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
        self, name, code, year, term, syllabus_filename, prereqs, ancillary,
        url, running=True, group=""
    ):
        self.name = name
        self.code = code
        self.year = year
        self.term = term
        self.syllabus_filename = syllabus_filename
        self.prereqs = prereqs
        self.ancillary = ancillary
        self.url = url
        self.is_running = running
        self.group = group

    def to_dict(self):
        return {
            "name": self.name,
            "code": self.code,
            "year": self.year,
            "term": self.term,
            "syllabus_filename": self.syllabus_filename,
            "prereqs": self.prereqs,
            "ancillary": self.ancillary,
            "url": self.url,
            "is_running": self.is_running,
            "group": self.group
        }

    @classmethod
    def dict_to_module(cls, m):
        # convert a module dict, as parsed from json, to a Module
        return cls(
            m["name"],
            m["code"],
            m["year"],
            m["term"],
            m["syllabus_filename"],
            m["prereqs"],
            m["ancillary"],
            m["url"],
            running=m["is_running"],
            group=m["group"]
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
    modules_from_json = json.load(f)

MODULES = {}
for code, mod_dict in modules_from_json.items():
    MODULES[code] = Module.dict_to_module(mod_dict)

##################################################
# Scrape filenames from the web, update MODULES  #
# Remember which modules had their url changed   #
# Mark modules not on the webpage as not running #
##################################################

if SCRAPE:
    print("Trying to download UCL modules webpage...")

    try:
        page = requests.get(MODULE_INFO_URL)
        page.raise_for_status()  # raise exception if http error is returned
    except requests.exceptions.HTTPError as e:
        print(e)
        sys.exit(1)
    except requests.exceptions.Timeout as e:
        print(e)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(e)
        sys.exit(1)

    print("Success!")
    print("Trying to parse the webpage with BS...")

    try:
        soup = BeautifulSoup(page.text, "lxml")
    except Exception as e:
        print(e)
        sys.exit(1)

    print("Success!")

    # The UCL CMS puts every syllabus file link in a span
    spans = soup.find_all("span")
    modules_on_web = set()
    for s in spans:
        a = s.find("a")
        if a is not None:
            # ...then "a" is a hyperlink to a syllabus pdf
            # with the link text being the module code then the name
            code_and_name = a.contents[0]  # e.g. "MATH0005 Algebra 1"
            # Get rid of non-breaking space u00a0
            code_and_name = code_and_name.replace(" ", " ")
            module_url = a["href"]
            filename = module_url.split("/")[-1]
            module_code_search = re.search(
                "(MATH|STAT)\\d{4}", code_and_name, re.IGNORECASE
            )
            if module_code_search is None:
                print(f"No code in {code_and_name}. Abandoning module.")
                continue
            else:
                module_code = module_code_search[0].upper()
                modules_on_web.add(module_code)
                module_name = code_and_name.split(" ", 1)[1]
                # Split at first space, assume this is the name
            if module_code in MODULES:
                MODULES[module_code].url = module_url
                modules_from_json[module_code]["url"] = module_url
                MODULES[module_code].syllabus_filename = filename
                modules_from_json[module_code]["syllabus_filename"] = filename
            elif module_code not in ANCILLARY_MODULES:
                print(
                    f"Non-ancillary module on web not in modules.json: {module_code}."
                )
                print("Creating a new record.")
                # Create a new entry for modules.json
                mod = Module(
                    module_name,
                    module_code,
                    0,
                    0,
                    filename,
                    [],
                    False,
                    module_url,
                    True,
                )  # can't get the true term, year, prereq info from here so just use blank values.
                MODULES[module_code] = mod
                modules_from_json[module_code] = mod.to_dict()

    for module_code in MODULES:
        if module_code not in modules_on_web:
            module_name = MODULES[module_code].name
            resp = input(f"{module_code} {module_name} not on webpage. Set to not running? y/N")
            if resp == "y":
                MODULES[module_code].is_running = False
                modules_from_json[module_code]["is_running"] = False


#####################################
# Write any changes to modules.json #
#####################################

# There can only be changes if we got new info from a web scrape.
if SCRAPE:
    print("Writing changes to modules.json...")
    with open("modules.json", "w") as f:
        json.dump(modules_from_json, f, indent=4)
        # indent=4 makes the file human-readable
    print("...done!")


#####################################
# Build networkX prerequisite graph #
#####################################

PREREQ_GRAPH = nx.DiGraph()
PREREQ_GRAPH.add_nodes_from(MODULES)
# prereqGraph is a graph whose nodes are the module codes
# Only running modules should be included

for code, module in MODULES.items():
    if module.is_running:
        for prereq_code, prereq_type in module.prereqs:
            if prereq_type in ["needed", "recommended"]:
                PREREQ_GRAPH.add_edge(prereq_code, code, object=prereq_type)

assert nx.is_directed_acyclic_graph(PREREQ_GRAPH)


#######################
# Parse pathways.json #
#######################

with open("pathways.json") as f:
    PATHWAYS = json.load(f)

# pathways is a {pathwayName: list of module codes} dictionary

############################
# Compute pathway closures #
############################

# Currently, some of the pathways aren't closed under taking
# prerequisites. We want them to be prerequisite-closed when we
# create our graphs. We must also be sure that only running modules are
# included in the pathways closures.

PATHWAY_CLOSURES = {}

for pathway_name, pathway in PATHWAYS.items():
    pathway_closure = set()
    for code in pathway:
        if MODULES[code].is_running:
            pathway_closure.add(code)
            pathway_closure.update(nx.ancestors(PREREQ_GRAPH, code))
    PATHWAY_CLOSURES[pathway_name] = pathway_closure

# When using graphviz, we want the pathway entries sorted by year then
# by term. That means turning the pathway sets into lists.

for pathway_name, module_code_set in PATHWAY_CLOSURES.items():
    module_code_list = list(module_code_set)
    module_code_list = sorted(module_code_list, key=lambda m: MODULES[m].term)
    module_code_list = sorted(module_code_list, key=lambda m: MODULES[m].year)
    # Python sorts are guaranteed to be "stable": they don't
    # change the order of things with the same key, see
    # https://docs.python.org/3/howto/sorting.html#sort-stability-and-complex-sorts
    PATHWAY_CLOSURES[pathway_name] = module_code_list


########################
# Make graphviz graphs #
########################

def displayyear(y):
    if y in [1, 2, 3, 4]:
        return str(int(y))
    else:
        return f"{int(y-0.5)} or {int(y+0.5)}"


def displayterm(t):
    if t in [1, 2, 3]:
        return str(int(t))
    else:
        return "1 and 2"


COLOURS = {
    # (year, term) : "colour"
    (1, 1): "darkgoldenrod1",
    (1, 2): "darkgoldenrod3",
    (1, 1.5): "darkgoldenrod2",
    (2, 1): "green1",
    (2, 2): "green2",
    (2, 1.5): "green3",
    (2.5, 1): "cadetblue1",
    (2.5, 2): "cadetblue2",
    (3, 1): "brown1",
    (3, 2): "brown3",
    (3.5, 1): "deeppink1",
    (3.5, 2): "deeppink3",
    (4, 1): "dodgerblue2",
    (4, 2): "dodgerblue3",
}


def make_gv_graph(pathway_name, pathway_contents):
    """pathway_contents should be a list of module codes sorted by year
    and term. The function will make an svg of the pathway using graphviz
    and save it."""
    pathway_graph = gv.Digraph(
        filename=pathway_name + ".dot",
        format="svg",
        node_attr={
            "shape": "box",
            "style": "filled,bold",
            "fillcolor": "white",
            "penwidth": "5",
        }
    )
    first_mod = MODULES[pathway_contents[0]]
    old_year = first_mod.year
    old_term = first_mod.term
    current_subgraph = gv.Digraph(str(old_year) + " " + str(old_term))
    current_subgraph_nodes = []
    current_subgraph.attr(rank="same")
    # NB using current_subgraph.graph_attr.update(rank="same") sets
    # everything in the whole graph to the same rank.
    for code in pathway_contents:
        module = MODULES[code]
        # Are we starting a new year or term?  Then set everything to
        # the same rank.
        if (module.year != old_year) or (module.term != old_term):
            # Add the old subgraph to the big graph
            pathway_graph.subgraph(current_subgraph)
            # Update old_year and old_term
            old_year = module.year
            old_term = module.term
            # Make a new subgraph
            current_subgraph = gv.Digraph(str(old_year) + " " + str(old_term))
            current_subgraph_nodes = []
            current_subgraph.attr(rank="same")
        # Build the label for the current node
        tooltip = f"Year {displayyear(module.year)}, term {displayterm(module.term)}"
        # label = module.code + "\n" + module.name
        # url = module.url
        # Add a node to the current subgraph
        current_subgraph.node(
            code,
            module.code + "\n" + module.name,  # node label
            tooltip=tooltip,
            color=COLOURS[(module.year, module.term)],
            href=module.url,
        )
        current_subgraph_nodes.append(module.code + " " + module.name)
        # build prereq edges
        for prereq_code, prereq_type in module.prereqs:
            if prereq_type == "needed":
                pathway_graph.edge(prereq_code, code,
                                   tooltip="required prerequisite")
            elif prereq_type == "recommended":
                pathway_graph.edge(prereq_code, code, style="dashed",
                                   tooltip="recommended prerequisite")
            elif prereq_type == "comment":
                pass
            else:
                print(f"Invalid prereq type: {module.code}")
    # deal with last subgraph
    pathway_graph.subgraph(current_subgraph)
    pathway_graph.render()


# Build a graph for each pathway

for pathway_name, pathway_contents in PATHWAY_CLOSURES.items():
    make_gv_graph(pathway_name, pathway_contents)

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

with open("pathways.html", "w") as html_file:
    # add the preamble
    preamble = open("preamble.html").read()
    html_file.write(preamble)
    html_file.write("\n")
    # add the pathway svgs, one by one
    for pathway_name in PATHWAYS:
        html_file.write(f"<h1>{pathway_name}</h1>\n")
        svg = open(pathway_name + ".dot.svg").read()
        html_file.write(svg)
        html_file.write("\n")
    # close the html tag
    html_file.write("</html>")


#####################
# Build pathways.md #
#####################


def tablify(module_list, include_group=True):
    """
    Return a string containing a markdown table of the prereqs of the
    running modules in the list module_list.
    """
    if include_group:
        header = "| Module | Year | Term | Group | Prerequisites\n|----|----|----|----|----\n"
    else:
        header = "| Module | Year | Term | Prerequisites\n|----|----|----|----\n"

    rows = "".join(generate_table_row(MODULES[code], include_group) for code in module_list if
                   MODULES[code].is_running)
    return header + rows


def generate_table_row(module, include_group):
    """
    Make the row of the prereqs table for the given module
    """
    module_col = (
        f'<a id="{module.code}"></a>[{module.code} {module.name}]({module.url})'
    )
    if module.year == 2.5:
        year_col = "2 or 3"
    elif module.year == 3.5:
        year_col = "3 or 4"
    else:
        year_col = str(int(module.year))
    if module.term == 1.5:  # mod runs in both terms
        term_col = "1 and 2"
    else:
        term_col = str(module.term)
    if include_group:
        group_col = module.group
    prereqs_col = ""
    for prereq_code, prereq_type in module.prereqs:
        # append prereq code, name, link to prereqsCol, whether it's optional
        if prereq_type == "comment":
            prereqs_col += prereq_code + ", "
        elif prereq_type == "needed":
            prereq_module_name = MODULES[prereq_code].name
            prereqs_col += (
                f'<a href="#{prereq_code}">{prereq_code} {prereq_module_name}</a>, '
            )
        else:
            prereq_module_name = MODULES[prereq_code]
            prereqs_col += f'<a href="#{prereq_code}">{prereq_code} {prereq_module_name.name}</a> (recommended), '
    if include_group:
        return f"| {module_col} | {year_col} | {term_col} | {group_col} | {prereqs_col[:-2]}\n"
    return f"| {module_col} | {year_col} | {term_col} | {prereqs_col[:-2]}\n"


with open("pathways.md", "w") as md_file:
    preamble = open("preamble.md").read()
    md_file.write(preamble)
    md_file.write("\n")
    # add the pathway tables, one by one
    for pathway_name, pathway_modules in PATHWAYS.items():
        pathway_modules = sorted(pathway_modules, key=lambda m: MODULES[m].term)
        pathway_modules = sorted(pathway_modules, key=lambda m: MODULES[m].year)
        md_file.write("## " + pathway_name + "\n\n")
        if pathway_name == "First and Second Year":
            md_file.write(tablify(pathway_modules, include_group=False))
        else:
            md_file.write(tablify(pathway_modules))
        md_file.write("\n")
