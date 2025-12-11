# The Voynich Transliteration Tool
# By: Krymorn (cmarbel)
# Version: 1.2.2
#
# A tool for remapping the v101 transcription of the voynich manuscript.
# TVTT accounts for optional contextual mapping (Eg. A character meaning something different at the beginning of a word versus the end versus the middle) (see README.md)
# 
# Note: The v101 transcription used does not include the v101 extended character set.


### Imports ###
import math
from collections import Counter


### Setup ###
# Delimiter and symbol configuration
# Note: Recommended to keep delimiters and symbols as they are, as the default settings work specifically with the v101 transcription
# Do not set spaceDelimiter and/or ambiguousSpaceDelimiter to "" as that will break certain parts of the code
spaceDelimiter = "="
ambiguousSpaceDelimiter = "-"

endOfWordMarker = "/"
startOfWordMarker = "@"

commentOutChar = ")"

# Enable/disable frequency analysis and character entropy calculations
enableAnalysis = True

# Setup file names
mapPath = "mapping.txt"
inputPath = "v101_cleaned.txt"
outputPath = "output.txt"
outputNumberPath = "output_numbers.txt"
analysisPath = "analysis.txt"

# Read input
with open(inputPath, "r") as inputFile:
  inputData = inputFile.read()
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
num_to_char_final  = {}

char_to_num_normal = {}
char_to_num_final  = {}

input_num_to_char_normal = {}
input_num_to_char_final  = {}

input_char_to_num_normal = {}
input_char_to_num_final  = {}

num_to_char_initial = {}
char_to_num_initial = {}

input_num_to_char_initial = {}
input_char_to_num_initial = {}


### Mapping ###
# Open and read mapping file
with open(mapPath, "r") as mapFile:

  # Read each line
  for line in mapFile:
    line = line.strip()

    # Ignore lines that are empty, formatted wrong, or are commented out by a ) character
    if not line or spaceDelimiter not in line or "~" not in line or line.startswith(commentOutChar):
      continue

    # Set up the is_initial boolean
    is_initial = False
    
    # Set up the is_final boolean
    is_final = False

    # Detect start-of-word (marked by "@" at the end of line in the input mapping file)
    if line.endswith(startOfWordMarker):
      line = line[:-1]
      is_initial = True
      
    # Detect end-of-word (marked by "/" at the end of line in the input mapping file)
    if line.endswith(endOfWordMarker):
      line = line[:-1]
      is_final = True

    # Break line into number and character
    number, line2 = line.split(spaceDelimiter, 1)
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

    else:
      input_char_to_num_normal[char] = number
      input_num_to_char_normal[number] = outputChar
      char_to_num_normal[char] = number
      num_to_char_normal[number] = outputChar

# Calculate the maximum length of any key in the input mapping, allowing dynamic checking for tokens length (1, 2, 3, etc.)
all_keys = (
  list(input_char_to_num_normal.keys()) +
  list(input_char_to_num_final.keys()) +
  list(input_char_to_num_initial.keys()) +
  list(char_to_num_normal.keys()) +
  list(char_to_num_final.keys()) + 
  list(char_to_num_initial.keys()) +
  list(num_to_char_normal.keys()) + 
  list(num_to_char_final.keys()) +
  list(num_to_char_initial.keys())
)

MAX_KEY_LENGTH = max((len(k) for k in all_keys), default=1)


### Functions ###
# Determine if the indexed character starts a word
def is_word_start(index, data):
  # If it's the very first character of the file
  if index == 0:
    return True

  # Check if the previous character was a separator
  prev_char = data[index - 1]
  return prev_char in [spaceDelimiter, ambiguousSpaceDelimiter, "\n"]

# Determine if the indexed character ends a word
def is_word_end(index, data, length=1):
  if index + length >= len(data):
    return True

  # Check if the previous character was a separator
  return data[index + length] in [spaceDelimiter, ambiguousSpaceDelimiter, "\n"]

