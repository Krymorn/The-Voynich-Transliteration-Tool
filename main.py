# The Voynich Transliteration Tool
# By: Krymorn (cmarbel)
# Version: 1.5.0
#
# A tool for remapping the v101 transcription of the voynich manuscript.
# Read the README.md file for a full explanation of all features.
#
# Note: The v101 transcription used does not include the v101 extended character set.

### Imports ###
import math
from collections import Counter
import deep_translator
import matplotlib.pyplot as plt
import numpy as np

### Setup ###
# Delimiter and symbol configuration
# Note: Recommended to keep delimiters and symbols as they are, as the default settings work specifically with the v101 transcription
# Do not set spaceDelimiter and/or ambiguousSpaceDelimiter to "" as that will break certain parts of the code
spaceDelimiter = "_"
ambiguousSpaceDelimiter = "-"

endOfWordMarker = "/"
startOfWordMarker = "@"

commentOutChar = ")"

firstOccuranceMarker = "'"
secondOccuranceMarker = "\""  # Note: Python requires you to have a \ before a " character because multiple " characters in a row mess up Python syntax
thirdOccuranceMarker = ":"
fourthOccuranceMarker = ";"

# --- FEATURE 3: SECTIONING ---
# Limit processing to specific lines (useful for checking Currier A vs Currier B)
# Set endLine to None to process until the end of the file.
# Example: startLine = 0, endLine = 1000 (Analyzes only the first 1000 lines)
startLine = 0 
endLine = None    # Leave as "None" if you want to continue to the end of the v101 transcription

# Enable/disable frequency analysis and character entropy calculations
enableAnalysis = False

# Enable/disable graph generation of Zipf's law analysis
enableZipfsLawGeneration = False

# Enable/disable HTML generation for comparison between your output and the Voynich Manuscript
enableHTMLComparison = False

# Enable/disable translation attempt and/or printing list of possible languages
enableTranslation = False
enablePrintLanguages = False

# Setup file names
mapPath = "mapping.txt" # Make sure this matches your actual mapping file name
inputPath = "v101_cleaned.txt"
outputPath = "output.txt"
outputNumberPath = "output_numbers.txt"
analysisPath = "analysis.txt"
translatePath = "translated.txt"

# Read input
with open(inputPath, "r") as inputFile:
    # Read all lines into a list first
    all_lines = inputFile.readlines()

    # --- APPLY SECTIONING ---
    # Slice the lines based on user config
    if endLine is None:
        selected_lines = all_lines[startLine:]
    else:
        selected_lines = all_lines[startLine:endLine]

    print(f"Processing lines {startLine} to {len(all_lines) if endLine is None else endLine}...")

    # Join them back into a single string for the rest of the script
    inputData = "".join(selected_lines)

    # Replace periods with equal signs
    inputData = inputData.replace(".", spaceDelimiter)

    # Replace commas with dashes
    inputData = inputData.replace(",", ambiguousSpaceDelimiter)

# Read output mapping file
with open(mapPath, "r") as inputMapFile:
  inputMapData = inputMapFile.read()

# Output
outputFile = open(outputPath, "w")
outputNumberFile = open(outputNumberPath, "w")

# Setup lists
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

### Mapping ###
# Set up the is_initial boolean
is_initial = False

# Set up the is_final boolean
is_final = False

# Set up the is_first boolean
is_first = False

# Set up the is_second boolean
is_second = False

# Set up the is_third boolean
is_third = False

# Set up the is_fourth boolean
is_fourth = False

# Open and read mapping file
with open(mapPath, "r") as mapFile:

  # Read each line
  for line in mapFile:

    line = line.strip()

    is_initial = False
    is_final = False
    is_first = False
    is_second = False
    is_third = False
    is_fourth = False

    # Ignore lines that are empty, formatted wrong, or are commented out by a ) character
    if not line or "=" not in line or "~" not in line or line.startswith(commentOutChar):
      continue

    # Detect start-of-word (marked by "@" at the end of line in the input mapping file)
    if line.endswith(startOfWordMarker):
      line = line[:-1]
      is_initial = True

    # Detect end-of-word (marked by "/" at the end of line in the input mapping file)
    if line.endswith(endOfWordMarker):
      line = line[:-1]
      is_final = True

    # Detect end-of-word (marked by "/" at the end of line in the input mapping file)
    if line.endswith(firstOccuranceMarker):
      line = line[:-1]
      is_first = True

    # Detect end-of-word (marked by "/" at the end of line in the input mapping file)
    if line.endswith(secondOccuranceMarker):
      line = line[:-1]
      is_second = True

    # Detect end-of-word (marked by "/" at the end of line in the input mapping file)
    if line.endswith(thirdOccuranceMarker):
      line = line[:-1]
      is_third = True

    # Detect end-of-word (marked by "/" at the end of line in the input mapping file)
    if line.endswith(fourthOccuranceMarker):
      line = line[:-1]
      is_fourth = True

    # Break line into number and character
    number, line2 = line.split("=", 1)
    char, outputChar = line2.split("~", 1)
    number = number.strip()
    char = char.strip()
    outputChar = outputChar.strip()

    # Write to lists
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

