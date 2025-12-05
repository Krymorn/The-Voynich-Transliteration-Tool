# The Voynich Transcription Tool
# By: Krymorn (cmarbel)
#
# A tool for remapping the v101 transcription of the voynich manuscript.
# TVTT accounts for optional contextual mapping (Eg. A character meaning something different at the beginning of a word versus the end versus the middle) (see README.md)

### Setup ###
# Setup file names
mapPath = "number_mapping.txt"
inputMapPath = "output_mapping.txt"
inputPath = "v101_cleaned.txt"
outputPath = "output.txt"
outputv101Path = "output_numbers.txt"

# Read input
with open(inputPath, "r") as inputFile:
  inputData = inputFile.read()

# Read output mapping file
with open(inputMapPath, "r") as inputMapFile:
  inputMapData = inputMapFile.read()

# Output
outputFile = open(outputPath, "w")
outputv101File = open(outputv101Path, "w")

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
# Open and read number mapping file
with open(mapPath, "r") as mapFile:

  # Read each line
  for line in mapFile:
    line = line.strip()

    # Clean up - and = characters which typically mark the end of a line in the v101 transcription
    if "-" in line:
      line = line.replace("-", "")
    elif "=" in line:
      line = line.replace("=", "")

    # Ignore lines that are empty, formatted wrong, or are commented out by a ) character
    if not line or "=" not in line or line.startswith(")"):
      continue

    # Set up the is_final boolean
    is_final = False

    # Set up the is_initial boolean
    is_initial = False

    # Detect end-of-word (marked by "/" at the end of line in the input mapping file)
    if "/" in line:
      line = line.replace("/", "")
      is_final = True

    # Detect start-of-word (marked by "@" at the end of line in the input mapping file)
    if "@" in line:
      line = line.replace("@", "")
      is_initial = True

    # Break line into number and character
    number, char = line.split("=", 1)
    number = number.strip()
    char = char.strip()

    # Write to lists
    if is_final:
      num_to_char_final[number] = char
      char_to_num_final[char] = number
    elif is_initial:
      num_to_char_initial[number] = char
      char_to_num_initial[char] = number
    else:
      num_to_char_normal[number] = char
      char_to_num_normal[char] = number

# Open and read output mapping file
with open(inputMapPath, "r") as inputMapFile:

  # Read each line
  for line in inputMapFile.readlines():
    line = line.strip()

    # Ignore lines that are empty, formatted wrong, or are commented out by a ) character
    if not line or "=" not in line or line.startswith(")"):
      continue

    # Set up the is_final boolean
    is_final = False

    # Set up the is_initial boolean
    is_initial = False

    # Detect end-of-word
    if "/" in line:
      line = line.replace("/", "")
      is_final = True

    # Detect start-of-word
    if "@" in line:
      line = line.replace("@", "")
      is_start = True

    # Break line into number and character
    number, char = line.split("=", 1)
    number = number.strip()
    char = char.strip()

    # Write to lists
    if is_final:
      input_num_to_char_final[number] = char
      input_char_to_num_final[char] = number
    elif is_initial:
      num_to_char_initial[number] = char
      char_to_num_initial[char] = number
    else:
      input_num_to_char_normal[number] = char
      input_char_to_num_normal[char] = number

# Calculate the maximum length of any key in the input mapping, allowing dynamic checking for tokens length (1, 2, 3, etc.)
all_keys = (
  list(char_to_num_normal.keys()) + 
  list(char_to_num_final.keys()) + 
  list(char_to_num_initial.keys()) +
  list(num_to_char_normal.keys()) + 
  list(num_to_char_final.keys()) +
  list(num_to_char_initial.keys())
)

# Get the maximum length of a mapping
MAX_KEY_LENGTH = max(len(k) for k in all_keys) if all_keys else 1


### Functions ###
# Determine if the indexed character starts a word
def is_word_start(index, data):
  # If it's the very first character of the file
  if index == 0:
    return True

  # Check if the previous character was a separator
  prev_char = data[index - 1]
  return prev_char in ["#", ",", "\n"]

# Determine if character is at the end of word
# Determine if the indexed character ends a word
def is_word_end(index, data, length=1):
  if index + length >= len(data):
    return True

  # Check if the previous character was a separator
  return data[index + length] in ["#", ",", "\n"]

# Get the character in the output mapping that corrosponds to the inputted number
def getChar(inputNum, index, data, length=1):

  # Return newlines as needed
  if inputNum == "\n":
    return "\n"

  # Check if character is at the end of a word
  at_end = is_word_end(index, data, length)
  at_start = is_word_start(index, data)

  # Check final character mapping first
  if at_end and inputNum in input_num_to_char_final:
    return input_num_to_char_final[inputNum]

  # Check initial character mapping second
  if at_start and inputNum in input_num_to_char_initial:
    return input_num_to_char_initial[inputNum]

  # Check normal character mapping third
  if inputNum in input_num_to_char_normal:
    return input_num_to_char_normal[inputNum]

  # Go to default final character mapping fourth
  if at_end and inputNum in num_to_char_final:
    return num_to_char_final[inputNum]

  # Go to default initial character mapping fifth
  if at_start and inputNum in num_to_char_initial:
    return num_to_char_initial[inputNum]

  # Go to default character mapping sixth
  return num_to_char_normal.get(inputNum, "")

# Get the number in the numbers mapping that corrosponds to the inputted character
def getNum(inputChar, index, data):

  # Return newlines as needed
  if inputChar == "\n":
    return "\n"

  # Calculate length based on the input string (e.g., "4o" is length 2)
  length = len(inputChar)

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
# Start file with a . for formatting purposes
outputv101File.write(".")

# Use a while loop to allow skipping indices for multi-character matches
i = 0
while i < len(inputData):
  ch = inputData[i]

  # Write newlines as needed
  if ch == "\n":
    outputv101File.write("\n")
    outputFile.write("\n")
    i += 1
    continue

  # Write # and , as needed
  if ch in ["#", ","]:
    outputv101File.write(ch + ".")
    outputFile.write(ch)
    i += 1
    continue

  # Check if the next characters form a known key (e.g., "4o")
  match_str = ch
  match_len = 1

  for length in range(MAX_KEY_LENGTH, 0, -1):
    if i + length > len(inputData):
      continue

    chars = inputData[i : i + length]

    # If the sequence exists in the input map, use it
    if chars in char_to_num_normal or chars in char_to_num_final or chars in char_to_num_initial:
      match_str = chars
      match_len = length
      break

  # Get characters and numbers
  encoded = getNum(match_str, i, inputData)
  decoded = getChar(encoded, i, inputData, match_len)

  # Write to output files
  outputv101File.write(encoded + ".")
  outputFile.write(decoded)

  # Increment index by the length of the matched token
  i += match_len

# Close output files
outputv101File.close()
outputFile.close()
