# The Voynich Transliteration Tool
# By: Krymorn (cmarbel)
# Version: 1.6.3
#
# A tool for remapping the v101 transcription of the voynich manuscript.
# Read the README.md file for a full explanation of all features.
#
# Note: The v101 transcription used does not include the v101 extended character set.

### Imports ###
import math
import os
import difflib
from collections import Counter

### Setup ###
spaceDelimiter = "_"
ambiguousSpaceDelimiter = "-"
endOfWordMarker = "/"
startOfWordMarker = "@"
commentOutChar = ")"

firstOccuranceMarker = "'"
secondOccuranceMarker = "\""  # Note: Python requires you to have a \ before a " character because multiple " characters in a row mess up Python syntax
thirdOccuranceMarker = ":"
fourthOccuranceMarker = ";"

# Translation Language
translationLanguage = 'la'  # Default translation language

# Processing Limits
startLine = 0
endLine = None  # Set to None for full text, or a number (e.g. 200) for testing

# Features
enableAnalysis = False
enableZipfsLawGeneration = False
enableZipfsReferenceLines = False
enableHTMLComparison = False
useVoynichChars = False
enableTranslation = False
enablePrintLanguages = False

# Corpus Analysis
enableFuzzyMatching = False
toleranceLevel = 2  # Options of 1/2/3, 1 being most tolerant of variations of words from the reference corpus and 3 being the least tolerant (most strict)
corpusReportPath = "discovery_report.txt"
referenceFolder = "reference_texts"
fuzzyOutputPath = "output_fuzzy.txt"

# File Paths
mapPath = "mapping.txt"
inputPath = "v101_cleaned.txt"
outputPath = "output.txt"
outputNumberPath = "output_numbers.txt"
analysisPath = "analysis.txt"
translatePath = "translated.txt"

# Read Input
with open(inputPath, "r") as inputFile:
  all_lines = inputFile.readlines()
  if endLine is None:
    selected_lines = all_lines[startLine:]
  else:
    selected_lines = all_lines[startLine:endLine]

  print(
      f"Processing lines {startLine} to {len(all_lines) if endLine is None else endLine}..."
  )
  inputData = "".join(selected_lines)
  inputData = inputData.replace(".", spaceDelimiter)
  inputData = inputData.replace(",", ambiguousSpaceDelimiter)

# Read Mapping
with open(mapPath, "r") as inputMapFile:
  inputMapData = inputMapFile.read()

# Outputs
outputFile = open(outputPath, "w")
outputNumberFile = open(outputNumberPath, "w")

# Dictionaries
num_to_char_normal = {}
num_to_char_final = {}
char_to_num_normal = {}
char_to_num_final = {}
input_num_to_char_normal = {}
input_num_to_char_final = {}
input_char_to_num_normal = {}
input_char_to_num_final = {}

num_to_char_initial = {}
char_to_num_initial = {}
input_num_to_char_initial = {}
input_char_to_num_initial = {}

num_to_char_first = {}
char_to_num_first = {}
input_num_to_char_first = {}
input_char_to_num_first = {}

num_to_char_second = {}
char_to_num_second = {}
input_num_to_char_second = {}
input_char_to_num_second = {}

num_to_char_third = {}
char_to_num_third = {}
input_num_to_char_third = {}
input_char_to_num_third = {}

num_to_char_fourth = {}
char_to_num_fourth = {}
input_num_to_char_fourth = {}
input_char_to_num_fourth = {}

# Parse Mapping
is_initial = False
is_final = False
is_first = False
is_second = False
is_third = False
is_fourth = False