# Calculate the maximum length of any key in the input mapping, allowing dynamic checking for tokens length (1, 2, 3, etc.)
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


### Functions ###
# Determine if the indexed character starts a word
def is_word_start(index, data):
  if index == 0:
    return True
  prev_char = data[index - 1]
  return prev_char in [spaceDelimiter, ambiguousSpaceDelimiter, "\n"]


# Determine if the indexed character ends a word
def is_word_end(index, data, length=1):
  if index + length >= len(data):
    return True
  return data[index +
              length] in [spaceDelimiter, ambiguousSpaceDelimiter, "\n"]


# Get the character in the output mapping that corresponds to the inputted number
def getChar(inputNum, index, data, length, occurrence):

  # Return newlines as needed
  if inputNum == "\n":
    return "\n"

  # Check context
  at_end = is_word_end(index, data, length)
  at_start = is_word_start(index, data)

  # 1. Check initial (Start of word)
  if at_start and inputNum in input_num_to_char_initial:
    return input_num_to_char_initial[inputNum]

  # 2. Check final (End of word)
  if at_end and inputNum in input_num_to_char_final:
    return input_num_to_char_final[inputNum]

  # 3. Check occurrence counts (1st time seeing this char, 2nd time, etc.)
  # Only applies to a maximum of 4 characters because that is the maximum numbers of times the same character appears in a word in the Voynich Manuscript
  if occurrence == 1 and inputNum in input_num_to_char_first:
    return input_num_to_char_first[inputNum]

  if occurrence == 2 and inputNum in input_num_to_char_second:
    return input_num_to_char_second[inputNum]

  if occurrence == 3 and inputNum in input_num_to_char_third:
    return input_num_to_char_third[inputNum]

  if occurrence == 4 and inputNum in input_num_to_char_fourth:
    return input_num_to_char_fourth[inputNum]

  # 4. Check normal (Default fallback)
  if inputNum in input_num_to_char_normal:
    return input_num_to_char_normal[inputNum]

  return num_to_char_normal.get(inputNum, "")


# Get the number in the numbers mapping that corresponds to the inputted character
def getNum(inputChar, index, data, occurrence):

  if inputChar == "\n":
    return "\n"

  length = len(inputChar)
  at_end = is_word_end(index, data, length)
  at_start = is_word_start(index, data)

  # 1. Check Initial/Final
  if at_end and inputChar in char_to_num_final:
    return char_to_num_final[inputChar]

  if at_start and inputChar in char_to_num_initial:
    return char_to_num_initial[inputChar]

  # 2. Check Occurrence Counts
  if occurrence == 1 and inputChar in char_to_num_first:
    return char_to_num_first[inputChar]

  if occurrence == 2 and inputChar in char_to_num_second:
    return char_to_num_second[inputChar]

  if occurrence == 3 and inputChar in char_to_num_third:
    return char_to_num_third[inputChar]

  if occurrence == 4 and inputChar in char_to_num_fourth:
    return char_to_num_fourth[inputChar]

  # 3. Fallback to Normal
  return char_to_num_normal.get(inputChar, "")


### Main ###
# Start numbers file with a . for formatting purposes
outputNumberFile.write(".")

i = 0
# Dictionary to track how many times specific characters appear in the current word
word_char_counts = {}

while i < len(inputData):
  ch = inputData[i]

  # Write newlines as needed
  if ch == "\n":
    outputNumberFile.write("\n.")
    outputFile.write("\n")
    word_char_counts.clear()  # Reset all counts for new word
    i += 1
    continue

  # Write = and - as needed
  if ch in [spaceDelimiter, ambiguousSpaceDelimiter]:
    outputNumberFile.write(ch + ".")
    outputFile.write(ch)
    word_char_counts.clear()  # Reset all counts for new word
    i += 1
    continue

  # Check if the next characters form a known key (e.g., "4o")
  match_str = ch
  match_len = 1

  # Deals with getting the characters if there is multi-character input
  for length in range(MAX_KEY_LENGTH, 0, -1):
    if i + length > len(inputData):
      continue

    inputChars = inputData[i:i + length]

    # If the sequence exists in ANY of the input maps
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

  # Calculate occurrence for this specific token
  current_occurrence = word_char_counts.get(match_str, 0) + 1
  word_char_counts[match_str] = current_occurrence

  # Get characters and numbers, passing the occurrence count
  encoded = getNum(match_str, i, inputData, current_occurrence)
  decoded = getChar(encoded, i, inputData, match_len, current_occurrence)

  # Write to output files
  outputNumberFile.write(encoded + ".")
  outputFile.write(decoded)

  # Increment index by the length of the matched token
  i += match_len


