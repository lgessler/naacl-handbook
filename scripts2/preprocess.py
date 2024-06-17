import csv
import re
import sys
from itertools import islice
from pathlib import Path
from nameparser import HumanName

import yaml


################################################################################
# Misc
################################################################################
LATEX_ESCAPE = [
    [r'\\', r'\\textbackslash{}'],
    [r'{([^}])', r'\\{\1'],
    [r'([^{])}', r'\1\\}'],
    [r'&', r'\\&'],
    [r'%', r'\\%'],
    [r'\$', r'\\\$'],
    [r'#', r'\\#'],
    [r'_', r'\\_'],
    [r'~', r'\\textasciitilde{}'],
    [r'\^', r'\^{}'],
    [r'<', r'\\textless{}'],
    [r'>', r'\\textgreater{}'],
    [r"≈", r'$\\approx$'],
    [r"∼", r'$\\sim$'],
    [r'\\textbackslash{}\\%', r"\\%"],
]
ALWAYS_ESCAPE = [
    ["", "'"],
    ["", "—"],
    ["↔", "$\leftrightarrow$"],
    ["\\footnote{", "{"],
    [" or \"이 텍스 트를 단순화\" (Korean)", ""],
    [r"\textbf", ""],
    [r"\url", ""],
    [r"\underline", ""],
]
MATH_MODE_PATTERN = re.compile(r"\$[^\s]+\$")


def maybe_latex_escape(s):
    def escape(s):
        for k, v in LATEX_ESCAPE:
            s = re.sub(k, v, s)
        return s
    for k, v in ALWAYS_ESCAPE:
        s = s.replace(k, v)

    if "$" in s and len([c for c in s if c == "$"]) % 2 == 0:
        in_math = False
        out = []
        buffer = []
        for c in s:
            if c == "$":
                if in_math:
                    in_math = False
                    buffer.append(c)
                    out.append("".join(buffer))
                    buffer = []
                else:
                    out.append(escape("".join(buffer)))
                    in_math = True
                    buffer = [c]
            elif in_math:
                buffer.append(c)
            else:
                buffer.append(c)
        out.append(escape("".join(buffer)))
        return "".join(out)

    return escape(s)


def time_incr(t, incr=18):
    l, r = t.split(":")
    l = int(l)
    r = int(r)
    r += incr
    if r >= 60:
        l += 1
        r -= 60
    return str(l).zfill(2) + ":" + str(r).zfill(2)


def last_names(authors):
    if len(authors) == 1:
        return authors[0][1]
    if len(authors) == 2:
        return " and ".join([x[1] for x in authors[-2:]])
    back = ", and ".join([x[1] for x in authors[-2:]])
    front = ", ".join([x[1] for x in authors[:-2]])
    return front + ", " + back


def select_keys(d, ks):
    return {k: v for k, v in d.items() if k in ks}


def batched(iterable, n):
    "Batch data into lists of length n. The last batch may be shorter."
    # batched('ABCDEFG', 3) --> ABC DEF G
    it = iter(iterable)
    while True:
        batch = list(islice(it, n))
        if not batch:
            return
        yield batch


################################################################################
# Parsing
################################################################################


def read_tsv(file_path):
    data = []
    with open(file_path, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file, delimiter='\t')
        for row in reader:
            data.append(dict(row))
    return data