# Get the character in the output mapping that corrosponds to the inputted number
def getChar(inputNum, index, data, length=1):

  # Return newlines as needed
  if inputNum == "\n":
    return "\n"

  # Check if character is at the end of a word
  at_end = is_word_end(index, data, length)
  at_start = is_word_start(index, data)

  # Check normal character mapping first
  if inputNum in input_num_to_char_normal:
    return input_num_to_char_normal[inputNum]

  # Check initial character mapping second
  if at_start and inputNum in input_num_to_char_initial:
    return input_num_to_char_initial[inputNum]

  # Check final character mapping third
  if at_end and inputNum in input_num_to_char_final:
    return input_num_to_char_final[inputNum]

  # Go to default initial character mapping fourth
  if at_start and inputNum in num_to_char_initial:
    return num_to_char_initial[inputNum]

  # Go to default final character mapping fifth
  if at_end and inputNum in num_to_char_final:
    return num_to_char_final[inputNum]

  # Go to default character mapping sixth
  return num_to_char_normal.get(inputNum, "")

# Get the number in the numbers mapping that corrosponds to the inputted character
def getNum(inputChar, index, data):

  # Return newlines as needed
  if inputChar == "\n":
    return "\n"

  # Calculate length based on the input string (e.g., "4o" is length 2)
  length = len(inputChar)

  # Determine if character is at beginning, somewhere in the middle, or end of the word
  at_end = is_word_end(index, data, length)
  at_start = is_word_start(index, data)

  # Go to default final character mapping
  if at_end and inputChar in char_to_num_final:
    return char_to_num_final[inputChar]

  # Go to default initial character mapping
  if at_start and inputChar in char_to_num_initial:
    return char_to_num_initial[inputChar]

  return char_to_num_normal.get(inputChar, "")


### Main ###
# Start numbers file with a . for formatting purposes
outputNumberFile.write(".")

# Use a while loop to allow skipping indices for multi-character matches
i = 0
while i < len(inputData):
  ch = inputData[i]

  # Write newlines as needed
  if ch == "\n":
    outputNumberFile.write("\n.")
    outputFile.write("\n")
    i += 1
    continue

  # Write = and - as needed
  if ch in [spaceDelimiter, ambiguousSpaceDelimiter]:
    outputNumberFile.write(ch + ".")
    outputFile.write(ch)
    i += 1
    continue

  # Check if the next characters form a known key (e.g., "4o")
  match_str = ch
  match_len = 1

  # Deals with getting the characters if there is multi-character input
  for length in range(MAX_KEY_LENGTH, 0, -1):
    if i + length > len(inputData):
      continue

    # Setting the characters
    inputChars = inputData[i : i + length]

    # If the sequence exists in the input map, use it
    if inputChars in input_char_to_num_normal or inputChars in input_char_to_num_final or inputChars in input_char_to_num_initial:
      match_str = inputChars
      match_len = length
      break

  # Get characters and numbers
  encoded = getNum(match_str, i, inputData)
  decoded = getChar(encoded, i, inputData, match_len)

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

# Set up writing to analysis file
analysisFile = open(analysisPath, "w")

# Count characters
counts = Counter(outputClean)
total_chars = len(outputClean)

# Word Part Analysis (Prefixes, Suffixes, Affixes)
def analyze_word_parts():
  # Normalize delimiters: convert newlines and dashes to standard spaces for splitting
  normalized = outputRaw.replace("\n", spaceDelimiter).replace(ambiguousSpaceDelimiter, spaceDelimiter)

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
    affixes = [] # Represents "All Substrings/Roots" found anywhere in the word

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
          affixes.append(word[i : i + n])

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

  #print("Character Entropy: " + str(round(entropy, 3)) + "%\n")      # Optional for command line
  analysisFile.write("Character Entropy: " + str(round(entropy, 3)) + "%\n")
  analysisFile.write("_____________________________\n\n")

# Character frequency
def frequency():
  freq = {}
  for char in set(outputClean):
    if char != "\n":
      freq[char] = outputClean.count(char)

  freq_sorted = sorted(freq.items(), key=lambda x: x[1], reverse=True)

  #print("Character Frequency:")      # Optional for command line
  analysisFile.write("Character Frequency:\n")
  # Iterate through outputArray
  for char, count in freq_sorted:

    if char != "\n":
      #print("{ " + char + ": " + str(count) + ", " + str(round(count / total_chars * 100, 3)) + "% }")      # Optional for command line
      analysisFile.write("{ " + char + ": " + str(count) + ", " + str(round(count / total_chars * 100, 3)) + "% }\n")

  analysisFile.write("_____________________________\n\n")

# Analyse if enabled
if enableAnalysis:
  entropy()
  frequency()
  analyze_word_parts()


### Closing ###
# Close output files
outputNumberFile.close()
outputFile.close()

# Close analysis file
analysisFile.close()