### Analysis ###
# Close and reopen outputFile to make it readable
outputFile.close()
outputFile = open(outputPath, "r")

# Read raw output for word analysis (keeping delimiters to identify word boundaries)
outputRaw = outputFile.read()

# Prepare clean output for character analysis (stripping delimiters)
outputClean = outputRaw.replace(spaceDelimiter, "")
outputClean = outputClean.replace(ambiguousSpaceDelimiter, "")
outputClean = outputClean.replace("\n", "")

# This ensures Zipf's law can actually see individual words
outputForWords = outputRaw.replace(spaceDelimiter, " ")
outputForWords = outputForWords.replace(ambiguousSpaceDelimiter, " ")
outputForWords = outputForWords.replace("\n", " ")

# Set up writing to analysis file
analysisFile = open(analysisPath, "w")

# Count characters
counts = Counter(outputClean)
total_chars = len(outputClean)

# --- FEATURE 4: REDUPLICATION ---
def analyze_reduplication(word_string):
    analysisFile.write("\n_____________________________\n")

    # Normalize delimiters
    normalized = word_string.replace("\n", " ").replace(ambiguousSpaceDelimiter, " ").replace(spaceDelimiter, " ")
    words = [w for w in normalized.split(" ") if w]

    redup_pairs = []
    redup_count = 0

    # Check for immediate repetition (Word[i] == Word[i+1])
    for k in range(len(words) - 1):
        if words[k] == words[k+1]:
            redup_count += 1
            redup_pairs.append(words[k])

    analysisFile.write(f"\nImmediate Reduplications (Word Repeated Twice): {redup_count}\n")
    if redup_count > 0:
        c = Counter(redup_pairs)
        analysisFile.write("Most Frequent Repeating Words (e.g. 'cat cat'):\n")
        for word, cnt in c.most_common(10):
            analysisFile.write(f"{{ {word}: {cnt} times }}\n")
    analysisFile.write("_____________________________\n")

# Word Part Analysis (Prefixes, Suffixes, Affixes)
def analyze_word_parts():
  # Normalize delimiters: convert newlines and dashes to standard spaces for splitting
  normalized = outputRaw.replace("\n", spaceDelimiter).replace(
      ambiguousSpaceDelimiter, spaceDelimiter)

  # Create a list of words, removing empty entries
  words = [w for w in normalized.split(spaceDelimiter) if w]
  total_words = len(words)

  analysisFile.write("Total Words Processed: " + str(total_words) + "\n")
  analysisFile.write("_____________________________\n")

  # Word Frequency Analysis
  word_counts = Counter(words)
  analysisFile.write("\nMost Common Whole Words:\n")
  for word, count in word_counts.most_common(20):
    pct = round((count / total_words) * 100, 2)
    analysisFile.write(f"{{ {word}: {count}, {pct}% }}\n")
  analysisFile.write("_____________________________\n")

  # Check patterns of length 2 up to 4
  # Change as needed
  min_ngram = 2
  max_ngram = 4

  for n in range(min_ngram, max_ngram + 1):
    prefixes = []
    suffixes = []
    affixes = [
    ]  # Represents "All Substrings/Roots" found anywhere in the word

    for word in words:
      word_len = len(word)

      # Skip words shorter than the n-gram length
      if word_len < n:
        continue

      # Extract Prefix (Start)
      prefixes.append(word[:n])

      # Extract Suffix (End)
      suffixes.append(word[-n:])

      # Extract Substrings (Roots/Substrings)
      for i in range(0, word_len - n + 1):
        affixes.append(word[i:i + n])

    # Helper to write stats to file
    def write_stats(title, data_list):
      if not data_list:
        analysisFile.write(f"\n{title} (Length {n}): [Insufficient Data]\n")
        return

      item_counts = Counter(data_list)
      total_items = len(data_list)

      analysisFile.write(f"\n{title} (Length {n}):\n")

      # Sort by frequency and take top 20
      for item, count in item_counts.most_common(20):
        pct = round((count / total_items) * 100, 2)
        analysisFile.write(f"{{ {item}: {count}, {pct}% }}\n")

    # Execute writing to analysis file
    write_stats("Common Prefixes (Initial)", prefixes)
    write_stats("Common Suffixes (Final)", suffixes)
    # Renamed label to reflect that we are now scanning the whole word
    write_stats("Common Affixes (All Positions)", affixes)