with open(mapPath, "r") as mapFile:
  for line in mapFile:
    line = line.strip()
    is_initial = False
    is_final = False
    is_first = False
    is_second = False
    is_third = False
    is_fourth = False

    if not line or "=" not in line or "~" not in line or line.startswith(
        commentOutChar):
      continue

    if line.endswith(startOfWordMarker):
      line = line[:-1]
      is_initial = True
    if line.endswith(endOfWordMarker):
      line = line[:-1]
      is_final = True
    if line.endswith(firstOccuranceMarker):
      line = line[:-1]
      is_first = True
    if line.endswith(secondOccuranceMarker):
      line = line[:-1]
      is_second = True
    if line.endswith(thirdOccuranceMarker):
      line = line[:-1]
      is_third = True
    if line.endswith(fourthOccuranceMarker):
      line = line[:-1]
      is_fourth = True

    number, line2 = line.split("=", 1)
    char, outputChar = line2.split("~", 1)
    number = number.strip()
    char = char.strip()
    outputChar = outputChar.strip()

    if is_initial:
      input_char_to_num_initial[char] = number
      input_num_to_char_initial[number] = outputChar
      char_to_num_initial[char] = number
      num_to_char_initial[number] = outputChar
    elif is_final:
      input_char_to_num_final[char] = number
      input_num_to_char_final[number] = outputChar
      char_to_num_final[char] = number
      num_to_char_final[number] = outputChar
    elif is_first:
      input_char_to_num_first[char] = number
      input_num_to_char_first[number] = outputChar
      char_to_num_first[char] = number
      num_to_char_first[number] = outputChar
    elif is_second:
      input_char_to_num_second[char] = number
      input_num_to_char_second[number] = outputChar
      char_to_num_second[char] = number
      num_to_char_second[number] = outputChar
    elif is_third:
      input_char_to_num_third[char] = number
      input_num_to_char_third[number] = outputChar
      char_to_num_third[char] = number
      num_to_char_third[number] = outputChar
    elif is_fourth:
      input_char_to_num_fourth[char] = number
      input_num_to_char_fourth[number] = outputChar
      char_to_num_fourth[char] = number
      num_to_char_fourth[number] = outputChar
    else:
      input_char_to_num_normal[char] = number
      input_num_to_char_normal[number] = outputChar
      char_to_num_normal[char] = number
      num_to_char_normal[number] = outputChar

all_keys = (list(input_char_to_num_normal.keys()) +
            list(input_char_to_num_final.keys()) +
            list(input_char_to_num_initial.keys()) +
            list(input_char_to_num_first.keys()) +
            list(input_char_to_num_second.keys()) +
            list(input_char_to_num_third.keys()) +
            list(input_char_to_num_fourth.keys()) +
            list(char_to_num_normal.keys()) + list(char_to_num_final.keys()) +
            list(char_to_num_initial.keys()) + list(char_to_num_first.keys()) +
            list(char_to_num_second.keys()) + list(char_to_num_third.keys()) +
            list(char_to_num_fourth.keys()) + list(num_to_char_normal.keys()) +
            list(num_to_char_final.keys()) + list(num_to_char_initial.keys()) +
            list(num_to_char_first.keys()) + list(num_to_char_second.keys()) +
            list(num_to_char_third.keys()) + list(num_to_char_fourth.keys()))

MAX_KEY_LENGTH = max((len(k) for k in all_keys), default=1)


### Core Functions ###
def is_word_start(index, data):
  if index == 0: return True
  prev_char = data[index - 1]
  return prev_char in [spaceDelimiter, ambiguousSpaceDelimiter, "\n"]


def is_word_end(index, data, length=1):
  if index + length >= len(data): return True
  return data[index +
              length] in [spaceDelimiter, ambiguousSpaceDelimiter, "\n"]


def getChar(inputNum, index, data, length, occurrence):
  if inputNum == "\n": return "\n"
  at_end = is_word_end(index, data, length)
  at_start = is_word_start(index, data)

  if at_start and inputNum in input_num_to_char_initial:
    return input_num_to_char_initial[inputNum]
  if at_end and inputNum in input_num_to_char_final:
    return input_num_to_char_final[inputNum]

  if occurrence == 1 and inputNum in input_num_to_char_first:
    return input_num_to_char_first[inputNum]
  if occurrence == 2 and inputNum in input_num_to_char_second:
    return input_num_to_char_second[inputNum]
  if occurrence == 3 and inputNum in input_num_to_char_third:
    return input_num_to_char_third[inputNum]
  if occurrence == 4 and inputNum in input_num_to_char_fourth:
    return input_num_to_char_fourth[inputNum]

  if inputNum in input_num_to_char_normal:
    return input_num_to_char_normal[inputNum]
  return num_to_char_normal.get(inputNum, "")


