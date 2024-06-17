# Introduction
This code was used to generate the NAACL 2024 handbook and is a heavily modified
version of [Matt Post's original from 2014](https://github.com/naacl-org/naacl-handbook).
The major differences stem from the fact that ACL conferences now use OpenReview 
instead of SoftConf, which requires you to do a lot more work manually than you used to have to.

If you're reading this, you'll likely need to adapt this code for use for your conference.
Read on.

# Handbook Chair Duties

Your job as the handbook chair is to do the following:

* Receive information about workshops, tutorials, presentations, and other information 
  from the various chairs of the conference, write new code to parse them (for e.g. oral
  presentations) or else add them manually (for e.g. tutorials)
* Coordinate with ACL staff to receive and properly include advertisements, venue information,
  and cover art.
* Produce a final PDF (perhaps with a virtual version different from the physical version).

This will take a *lot* of manual work, so be ready. It is also good for you to ask the publication
chairs early how they will be storing schedule information. Ask them to be as consistent and structured
as possible so that you minimize the amount of work you'll have to do later in getting it all to parse.

# Code Organization
These are the important files and directories:

* `handbook.tex`: this is the top-level `.tex` file which will include all other `.tex` sources.
* `handbook_physical.tex`: ditto, but for the physical version of the handbook. For NAACL 2024, the major
  difference was that the physical handbook did not have any information on paper presentations.
* `Makefile` and `Makefile_physical`: you will use these to build PDFs by running `make`.
* `scripts/`: these are mostly legacy scripts except for one or two which are invoked by `make`.
* `scripts2/preprocess.py`: this is code I wrote to parse input and generate all the non-manual `.tex`
  files for NAACL 2024. You will be heavily editing or replacing this.
* `inputs/`: this stores the paper information you will be receiving from the publication chairs and the
  program chairs. For NAACL 2024, this came in the form of `.yml` files from the publication chairs,
  and `.tsv`s from the Program Chairs derived from the Google Sheets document they were using to schedule.
* `content/`: **manually** created `.tex` sources which you will need to replace
* `auto/`: **automatically** created `.tex` and `.bib` files generated by `scripts2/preprocess.py`.

# Compiling
First, you'll need to install a few dependencies. The Python ones should be straightforward, but for the
LaTeX dependencies, you will need recent versions of a few packages. Most importantly, you will need
a recent version of biber. Assuming you are a `sudo`er and have `tlmgr`, do the following:

```bash
sudo tlmgr install combelow newunicodechar fncychap csquotes multirow biblatex biber pstricks marginnote enumitem t5enc kotex amsfonts makecell
```

You should start by compiling the NAACL 2024 handbook to make sure everything's OK. 

1. Run `python scripts2/preprocess.py --physical` (or `python scripts2/preprocess.py --virtual`) to
   populate `auto/` with generated `.tex` sources. (These two variants overwrite each other, so be sure
   to run the one you need before you run the next step.)
2. Run `make` or `make -f Makefile-physical` to generate the PDF.

That's it!