# Character Entropy
def entropy():
  entropy = 0.0
  for count in counts.values():

    probability = count / total_chars
    entropy -= probability * math.log2(probability)

  analysisFile.write("Character Entropy: " + str(round(entropy, 3)) + "%\n")
  analysisFile.write("_____________________________\n\n")

# Character frequency
def frequency():
  freq = {}
  for char in set(outputClean):
    if char != "\n":
      freq[char] = outputClean.count(char)

  freq_sorted = sorted(freq.items(), key=lambda x: x[1], reverse=True)

  analysisFile.write("Character Frequency:\n")
  # Iterate through outputArray
  for char, count in freq_sorted:

    if char != "\n":
      #print("{ " + char + ": " + str(count) + ", " + str(round(count / total_chars * 100, 3)) + "% }")      # Optional for command line
      analysisFile.write("{ " + char + ": " + str(count) + ", " +
                         str(round(count / total_chars * 100, 3)) + "% }\n")

  analysisFile.write("_____________________________\n\n")

# Likely vowel finding
def sukhotin_vowel_analysis(text):  
  # Filter valid characters
  valid_chars = [c for c in text if c.isalnum()]
  alphabet = sorted(list(set(valid_chars)))
  n = len(alphabet)
  char_to_index = {c: i for i, c in enumerate(alphabet)}

  # 1. Build Adjacency Matrix (Row = char, Col = neighbor)
  matrix = [[0] * n for _ in range(n)]
  for k in range(len(valid_chars) - 1):
    i = char_to_index[valid_chars[k]]
    j = char_to_index[valid_chars[k+1]]
    matrix[i][j] += 1
    matrix[j][i] += 1  # Treat adjacency as undirected

  # 2. Initially assume everyone is a Consonant
  is_vowel = [False] * n

  analysisFile.write("\nSukhotin's Vowel Classification:\n")

  # 3. Iterative Selection
  while True:
    # Calculate "adjacency to current consonants" for each character
    scores = []
    for i in range(n):
      if is_vowel[i]:
        scores.append(-float('inf')) # Already a vowel
        continue

      score = 0
      for j in range(n):
        if not is_vowel[j]: # If neighbor is currently a consonant
            score += matrix[i][j]
      scores.append(score)

    # Find the best candidate
    max_score = max(scores)

    # Stop if the candidate doesn't interact with consonants mainly (heuristic threshold)
    if max_score <= 0:
      break

    candidate_idx = scores.index(max_score)

    # Mark as vowel
    is_vowel[candidate_idx] = True
    vowel_char = alphabet[candidate_idx]
    analysisFile.write(f"identified potential vowel: {vowel_char} (Score: {max_score})\n")

    # In standard Sukhotin, you subtract the interactions of the new vowel 
    # from the matrix so they don't count towards finding the next vowel.
    # (Simplified implementation implies we just stop counting it in the loop above)

  vowels = [alphabet[i] for i in range(n) if is_vowel[i]]
  consonants = [alphabet[i] for i in range(n) if not is_vowel[i]]

  analysisFile.write(f"\nFinal Vowels: {vowels}\n\n")
  analysisFile.write(f"Final Consonants: {consonants}\n")

# Analyse if enabled
if enableAnalysis:
  entropy()
  frequency()
  analyze_word_parts()
  analyze_reduplication(outputRaw) # NEW FEATURE CALL
  sukhotin_vowel_analysis(outputClean)


### Graph Zipf's Law ###
# Plot Zipf's Law on a graph and save it
def plot_zipf_law(text):
  # Get word counts
  words = text.split()
  counts = Counter(words)

  # Sort by frequency (most common first)
  sorted_counts = sorted(counts.values(), reverse=True)

  # Generate Ranks (1, 2, 3...)
  ranks = np.arange(1, len(sorted_counts) + 1)
  frequencies = np.array(sorted_counts)

  # Plotting
  plt.figure(figsize=(10, 6))
  plt.loglog(ranks, frequencies, marker=".", linestyle="none", label="Transliterated Data")

  # Generate Ideal Zipf Line (y = c / x) for comparison
  # We anchor the ideal line to the most frequent word
  c = frequencies[0]
  ideal_zipf = c / ranks
  plt.loglog(ranks, ideal_zipf, 'r--', label="Ideal Zipf's Law (Slope -1)")

  plt.title("Zipf's Law Analysis of Transliterated Text")
  plt.xlabel("Rank (log scale)")
  plt.ylabel("Frequency (log scale)")
  plt.legend()
  plt.grid(True, which="both", ls="-", alpha=0.5)

  # Save the plot
  plt.savefig("zipf_analysis.png")
  # plt.show() # Uncomment if you want it to pop up
  print("Zipf's law plot saved to zipf_analysis.png")