def read_yaml(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        try:
            data = yaml.safe_load(file)
        except yaml.YAMLError as exc:
            print(f"Error reading YAML file: {exc}")
            return None
    return data


def normalize_id(s):
    if m := re.match(r"(\d+)\sIND", s, re.IGNORECASE):
        return "ind-" + str(int(m.groups()[0]))
    elif m := re.match(r"(\d+)\sTACL", s, re.IGNORECASE):
        return "tacl-" + str(int(m.groups()[0]))
    elif m := re.match(r"(\d+)\sCL", s, re.IGNORECASE):
        return "cl-" + str(int(m.groups()[0]))
    elif m := re.match(r"(\d+)\sSRW", s, re.IGNORECASE):
        return "srw-" + str(int(m.groups()[0]))
    elif m := re.match(r"(\d+)\sDEMO", s, re.IGNORECASE):
        return "demo-" + str(int(m.groups()[0]))
    return s


def parse_author_name(s):
    """
    If we didn't get a pre-split author name, we just make a best effort.
    """
    n = HumanName(s)
    p1 = (n.first + " " + n.middle).strip()
    p2 = (n.last + " " + n.suffix).strip()
    return [p1, p2]


def replace_authors_and_abstract(x, all_paper_meta):
    pid = x["Paper ID"]
    if "Abstract" not in x:
        x["Abstract"] = ""
    if pid in all_paper_meta:
        authors = [(x["first_name"], x["last_name"]) for x in all_paper_meta[pid]["authors"]]
        x["Authors"] = authors
        x["Abstract"] = all_paper_meta[pid]["abstract"]
    else:
        if x["Abstract"] == "":
            print(f"WARNING! Couldn't find abstract for {pid}.")
        print(f"WARNING! Couldn't find parsed author info for {pid}. Attempting to guess split for author names.")
        authors = []
        for author in eval(x["Authors"]) if x["Authors"][0] == "[" else x["Authors"].split(", "):
            authors.append(parse_author_name(author))
        x["Authors"] = authors


def clean_author_errors(x):
    authors = x["Authors"]
    for i in range(len(authors)):
        f, l = authors[i]
        if (f, l) == ("Chunsheng", ""):
            authors[i] = ("Chunsheng", "Zuo")
        elif (f, l) == ("WangYou", ""):
            authors[i] = ("Wang", "You")
        elif (f, l) == ("Sai Ramana Reddy", ""):
            authors[i] = ("Sai Ramana", "Reddy")


def add_order_info(main_program):
    oral_table = read_tsv("input/oral_program.tsv")
    paper_idx = {normalize_id(x["Paper ID"]): x for x in oral_table}
    for x in main_program:
        if x["Paper ID"] in paper_idx:
            x["Order"] = paper_idx[x["Paper ID"]]["Pres. Order"]
        else:
            x["Order"] = "999"

def clean_main_program(main_program, all_paper_meta):
    main_program = [
        x for x in main_program
        if (not "not presenting" in x["Format"].lower())
           and "withdraw" not in x["Attendance"].lower()
           and "GT" not in x["Session"]
           and "Virtual" not in x["Session"]
    ]
    for x in main_program:
        x["Paper ID"] = normalize_id(x["Paper ID"])
        replace_authors_and_abstract(x, all_paper_meta)
        x["Session"] = (
            x["Session"]
            .replace("ORAL", "Oral")
            .replace("Oral ", "Orals ")
            .replace("Poster ", "Posters ")
        ).strip()
        if x["Session"] in ["I6", "B6"]:
            x["Session"] = x["Format"] + "s " + x["Session"]
        clean_author_errors(x)

    add_order_info(main_program)
    return main_program


def parse_presentation_type(main_program, prefix, all_papers):
    sessions = {x["Session"] for x in main_program if prefix in x["Session"]}
    sessions = {s.replace(prefix, ""): [] for s in sessions}
    for x in main_program:
        sid = x["Session"].replace(prefix, "")
        if sid in sessions:
            d = {
                "id": x["Paper ID"],
                "title": x["Title"],
                "authors": x["Authors"],
                "abstract": x["Abstract"],
                "order": x["Order"]
            }
            sessions[sid].append(d)
            all_papers.append(d)
    for sid in sessions.keys():
        sessions[sid] = sorted(sessions[sid], key=lambda x:int(x["order"]))
    return sessions


def preprocess():
    p1 = [x for x in read_yaml("input/findings_papers.yml") if x["decision"] == "toFindings"]
    p2 = [x for x in read_yaml("input/main_papers.yml") if x["decision"] == "toMainConference"]
    all_paper_meta = {normalize_id(str(p["id"])): p for p in p1 + p2}

    main_program = read_tsv("input/main_program_table.tsv")
    main_program = clean_main_program(main_program, all_paper_meta)

    all_papers = []
    orals = parse_presentation_type(main_program, "Orals ", all_papers)
    demos = parse_presentation_type(main_program, "Demos ", all_papers)
    posters = parse_presentation_type(main_program, "Posters ", all_papers)

    session_venues = {
        1: "Don Alberto 1",
        2: "Don Alberto 2",
        3: "Don Alberto 3",
        4: "Don Alberto 4",
        5: "Do\\~na Adelita",
        6: "Don Diego 2--4"
    }
    return locals()


################################################################################
# Generation
################################################################################


def generate_overview(overview, out_path, **inputs):
    # ensure dir exists
    out_path.parent.mkdir(parents=True, exist_ok=True)

    o = []
    o.append(r"\section*{Overview}")
    o.append(r"\begingroup")
    o.append(r"\renewcommand\arraystretch{1.8}")
    o.append(r"\begin{SingleTrackSchedule}")

    for (bt, et), title, loc_or_session in overview:
        l = ["  "]
        if bt == "" and et == "":
            l.append(" & & & \n ")
        else:
            l.append(f"{bt} & -- & {et} &\n  ")
        if isinstance(loc_or_session, dict):
            l.append(r"\begin{tabular}{|p{1.65in}|p{1.65in}|}" + "\n")
            l.append(r"    \multicolumn{2}{l}{\bfseries{" + title + r"}}\\\hline" + "\n")
            for row in batched(sorted(loc_or_session.items(), key=lambda x:x[0]), 2):
                names = [f"\\textbf{{{n}}}" for _, n in row]
                l.append("  " + " & ".join(names) + "\\\\\n")
                locs = [f"\\emph{{{inputs['session_venues'][i]}}}" for i, _ in row]
                l.append("  " + " & ".join(locs) + "\\\\\\hline\n")
            l.append(r"\end{tabular} \\" + "\n")
        else:
            l.append(fr"{title} \hfill \emph{{{loc_or_session}}}")
            l.append("\n  \\\\")

        o.append("".join(l))

    o.append(r"\end{SingleTrackSchedule}")
    o.append(r"\endgroup")

    out_path.write_text("\n".join(o) + "\n", encoding="utf-8")

def generate_session_overview(session, inputs, key, times):
    orals = inputs["orals"]
    venues = inputs["session_venues"]

    def f(themes, papers, venues):
        head = rf"""\begin{{ThreeSessionOverview}}
  {{{themes[0]}}}
  {{{themes[1]}}}
  {{{themes[2]}}}
  {{{venues[0]}}}
  {{{venues[1]}}}
  {{{venues[2]}}}
"""
        body = ""
        for i in range(5):
            p1 = papers[0][i] if i < len(papers[0]) else None
            p2 = papers[1][i] if i < len(papers[1]) else None
            p3 = papers[2][i] if i < len(papers[2]) else None
            body += rf"""  \marginnote{{\rotatebox{{90}}{{{times[i]}}}}}[2mm]""" + "\n"
            body += rf"  \papertableentry{{{p1['id']}}}" if p1 is not None else ""
            body += " & "
            body += rf"\papertableentry{{{p2['id']}}}" if p2 is not None else ""
            body += " & "
            body += rf"\papertableentry{{{p3['id']}}}" if p3 is not None else ""
            body += "\\\\\n  \hline"
        body += "\n"
        tail = rf"""\end{{ThreeSessionOverview}}"""
        return head + body + tail

    output = rf"""\clearpage
\section[Session {key}]{{Session {key} Overview -- \daydateyear}}
\setheaders{{Session {key}}}{{\daydateyear}}
\setlength{{\parskip}}{{2ex}}
"""
    output += f(
        [session[1], session[2], session[3]],
        [orals[f"{key}1"], orals[f"{key}2"], orals[f"{key}3"]],
        [venues[1], venues[2], venues[3]]
    )
    output += "\n\\clearpage\n"
    output += f(
        [session[4], session[5], ""],
        [orals[f"{key}4"], orals[f"{key}5"], []],
        [venues[4], venues[5], ""]
    )
    output += "\n"
    return output


def generate_session_oral_details(session, inputs, key, times):
    venues = inputs["session_venues"]
    orals = inputs["orals"]
    output = r"\newpage" + "\n"
    #output += fr"\section*{{Session {key}}}" + "\n"
    for i in range(1, 6):
        title = session[i]
        venue = venues[i]
        output += rf"\section{{Session {key}{i}: {title}}}" + "\n"
        output += rf"{{\bf {venue}}}\par" + "\n"
        output += r"\vspace{1em}"
        k2 = f"{key}{i}"
        if k2 in orals:
            for j, paper in enumerate(orals[k2]):
                output += fr"\paperabstract{{\day}}{{{times[j]}--{time_incr(times[j])}}}{{}}{{}}{{{paper['id']}}}" + "\n"
        output += r"\clearpage" + "\n\n"
    return output


def generate_session_poster_details(inputs, inputs_key, key, time):
    ck = f"{key}6"
    venue = inputs["session_venues"][6]
    if ck not in inputs[inputs_key]:
        return ""
    stype = "Poster" if inputs_key == "posters" else "Demo"
    name = fr"Session {ck}: {stype}s"
    output = rf"""\section{{{name}}}
\setheaders{{{name}}}{{\daydateyear}}
{{\large Time: {time}\hfill Location: {venue}}}\\
\\
"""
    papers = inputs[inputs_key][ck]
    for paper in papers:
        output += rf"\posterabstract{{{paper['id']}}}" + "\n"
    return output


def generate_session(session, inputs, key, begin_time):
    times = [begin_time]
    poster_only = 1 not in session.keys()

    if poster_only:
        times.append(time_incr(begin_time, 30))
    else:
        for _ in range(4):
            times.append(time_incr(times[-1], 18))

    # poster only?
    if not poster_only:
        output = generate_session_overview(session, inputs, key, times)
        output += generate_session_oral_details(session, inputs, key, times)
    else:
        output = ""
    output += generate_session_poster_details(inputs, "posters", key, begin_time + "--" + time_incr(times[-1]))
    output += generate_session_poster_details(inputs, "demos", key, begin_time + "--" + time_incr(times[-1]))
    with open(f"auto/papers/session_{key}.tex", "w") as f:
        f.write(output)


def generate_day1(**inputs):
    session_b = {
        1: "Special Theme: Languages of Latin America",
        2: "Generation",
        3: "Question Answering",
        4: "Machine Translation",
        5: "Discourse and Pragmatics",
        6: "Poster Session 1: TACL + CL + Main",
    }
    session_c = {
        1: "Ethics, Bias, and Fairness 1",
        2: "Summarization",
        3: "Information Extraction",
        4: "Multilinguality and Language Diversity",
        5: "Semantics: Sentence-level Semantics, Textual Inference and Other areas",
        6: "Poster Session 2: Main"
    }
    session_d = {
        1: "Ethics, Bias, and Fairness 2",
        2: "Dialogue and Interactive Systems",
        3: "Information Retrieval and Text Mining",
        4: "Efficient/Low-Resource Methods for NLP",
        5: "Industry 1",
        6: "Posters Session 3: Main",
    }
    overview = [
        [["07:30", "16:30"], "Registration", "Diego Foyer"],
        [["09:00", "09:30"], "{\\bf Session A: Opening Session", "Don Alberto}"],
        [["09:30", "10:30"], "{\\bf Session A: Keynote Speaker: Claudio Santos Pinhanez}", "Don Alberto"],
        [["10:30", "11:00"], "{\\it Break}", ""],
        [["11:00", "12:30"], "Session B", session_b],
        [["12:30", "14:00"], "{\\it Lunch break}", ""],
        [["14:00", "15:30"], "Session C", session_c],
        [["15:30", "16:00"], "{\\it Break}", ""],
        [["16:00", "17:30"], "Session D", session_d],
    ]
    generate_overview(overview, Path("auto/papers/Monday-overview.tex"), **inputs)
    generate_session(session_b, inputs, "B", "11:00")
    generate_session(session_c, inputs, "C", "14:00")
    generate_session(session_d, inputs, "D", "16:00")


def generate_day2(**inputs):
    session_e = {
        1: "Linguistic theories, Cognitive Modeling and Psycholinguistics",
        2: "Computational Social Science and Cultural Analytics",
        3: "Sentiment Analysis, Stylistic Analysis, and Argument Mining",
        4: "Machine Learning for NLP",
        5: "Industry 2",
        6: "Poster Session 4: Main",
    }
    session_h = {
        6: "Poster Session 5: Industry + SRW + Findings"
    }
    overview = [
        [["08:30", "16:30"], "Registration", "Diego Foyer"],
        [["09:00", "10:30"], "Session E", session_e],
        [["10:30", "11:00"], "{\\it Break}", ""],
        [["11:00", "12:30"], "{\\bf Session F: Plenary Panel}", "Don Alberto"],
        [["12:30", "14:00"], "{\\it Lunch break}", ""],
        [["14:00", "15:00"], "{\\bf Session G: Business Meeting}", "Don Alberto 2--3"],
        [["15:00", "15:30"], "{\\it Break}", ""],
        [["15:30", "17:00"], "{\\bf Session H: Poster Session 5: Industry + SRW + Findings}", "Do\~na Adelita"],
        [["19:00", "22:00"], "{\\bf Social Event Dinner}", "Don Alberto"],
    ]
    generate_overview(overview, Path("auto/papers/Tuesday-overview.tex"), **inputs)
    generate_session(session_e, inputs, "E", "09:00")
    generate_session(session_h, inputs, "H", "15:30")


def generate_day3(**inputs):
    session_i = {
        1: "Resources and Evaluation 1",
        2: "Multimodality and Language Grounding to Vision, Robotics and Beyond",
        3: "NLP Applications 1",
        4: "Interpretability and Analysis of Models for NLP 1",
        5: "Industry 3",
        6: "Poster Session 6: Findings",
    }
    session_j = {
        1: "Resources and Evaluation 2",
        2: "Speech recognition, text-to-speech and spoken language understanding",
        3: "NLP Applications 2",
        4: "Interpretability and Analysis of Models for NLP 2",
        5: "Industry 4",
        6: "Poster Session 7: Findings",
    }
    overview = [
        [["08:30", "16:30"], "Registration", "Diego Foyer"],
        [["09:00", "10:30"], "Session I", session_i],
        [["10:30", "11:00"], "{\\it Break}", ""],
        [["11:00", "12:30"], "Session J", session_j],
        [["12:30", "14:00"], "{\\it Lunch break}", ""],
        [["14:30", "15:00"], "{\\bf Session K: Keynote Speaker: Seana Coulson}", "Don Alberto"],
        [["15:00", "15:30"], "{\\it Break}", ""],
        [["15:30", "16:15"], "{\\bf Session L: Best Paper Awards}", "Don Alberto"],
        [["16:15", "17:00"], "{\\bf Session L: Closing Session}", "Don Alberto"],
    ]
    generate_overview(overview, Path("auto/papers/Wednesday-overview.tex"), **inputs)
    generate_session(session_i, inputs, "I", "09:00")
    generate_session(session_j, inputs, "J", "11:00")


def generate_mexican_nlp(**inputs):
    overview = [
        [["08:20", "08:50"], "Registration", "Do\~na Adelita"],
        [["08:50", "09:00"], "{\\bf Opening Session}", "Do\~na Adelita"],
        [["09:00", "10:00"], "{\\bf Keynote: Diyi Yang}", "Do\~na Adelita"],
        [["10:00", "11:00"], "{\\bf Keynote: Alexis Palmer}", "Do\~na Adelita"],
        [["11:00", "11:30"], "{\\it Break}", ""],
        [["11:30", "13:00"], "{\\bf Panel A}", "Do\~na Adelita"],
        [["12:30", "14:00"], "{\\it Lunch break}", ""],
        [["14:30", "15:30"], "{\\bf Keynote: Umut Pajaro Velasquez}", "Do\~na Adelita"],
        [["15:30", "16:30"], "{\\bf Keynote: Veronica Perez Rosas}", "Do\~na Adelita"],
        [["16:30", "17:00"], "{\\it Break}", ""],
        [["17:00", "18:30"], "{\\bf Panel B}", "Do\~na Adelita"],
    ]
    generate_overview(overview, Path("auto/mexican_nlp/Friday-overview.tex"), **inputs)
    overview = [
        [["09:00", "10:30"], "{\\bf Tutorial A}", "Do\~na Adelita"],
        [["09:00", "10:30"], "{\\bf Tutorial B}", "Don Juli\\'an"],
        [["10:30", "11:00"], "{\\it Break}", ""],
        [["11:00", "12:30"], "{\\bf Tutorial A}", "Do\~na Adelita"],
        [["11:00", "12:30"], "{\\bf Tutorial B}", "Don Jul\\'ian"],
        [["12:30", "14:00"], "{\\it Lunch break}", ""],
        [["14:00", "16:00"], "{\\bf Tutorial C}", "Do\~na Adelita"],
        [["14:00", "16:00"], "{\\bf Tutorial D}", "Don Juli\\'an"],
        [["16:00", "16:15"], "{\\it Break}", ""],
        [["16:15", "18:30"], "{\\bf Panel C}", "Do\~na Adelita"],
    ]
    generate_overview(overview, Path("auto/mexican_nlp/Saturday-overview.tex"), **inputs)


def generate_tutorial(**inputs):
    tut1 = (
        r"\makecell[l]{{\bf Catch Me If You GPT: Tutorial on Deepfake Texts} \\"
        r"Adaku Uchendu, Saranya Venkatraman, Thai Le, and \\ Dongwon Lee}"
    )
    tut2 = (
        r"\makecell[l]{\\ {\bf Combating Security and Privacy Issues in the Era} \\ {\bf of Large Language Models} \\"
        r"Muhao Chen, Chaowei Xiao, Huan Sun, Lei Li, \\ Leon Derczynski and Anima Anandkumar}"
    )
    tut3 = (
        r"\makecell[l]{\\ {\bf Explanation in the Era of Large Language Models} \\"
        r"Zining Zhu, Hanjie Chen, Xi Ye, Chenhao Tan, Ana Marasovic, \\ Sarah Wiegreffe and Qing Lyu}"
    )

    tut4 = (
        r"\makecell[l]{{\bf From Text to Context: Contextualizing Language with} \\ {\bf Humans, Groups, and Communities for Socially Aware NLP} \\"
        r"Adithya V Ganesan, Siddharth Mangalik, Vasudha Varadarajan, \\ Nikita Soni, Swanie Juhng, Jo\~ao Sedoc, H.~Andrew Schwartz, \\ Salvatore Giorgi and Ryan Boyd}"
    )
    tut5 = (
        r"\makecell[l]{\\ {\bf Human-AI Interaction in the Age of LLMs} \\"
        r"Diyi Yang, Tongshuang Wu and Marti A. Hearst}"
    )
    tut6 = (
        r"\makecell[l]{\\ {\bf Spatial and Temporal Language Understanding:} \\ {\bf Representation, Reasoning, and Grounding} \\"
        r"Parisa Kordjamshidi, Marie-Francine Moens, \\ James Pustejovsky and Qiang Ning}"
    )

    reception_detail = (
        r"\begin{tabular}{lcl}"
        r"18:30 &--& Check-in, drink tickets distributed \\"
        r"19:00 &--& Doors open, appetizers served \\"
        r"21:00 &--& Last call \\"
        r"\end{tabular}"
    )
    overview = [
        [["08:30", "16:30"], "Registration", "Diego Foyer"],
        [["09:00", "12:30"], "{\\bf Tutorials (Level 4)}", ""],
        [["", ""], tut1, "Do\\~na Adelita"],
        [["", ""], tut2, "Don Alberto 4"],
        [["", ""], tut3, "Don Alberto 3"],
        [["12:30", "14:00"], "{\\it Lunch break}", ""],
        [["14:00", "17:30"], "{\\bf Tutorials (Level 4)}", ""],
        [["", ""], tut4, "Do\\~na Adelita"],
        [["", ""], tut5, "Don Alberto 2"],
        [["", ""], tut6, "Don Alberto 3"],
        [["19:00", "21:30"], "{\\bf Welcome Reception}", "Don Alberto"],
        [["", ""], reception_detail, ""],
    ]
    generate_overview(overview, Path("content/tutorials/tutorials-overview.tex"), **inputs)


def generate_bib(x):
    out = []
    out.append("@INPROCEEDINGS{" + x["id"] + ",")
    authors = " and ".join(f"{l}, {f}" for f, l in x["authors"])
    sortname = authors
    title = x["title"]
    if "-" in x["id"]:
        prefix = "[" + x["id"].split("-")[0].upper() + "] "
        title = prefix + title
        sortname = prefix + authors
    authors = maybe_latex_escape(authors)
    sortname = maybe_latex_escape(sortname)
    title = maybe_latex_escape(title)
    out.append("  AUTHOR = {" + authors + "},")
    out.append("  SORTNAME = {" + sortname + "},")
    out.append("  TITLE = {" + title + "}}")
    out.append("")
    return out


def generate_all_bib_and_abstracts(**inputs):
    out = []
    for x in inputs["all_papers"]:
        out.extend(generate_bib(x))
        with open(f"auto/abstracts/{x['id']}.tex", "w") as f:
            s = maybe_latex_escape(x["abstract"])
            s = re.sub("\n+", " ", s)
            f.write(s)

    s = "\n".join(out) + "\n"
    with open(f"auto/papers/papers.bib", "w") as f:
        f.write(s)


def main():
    inputs = preprocess()

    # virtual
    inputs["physical"] = False
    generate_all_bib_and_abstracts(**inputs)
    generate_mexican_nlp(**inputs)
    generate_tutorial(**inputs)
    generate_day1(**inputs)
    generate_day2(**inputs)
    generate_day3(**inputs)

    # physical
    inputs["physical"] = True
    generate_all_bib_and_abstracts(**inputs)
    generate_mexican_nlp(**inputs)
    generate_tutorial(**inputs)
    generate_day1(**inputs)
    generate_day2(**inputs)
    generate_day3(**inputs)