def getNum(inputChar, index, data, occurrence):
  if inputChar == "\n": return "\n"
  length = len(inputChar)
  at_end = is_word_end(index, data, length)
  at_start = is_word_start(index, data)

  if at_end and inputChar in char_to_num_final:
    return char_to_num_final[inputChar]
  if at_start and inputChar in char_to_num_initial:
    return char_to_num_initial[inputChar]

  if occurrence == 1 and inputChar in char_to_num_first:
    return char_to_num_first[inputChar]
  if occurrence == 2 and inputChar in char_to_num_second:
    return char_to_num_second[inputChar]
  if occurrence == 3 and inputChar in char_to_num_third:
    return char_to_num_third[inputChar]
  if occurrence == 4 and inputChar in char_to_num_fourth:
    return char_to_num_fourth[inputChar]

  return char_to_num_normal.get(inputChar, "")


### Main Transliteration Loop ###
outputNumberFile.write(".")
i = 0
word_char_counts = {}

while i < len(inputData):
  ch = inputData[i]

  if ch == "\n":
    outputNumberFile.write("\n.")
    outputFile.write("\n")
    word_char_counts.clear()
    i += 1
    continue

  if ch in [spaceDelimiter, ambiguousSpaceDelimiter]:
    outputNumberFile.write(ch + ".")
    outputFile.write(ch)
    word_char_counts.clear()
    i += 1
    continue

  match_str = ch
  match_len = 1

  for length in range(MAX_KEY_LENGTH, 0, -1):
    if i + length > len(inputData):
      continue
    inputChars = inputData[i:i + length]
    if (inputChars in input_char_to_num_normal
        or inputChars in input_char_to_num_final
        or inputChars in input_char_to_num_initial
        or inputChars in input_char_to_num_first
        or inputChars in input_char_to_num_second
        or inputChars in input_char_to_num_third
        or inputChars in input_char_to_num_fourth):
      match_str = inputChars
      match_len = length
      break

  current_occurrence = word_char_counts.get(match_str, 0) + 1
  word_char_counts[match_str] = current_occurrence

  encoded = getNum(match_str, i, inputData, current_occurrence)
  decoded = getChar(encoded, i, inputData, match_len, current_occurrence)

  outputNumberFile.write(encoded + ".")
  outputFile.write(decoded)
  i += match_len

outputFile.close()
outputFile = open(outputPath, "r")
outputRaw = outputFile.read()
outputClean = outputRaw.replace(spaceDelimiter, "").replace(ambiguousSpaceDelimiter, "")#.replace("\n", "")
outputForWords = outputRaw.replace(spaceDelimiter, " ").replace(ambiguousSpaceDelimiter, " ")#.replace("\n", " ")
analysisFile = open(analysisPath, "w")
counts = Counter(outputClean)
total_chars = len(outputClean)


### Analysis Helpers ###
def analyze_reduplication(word_string):
  analysisFile.write("\n_____________________________\n")
  normalized = word_string.replace("\n", " ").replace(ambiguousSpaceDelimiter,
                                                      " ").replace(
                                                          spaceDelimiter, " ")
  words = [w for w in normalized.split(" ") if w]
  redup_pairs = []
  redup_count = 0
  for k in range(len(words) - 1):
    if words[k] == words[k + 1]:
      redup_count += 1
      redup_pairs.append(words[k])
  analysisFile.write(f"\nImmediate Reduplications: {redup_count}\n")
  if redup_count > 0:
    c = Counter(redup_pairs)
    analysisFile.write("Most Frequent Repeating Words:\n")
    for word, cnt in c.most_common(10):
      analysisFile.write(f"{{ {word}: {cnt} times }}\n")
  analysisFile.write("_____________________________\n")