if enableZipfsLawGeneration:
  try:
    plot_zipf_law(outputForWords)
  except ImportError:
    print("Matplotlib not installed; skipping Zipf plot.")


### HTML Comparison of your output to the actual Voynich Manuscript ###
# Generate the HTML file with a visual comparison
def generate_html_report(original_text, transliterated_text):
  # Split by lines
  # Note: We replace your custom delimiters with standard newlines for display
  orig_lines = original_text.replace(spaceDelimiter, " ").split("\n")
  trans_lines = transliterated_text.replace(spaceDelimiter, " ").split("\n")

  html_content = """
  <html>
  <head>
      <style>
          body { font-family: sans-serif; padding: 20px; background: #f0f0f0; }
          .container { display: flex; flex-direction: column; gap: 10px; }
          .row { display: flex; background: white; border-bottom: 1px solid #ccc; padding: 10px; }
          .trans { flex: 1; padding-right: 10px; border-right: 1px solid #eee; color: #333; }
          .orig { flex: 1; padding-left: 10px; color: #0066cc; font-family: "Courier New", monospace; }
          h1 { text-align: center; }

          /* Optional: Add a web font for Voynich here if you have a .woff file */
          /* @font-face { font-family: 'Voynich'; src: url('voynich.woff'); } */
          /* .orig { font-family: 'Voynich'; } */
      </style>
  </head>
  <body>
      <h1>Voynich Transliteration Side-By-Side Comparison</h1>
      <div class="container">
          <div class="row" style="background:#ddd; font-weight:bold;">
              <div class="trans">Transliteration (Target)</div>
              <div class="orig">Original (Source)</div>
          </div>
  """

  # Iterate through lines (zip stops at the shortest list)
  for t_line, o_line in zip(trans_lines, orig_lines):
      if not t_line.strip() and not o_line.strip():
          continue # Skip empty lines

      html_content += f"""
          <div class="row">
              <div class="trans">{t_line}</div>
              <div class="orig">{o_line}</div>
          </div>
      """

  html_content += """
      </div>
  </body>
  </html>
  """

  with open("comparison.html", "w", encoding="utf-8") as f:
      f.write(html_content)
  print("HTML Report saved to comparison.html")

if enableHTMLComparison:
  generate_html_report(inputData, outputRaw)


### Translate ###
# Print all possible languages in terminal is enabled
if enablePrintLanguages:
  langs_dict = deep_translator.GoogleTranslator().get_supported_languages(
      as_dict=True)
  print(langs_dict)

# Empty translate file
translateFile = open(translatePath, "w")
translateFile.close()

# Reopen translate file for appending
translateFile = open(translatePath, "a")

# Get length of output file
outputLength = len(outputFile.read())
outputLengthDuplicate = outputLength

# Attempt to translate output if enabled
if enableTranslation:
  # Translate output file
  # Replace target='en' with another language of your choice if you want (e.g. target='de' for German output)
  chunk_size = 4500  # Keep chunk under 5000 characters to be safe (Google Translate only allows up to 5000 characters per translation)

  # Loop through outputRaw in steps of 4500
  for i in range(0, len(outputRaw), chunk_size):
    # Slice the string to get just this chunk
    chunk = outputRaw[i:i + chunk_size]

    # Clean the chunk
    # Set .replace(ambiguousSpaceDelimiter, " ") to .replace(ambiguousSpaceDelimiter, "") if you want to ignore ambiguous spaces
    chunk_clean = chunk.replace(spaceDelimiter, " ").replace(ambiguousSpaceDelimiter, " ")

    # Translate only this chunk
    # Default is translating to latin (set enableTransltion to True if you want a list fo every avalible language in terminal)
    translated = deep_translator.GoogleTranslator(
        source='la', target='en').translate(text=chunk_clean)
    translateFile.write(translated + " ")

### Closing ###
# Close output files
outputNumberFile.close()
outputFile.close()

# Close analysis file
analysisFile.close()

# Close translate file
translateFile.close()
