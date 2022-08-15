
# Pathways

Pathways has been completely re-written to improve the code, add
some new features, and to switch away from xml and xsl transforms to
json and Python.

---

Pathways consists of several files.

 - `modules.json`, containing information about UCL maths modules.
 - `pathways.json`, splitting the modules into different pathways.
 - `syllabus_pdf_scanner.py`, a Python script that downloads all the
 syllabus pdf files from the UCL website, extracts year and term data
 using [`PyPDF2`](https://pypdf2.readthedocs.io/en/latest/), and uses it
 to update `modules.json`.
 - `pathways2.py`, which scrapes the UCL maths module webpage for
 syllabus filenames using [Beautiful
 Soup](https://www.crummy.com/software/BeautifulSoup/bs4/doc/), then
 produces tables of modules and prerequisites in markdown suitable for
 use in [Jekyll](https://jekyllrb.com/) and visualisations with the help
 of [`NetworkX`](https://networkx.org/) and
 [PyGraphviz](https://pygraphviz.github.io/).

You can see the markdown tables
[here](https://www.ucl.ac.uk/~ucahmto/pathways/) and the graphviz output
[here](http://www.homepages.ucl.ac.uk/~ucahmto/pathways.htm).