def analyze_word_parts():
  normalized = outputRaw.replace("\n", spaceDelimiter).replace(
      ambiguousSpaceDelimiter, spaceDelimiter)
  words = [w for w in normalized.split(spaceDelimiter) if w]
  total_words = len(words)
  analysisFile.write("Total Words Processed: " + str(total_words) + "\n")
  analysisFile.write("_____________________________\n")

  word_counts = Counter(words)
  analysisFile.write("\nMost Common Whole Words:\n")
  for word, count in word_counts.most_common(20):
    pct = round((count / total_words) * 100, 2)
    analysisFile.write(f"{{ {word}: {count}, {pct}% }}\n")
  analysisFile.write("_____________________________\n")

  min_ngram = 2
  max_ngram = 4
  for n in range(min_ngram, max_ngram + 1):
    prefixes = []
    suffixes = []
    affixes = []
    for word in words:
      word_len = len(word)
      if word_len < n: continue
      prefixes.append(word[:n])
      suffixes.append(word[-n:])
      for i in range(0, word_len - n + 1):
        affixes.append(word[i:i + n])

    def write_stats(title, data_list):
      if not data_list: return
      item_counts = Counter(data_list)
      total_items = len(data_list)
      analysisFile.write(f"\n{title} (Length {n}):\n")
      for item, count in item_counts.most_common(20):
        pct = round((count / total_items) * 100, 2)
        analysisFile.write(f"{{ {item}: {count}, {pct}% }}\n")

    write_stats("Common Prefixes", prefixes)
    write_stats("Common Suffixes", suffixes)
    write_stats("Common Affixes", affixes)


def entropy():
  e = 0.0
  for count in counts.values():
    p = count / total_chars
    e -= p * math.log2(p)
  analysisFile.write("Character Entropy: " + str(round(e, 3)) + " Bits\n")
  analysisFile.write("_____________________________\n\n")


def frequency():
  freq = {}
  for char in set(outputClean):
    if char != "\n":
      freq[char] = outputClean.count(char)
  freq_sorted = sorted(freq.items(), key=lambda x: x[1], reverse=True)
  analysisFile.write("Character Frequency:\n")
  for char, count in freq_sorted:
    if char != "\n":
      analysisFile.write("{ " + char + ": " + str(count) + ", " +
                         str(round(count / total_chars * 100, 3)) + "% }\n")
  analysisFile.write("_____________________________\n\n")


def sukhotin_vowel_analysis(text):
  valid_chars = [c for c in text if c.isalnum()]
  alphabet = sorted(list(set(valid_chars)))
  n = len(alphabet)
  char_to_index = {c: i for i, c in enumerate(alphabet)}
  matrix = [[0] * n for _ in range(n)]
  for k in range(len(valid_chars) - 1):
    i = char_to_index[valid_chars[k]]
    j = char_to_index[valid_chars[k + 1]]
    matrix[i][j] += 1
    matrix[j][i] += 1
  is_vowel = [False] * n
  analysisFile.write("\nSukhotin's Vowel Classification:\n\n")
  while True:
    scores = []
    for i in range(n):
      if is_vowel[i]:
        scores.append(-float('inf'))
        continue
      score = 0
      for j in range(n):
        if not is_vowel[j]:
          score += matrix[i][j]
      scores.append(score)
    max_score = max(scores)
    if max_score <= 0: break
    candidate_idx = scores.index(max_score)
    is_vowel[candidate_idx] = True
    analysisFile.write(
        f"identified potential vowel: {alphabet[candidate_idx]} (Score: {max_score})\n"
    )
  vowels = [alphabet[i] for i in range(n) if is_vowel[i]]
  consonants = [alphabet[i] for i in range(n) if not is_vowel[i]]
  analysisFile.write(
      f"\nFinal Vowels: {vowels}\nFinal Consonants: {consonants}\n")


if enableAnalysis:
  entropy()
  frequency()
  analyze_word_parts()
  analyze_reduplication(outputRaw)
  sukhotin_vowel_analysis(outputClean)


### Graph Zipf's Law ###
def plot_zipf_law(text):
  try:
    import numpy as np
    import matplotlib.pyplot as plt
    words = text.split()
    counts_z = Counter(words)
    sorted_counts = sorted(counts_z.values(), reverse=True)
    if not sorted_counts: return
    ranks = np.arange(1, len(sorted_counts) + 1)
    frequencies = np.array(sorted_counts)
    plt.figure(figsize=(14, 8))
    plt.loglog(ranks,
               frequencies,
               marker=".",
               linestyle="none",
               color="blue",
               alpha=0.7,
               markersize=8,
               label="Transliteration")
    c = frequencies[0]
    references = [("Modern English", 1.00, "grey", "--"),
                  ("Middle High German", 1.03, "green", ":"),
                  ("Old French/Italian", 1.06, "orange", "-."),
                  ("Old English", 1.08, "purple", ":"),
                  ("Latin", 1.15, "yellow", "-.")]
    if enableZipfsReferenceLines:
      for label, slope, color, style in references:
        ref_line = c / (ranks**slope)
        plt.loglog(ranks,
                   ref_line,
                   linestyle=style,
                   color=color,
                   linewidth=1.5,
                   alpha=0.6,
                   label=f"{label} (s={slope})")
    plt.title("Zipf's Law Analysis", fontsize=20)
    plt.xlabel("Rank (log scale)", fontsize=16)
    plt.ylabel("Frequency (log scale)", fontsize=16)
    plt.grid(True, which="both", ls="-", alpha=0.2)
    plt.legend(bbox_to_anchor=(1.02, 1),
               loc='upper left',
               borderaxespad=0,
               fontsize=14)
    plt.tight_layout()
    plt.savefig("zipf_analysis.png", dpi=150)
    print("Zipf's law plot saved.")
  except ImportError:
    print("Matplotlib not installed.")


if enableZipfsLawGeneration:
  plot_zipf_law(outputForWords)


### Comparison HTML ###
def generate_html_report(original_text, transliterated_text):
  orig_lines = original_text.replace(spaceDelimiter,
                                     " ").replace(ambiguousSpaceDelimiter,
                                                  " ").split("\n")
  trans_lines = transliterated_text.replace(spaceDelimiter, " ").replace(
      ambiguousSpaceDelimiter, " ").split("\n")
  html = "<html><head><style>body{font-family:sans-serif;padding:20px;background:#f0f0f0}.container{display:flex;flex-direction:column;gap:10px}.row{display:flex;background:white;border-bottom:1px solid #ccc;padding:10px}.trans{flex:1;padding-right:10px;border-right:1px solid #eee;color:#333}.orig{flex:1;padding-left:10px;font-family:'Courier New',monospace}</style></head><body><h1>Comparison</h1><div class='container'>"
  for t, o in zip(trans_lines, orig_lines):
    if not t.strip() and not o.strip(): continue
    html += f"<div class='row'><div class='trans'>{t}</div><div class='orig'>{o}</div></div>"
  html += "</div></body></html>"
  with open("comparison.html", "w", encoding="utf-8") as f:
    f.write(html)
  print("HTML Report saved.")


if enableHTMLComparison:
  generate_html_report(inputData, outputRaw)

### Translation ###
if enablePrintLanguages:
  try:
    from deep_translator import GoogleTranslator
    print(GoogleTranslator().get_supported_languages(as_dict=True))
  except:
    pass

if enableTranslation:
  try:
    from deep_translator import GoogleTranslator
    translateFile = open(translatePath, "w")
    translateFile.close()
    translateFile = open(translatePath, "a")
    chunk_size = 4500
    for i in range(0, len(outputRaw), chunk_size):
      chunk = outputRaw[i:i + chunk_size]
      chunk_clean = chunk.replace(spaceDelimiter,
                                  " ").replace(ambiguousSpaceDelimiter, " ")
      translated = GoogleTranslator(
          source='la', target=translationLanguage).translate(text=chunk_clean)
      translateFile.write(translated + " ")
  except:
    print("Translator not installed.")


### Corpus Analysis (Levenshtein Distance) ###
def levenshtein_distance(s1, s2):
    """Calculates the minimum number of edits required to change s1 into s2."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def get_best_levenshtein_match(word, dictionary, max_edits):
    """Finds the best match in the dictionary within the allowed edit distance."""
    best_match = None
    best_distance = max_edits + 1  # Must be strictly less than this to qualify

    for dict_word in dictionary:
        # Optimization: If length difference is greater than max_edits, it's mathematically impossible to match
        if abs(len(word) - len(dict_word)) > max_edits:
            continue

        dist = levenshtein_distance(word, dict_word)
        if dist < best_distance:
            best_distance = dist
            best_match = dict_word
            # If we find a match with only 1 edit, take it immediately to save processing time
            if best_distance <= 1: 
                break

    return best_match

### Corpus Analysis (Optimized Segmentation) ###
def run_corpus_analysis(transliterated_text):
    print("\nStarting Corpus Analysis...")

    # 1. Setup
    clean_text = transliterated_text.replace(spaceDelimiter, " ").replace(
        ambiguousSpaceDelimiter, " ").replace("\n", " ").lower()
    trans_words = clean_text.split()
    total_words = len(trans_words)

    # 2. Build Dictionary
    known_words = set()
    reference_files = [f for f in os.listdir(referenceFolder) if f.endswith('.txt')]
    for filename in reference_files:
        with open(os.path.join(referenceFolder, filename), 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read().lower()
            for char in '.,;:!?()"[]{}': content = content.replace(char, ' ')
            known_words.update(content.split())

    if not known_words: return

    findings_segmentation = []
    findings_fuzzy = []
    corrected_text_list = []
    match_cache = {}

    # 3. Validation Logic
    def is_valid_merge(original, match):
        """Ensures the merge isn't just a wild guess."""
        # The match must contain most of the characters from the original pieces
        # This prevents 'er'+'e' becoming 'vere' if 'e' is too small to justify 'v'
        common = Counter(original) & Counter(match)
        overlap = sum(common.values())
        return (overlap / len(match)) >= 0.80 

    # 4. Analysis Loop
    i = 0
    while i < total_words:
        w1 = trans_words[i]

        if w1 in known_words:
            corrected_text_list.append(w1)
            i += 1
            continue

        if i + 1 < total_words:
            m2_cand = w1 + trans_words[i+1]
            if m2_cand in known_words:
                findings_segmentation.append(f"Merge '{w1}'+'{trans_words[i+1]}' -> '{m2_cand}' (Exact 100%)")
                corrected_text_list.append(m2_cand)
                i += 2
                continue

        # Fuzzy Typos
        best_match = None
        if w1 in match_cache:
            best_match = match_cache[w1]
        elif len(w1) >= 3:
            cutoff = 0.65 + (toleranceLevel * 0.05)
            matches = difflib.get_close_matches(w1, known_words, n=1, cutoff=cutoff)
            if matches:
                best_match = matches[0]
                # Calculate Score
                score = round(difflib.SequenceMatcher(None, w1, best_match).ratio() * 100)
                findings_fuzzy.append(f"Word '{w1}' -> '{best_match}' ({score}%)")
            match_cache[w1] = best_match

        if best_match:
            corrected_text_list.append(best_match)
            i += 1
            continue

        # Fuzzy Merges
        if i + 1 < total_words:
            m2_cand = w1 + trans_words[i+1]
            if len(m2_cand) >= 4:
                m_cutoff = min(0.85, 0.70 + (toleranceLevel * 0.05))
                m_matches = difflib.get_close_matches(m2_cand, known_words, n=1, cutoff=m_cutoff)
                if m_matches:
                    res = m_matches[0]
                    if is_valid_merge(m2_cand, res):
                        score = round(difflib.SequenceMatcher(None, m2_cand, res).ratio() * 100)
                        findings_segmentation.append(f"Merge '{w1}'+'{trans_words[i+1]}' -> '{res}' (Fuzzy {score}%)")
                        corrected_text_list.append(res)
                        i += 2
                        continue

        corrected_text_list.append(w1)
        i += 1

    # 5. Export
    with open(corpusReportPath, "w", encoding="utf-8") as f:
        f.write(f"CORPUS ANALYSIS REPORT\n======================\nTotal Words: {total_words}\n")
        f.write("\nSEGMENTATION:\n" + "\n".join(findings_segmentation))
        f.write("\n\nFUZZY TYPOS:\n" + "\n".join(findings_fuzzy))

    with open(fuzzyOutputPath, "w", encoding="utf-8") as f:
        f.write(" ".join(corrected_text_list))

    print(f"Analysis Complete.")
    print(f"Report: {corpusReportPath}")
    print(f"Fuzzy Text Output: {fuzzyOutputPath}")

if enableFuzzyMatching:
  run_corpus_analysis(outputRaw)

### Closing ###
outputNumberFile.close()
outputFile.close()
analysisFile.close()
